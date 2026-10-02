"""Chat completions through Snowflake Cortex's OpenAI-compatible REST endpoint."""
import logging

import requests

from hiresafe.config import get_settings

log = logging.getLogger(__name__)
TIMEOUT_S = 60


def _call(model: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    s = get_settings()
    resp = requests.post(
        f"https://{s['host']}/api/v2/cortex/v1/chat/completions",
        headers={"Authorization": f"Bearer {s['pat']}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages,
              "temperature": temperature, "max_completion_tokens": max_tokens},
        timeout=TIMEOUT_S,
    )
    if resp.status_code != 200:
        # Response body is Snowflake's error message; it never contains our token.
        raise RuntimeError(f"Cortex {model} returned HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"]


def chat_with_model(messages: list[dict], model: str | None = None,
                    temperature: float = 0.0, max_tokens: int = 1024) -> tuple[str, str]:
    """Like chat(), but returns (content, model_that_actually_answered)."""
    s = get_settings()
    primary = model or s["model"]
    try:
        return _call(primary, messages, temperature, max_tokens), primary
    except (requests.RequestException, RuntimeError) as e:
        fallback = s["fallback_model"]
        if primary == fallback:
            raise
        log.warning("Model %s failed (%s); retrying with %s", primary, e, fallback)
        return _call(fallback, messages, temperature, max_tokens), fallback


def chat(messages: list[dict], model: str | None = None,
         temperature: float = 0.0, max_tokens: int = 1024) -> str:
    """Send messages to Llama via Cortex. Falls back to the smaller model if the main one fails."""
    return chat_with_model(messages, model, temperature, max_tokens)[0]
