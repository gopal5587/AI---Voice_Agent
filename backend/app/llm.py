"""Thin OpenAI chat client. Every caller has a deterministic fallback, so the system works without a key."""
import json
import logging

import httpx

from .config import settings

log = logging.getLogger("llm")


def chat(messages: list[dict], json_mode: bool = False, max_tokens: int = 250, timeout: float = 8.0) -> str | None:
    if not settings.llm_enabled:
        return None
    body = {"model": settings.openai_model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        resp = httpx.post("https://api.openai.com/v1/chat/completions", json=body, timeout=timeout,
                          headers={"Authorization": f"Bearer {settings.openai_api_key}"})
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError) as exc:
        log.warning("LLM call failed, using deterministic fallback: %s", exc)
        return None


def chat_json(messages: list[dict], **kw) -> dict | None:
    raw = chat(messages, json_mode=True, **kw)
    try:
        return json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return None
