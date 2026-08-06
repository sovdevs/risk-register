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


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_mitigation",
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
    },
    {
        "type": "function",
        "function": {
            "name": "update_mitigation",
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
    },
]


def run_agent(system_prompt, user_prompt):
    """Like generate_text, but the model may also call tools to propose a
    write. Proposed actions are returned alongside the answer, unexecuted —
    the caller is responsible for showing them to the user and only
    executing on explicit approval."""
    client, model = _client_and_model()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=AGENT_TOOLS,
        )
    except Exception as exc:
        raise AIError(f"OpenAI request failed: {exc}") from exc

    message = response.choices[0].message
    actions = []
    for call in message.tool_calls or []:
        try:
            args = json.loads(call.function.arguments)
        except (TypeError, ValueError):
            continue
        actions.append({"tool": call.function.name, "args": args})
    return message.content, actions


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
