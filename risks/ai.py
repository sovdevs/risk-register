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
