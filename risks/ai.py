import json

from openai import OpenAI

from .models import AISettings


class AIError(Exception):
    """Raised for both "not configured" and "request failed" cases, so
    views can catch one thing and show a friendly message instead of a
    raw stack trace."""


def _client_and_model():
    settings_obj = AISettings.load()
    if not settings_obj.api_key:
        raise AIError("No OpenAI API key configured. Add one in AI Settings.")
    return OpenAI(api_key=settings_obj.api_key), settings_obj.model


def generate_text(system_prompt, user_prompt):
    client, model = _client_and_model()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        raise AIError(f"OpenAI request failed: {exc}") from exc

    return response.choices[0].message.content


# Single source of truth for what the assistant can do — each entry drives
# both the OpenAI tool schema (below) and the "what this can do" panel in
# the UI (risks/views.py TOOL_REGISTRY re-export), so the prompt shown to
# the user and the prompt sent to the model can't drift apart.
#
# kind="read": executed immediately, server-side, result fed back to the
# model — never touches the database.
# kind="write": never executed by run_agent — always returned as a
# proposed action for the caller to gate behind approval.
TOOLS = [
    {
        "name": "search_risks",
        "kind": "read",
        "description": (
            "Search the risk register by owner, status, category, and/or "
            "whether the risk has an overdue mitigation. Any filter left "
            "out matches everything. Returns up to 20 matches."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "owner_username": {
                    "type": "string",
                    "description": (
                        "Matches either the risk's owner or the owner of "
                        "its mitigation action plan — these can be "
                        "different people."
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": ["identified", "assessing", "mitigating", "monitoring", "closed"],
                },
                "category": {"type": "string"},
                "overdue_only": {"type": "boolean"},
            },
        },
    },
    {
        "name": "get_risk_detail",
        "kind": "read",
        "description": (
            "Look up full detail for one risk by exact title: description, "
            "current score, and its mitigation if one exists."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "risk_title": {"type": "string", "description": "Exact title of the risk."},
            },
            "required": ["risk_title"],
        },
    },
    {
        "name": "create_mitigation",
        "kind": "write",
        "description": (
            "Propose a new mitigation/action plan for a risk. Not saved "
            "until the user approves it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "risk_title": {"type": "string", "description": "Exact title of the risk."},
                "treatment_type": {
                    "type": "string",
                    "enum": ["accept", "mitigate", "transfer", "avoid"],
                },
                "action_plan": {"type": "string"},
                "owner_username": {"type": "string"},
                "due_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": [
                "risk_title", "treatment_type", "action_plan",
                "owner_username", "due_date",
            ],
        },
    },
    {
        "name": "update_mitigation",
        "kind": "write",
        "description": (
            "Propose changes to a risk's existing mitigation (status, "
            "owner, due date, and/or action plan). Not saved until the "
            "user approves it. Omit fields that shouldn't change."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "risk_title": {"type": "string", "description": "Exact title of the risk."},
                "status": {
                    "type": "string",
                    "enum": ["not_started", "in_progress", "complete"],
                },
                "owner_username": {"type": "string"},
                "due_date": {"type": "string", "description": "YYYY-MM-DD"},
                "action_plan": {"type": "string"},
            },
            "required": ["risk_title"],
        },
    },
]

WRITE_TOOL_NAMES = {t["name"] for t in TOOLS if t["kind"] == "write"}

AGENT_TOOLS = [
    {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
    for t in TOOLS
]

MAX_TOOL_ROUNDS = 5


def run_agent(system_prompt, user_prompt, execute_read_tool):
    """Runs a tool-calling loop: the model can call read tools (executed
    immediately via execute_read_tool(name, args) -> JSON-serializable
    result, fed back so it can reason over real data) and/or write tools
    (never executed here — queued and returned as proposed actions for the
    caller to gate behind approval). Returns (final_text, proposed_actions).
    """
    client, model = _client_and_model()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    proposed_actions = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, tools=AGENT_TOOLS,
            )
        except Exception as exc:
            raise AIError(f"OpenAI request failed: {exc}") from exc

        message = response.choices[0].message
        if not message.tool_calls:
            return message.content, proposed_actions

        messages.append(message)
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments)
            except (TypeError, ValueError):
                args = {}
            if call.function.name in WRITE_TOOL_NAMES:
                proposed_actions.append({"tool": call.function.name, "args": args})
                tool_result = "Queued for user approval — not applied yet."
            else:
                tool_result = json.dumps(execute_read_tool(call.function.name, args))
            messages.append({
                "role": "tool", "tool_call_id": call.id, "content": tool_result,
            })

    raise AIError("Assistant didn't reach a final answer after several tool calls.")


def generate_json(system_prompt, user_prompt):
    client, model = _client_and_model()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise AIError(f"OpenAI request failed: {exc}") from exc

    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except (TypeError, ValueError) as exc:
        raise AIError(f"AI response wasn't valid JSON: {exc}") from exc
