"""
LLM call shim.

Single chokepoint for all model calls. v3.2 routes everything to the
OpenAI Python SDK (Chat Completions) so we can run on a cheap testing
model like `gpt-4o-mini` without going through OpenRouter or
OpenInference. The free-tier proxy was returning 502s mid-stream and
masking real coaching content.

All agents (Coach, Assessor, Client Task Agent, Code Generator, Judge)
keep calling `chat(...)` with the same kwargs; only the wire layer
changes when the provider does.

To swap providers later, set `LLM_BASE_URL` in the env (the OpenAI SDK
honors it as a base URL — any OpenAI-compatible endpoint works).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import openai

from backend.config import settings


logger = logging.getLogger("nxtcorp.llm")

# Transient upstream conditions worth retrying. 502 = bad gateway, 503 =
# unavailable, 504 = gateway timeout, 429 = rate-limited.
_RETRY_HTTP_CODES = {429, 502, 503, 504}
_RETRY_MAX_ATTEMPTS = 3   # total attempts including the first
_RETRY_DELAY_SECONDS = 2.0


# ---------- Public types ----------

@dataclass
class ChatResult:
    text: str                        # raw assistant text content
    input_tokens: int                # prompt tokens reported by OpenAI
    output_tokens: int               # completion tokens
    raw_response: dict[str, Any]     # full response.model_dump() for debugging


class LLMError(RuntimeError):
    pass


# ---------- Defensive JSON extraction (unchanged) ----------

_FENCE_RE = re.compile(r"```(?:json|py|python)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(raw: str) -> dict[str, Any]:
    """Pull a JSON object out of a model response.

    Strategy: try direct json.loads → strip fences → find brace span.
    Raises ValueError if nothing parseable is found.
    """
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = _FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"could not parse JSON from response: {raw[:200]!r}")


# ---------- Client cache ----------
#
# openai.OpenAI() reuses an httpx pool when reused. Cache one client per
# (api_key, base_url) pair so repeated agent calls share connections.

_client_cache: dict[tuple[str, str], openai.OpenAI] = {}


def _resolve_api_key() -> str:
    # Prefer the explicit LLM_API_KEY env-mapped field; fall back to the
    # legacy ANTHROPIC_API_KEY slot so existing .env files keep working
    # during the transition.
    return (
        getattr(settings, "llm_api_key", "")
        or getattr(settings, "anthropic_api_key", "")
        or ""
    )


def _resolve_base_url() -> str:
    return (
        getattr(settings, "llm_base_url", "")
        or getattr(settings, "anthropic_base_url", "")
        or ""
    )


def _resolve_model() -> str:
    return (
        getattr(settings, "llm_model", "")
        or getattr(settings, "anthropic_model", "")
        or "gpt-4o-mini"
    )


def _get_client() -> openai.OpenAI:
    api_key = _resolve_api_key()
    base_url = _resolve_base_url()
    key = (api_key, base_url)
    client = _client_cache.get(key)
    if client is None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = openai.OpenAI(**kwargs)
        _client_cache[key] = client
    return client


# ---------- Main entry point ----------

def chat(
    *,
    system: str,
    user: str,
    max_tokens: int = 500,
    model: Optional[str] = None,
    temperature: float = 0.4,
    response_format_json: bool = False,
    timeout_seconds: float = 60.0,
) -> ChatResult:
    """Call the configured OpenAI model with one system + one user message.

    Callers that want JSON output should set `response_format_json=True`;
    we map that to `response_format={"type": "json_object"}` which the
    model honors natively (gpt-4o-mini and friends).
    """
    if not _resolve_api_key():
        raise LLMError(
            "LLM_API_KEY (or legacy ANTHROPIC_API_KEY) is not set in the env"
        )

    client = _get_client()

    payload: dict[str, Any] = {
        "model": model or _resolve_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "timeout": timeout_seconds,
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}

    # Retry transient upstream issues (502/503/504/429 + connection errors).
    # Up to _RETRY_MAX_ATTEMPTS total tries, 2 s between them. Permanent
    # 4xx errors (401 auth, 400 bad request) raise on the first attempt.
    resp = None
    last_err: Optional[Exception] = None
    for attempt in range(1, _RETRY_MAX_ATTEMPTS + 1):
        try:
            resp = client.chat.completions.create(**payload)
            last_err = None
            break
        except openai.APIStatusError as e:
            status = getattr(e, "status_code", None)
            last_err = e
            if status in _RETRY_HTTP_CODES and attempt < _RETRY_MAX_ATTEMPTS:
                logger.warning(
                    "LLM HTTP %s on attempt %d/%d; retrying in %.1fs",
                    status, attempt, _RETRY_MAX_ATTEMPTS, _RETRY_DELAY_SECONDS,
                )
                time.sleep(_RETRY_DELAY_SECONDS)
                continue
            body_snippet = ""
            try:
                body_snippet = str(e.response.text)[:300]
            except Exception:
                pass
            raise LLMError(
                f"OpenAI HTTP {status}: {e}. body={body_snippet}"
            ) from e
        except openai.APIConnectionError as e:
            last_err = e
            if attempt < _RETRY_MAX_ATTEMPTS:
                logger.warning(
                    "LLM connection error on attempt %d/%d (%s); retrying in %.1fs",
                    attempt, _RETRY_MAX_ATTEMPTS, e, _RETRY_DELAY_SECONDS,
                )
                time.sleep(_RETRY_DELAY_SECONDS)
                continue
            raise LLMError(f"network error talking to OpenAI: {e}") from e
        except openai.APIError as e:
            # Generic non-retriable API error — surface immediately.
            raise LLMError(f"OpenAI API error: {e}") from e

    if resp is None:
        # Defensive — loop should have either set resp or raised.
        raise LLMError(f"LLM call exhausted retries: {last_err}")

    try:
        choice = resp.choices[0]
        text = (choice.message.content or "").strip()
    except (AttributeError, IndexError) as e:
        raise LLMError(f"unexpected OpenAI response shape: {resp}") from e

    usage = getattr(resp, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0

    try:
        raw_dump = resp.model_dump()
    except Exception:
        raw_dump = {}

    return ChatResult(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw_response=raw_dump,
    )


__all__ = ["chat", "ChatResult", "LLMError", "extract_json"]
