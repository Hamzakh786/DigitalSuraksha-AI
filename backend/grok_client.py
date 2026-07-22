"""
Thin wrapper around the xAI (Grok) chat completions API.
Docs: https://docs.x.ai/  -- OpenAI-compatible /v1/chat/completions endpoint.

Set GROK_API_KEY (and optionally GROK_MODEL) as environment variables,
e.g. in a .env file next to this module (see .env.example).
"""

import os
import json
import requests

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("GROK_MODEL", "grok-4.5")


class GrokError(Exception):
    pass


def _api_key():
    key = os.environ.get("GROK_API_KEY")
    if not key:
        raise GrokError(
            "GROK_API_KEY is not set. Add it to backend/.env (copy .env.example) "
            "or export it in your shell before starting the server."
        )
    return key


def chat_completion(messages, temperature=0.2, max_tokens=800, json_mode=False):
    """
    messages: list of {"role": "system"|"user"|"assistant", "content": str}
    json_mode: if True, asks Grok to return valid JSON only.
    Returns the assistant's raw text content.
    """
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(GROK_API_URL, headers=headers, data=json.dumps(payload), timeout=60)

    if resp.status_code != 200:
        raise GrokError(f"Grok API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise GrokError(f"Unexpected Grok response shape: {data}") from e


def extract_json(text):
    """Best-effort extraction of a JSON object from a model response,
    tolerating stray markdown fences some models still add."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise GrokError(f"No JSON object found in model output: {text[:300]}")
    return json.loads(text[start:end + 1])
