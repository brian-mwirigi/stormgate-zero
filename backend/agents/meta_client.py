"""Thin client for the Meta Responses API and the open-weight endpoint.

Calls are OpenAI-compatible: POST {base}/responses with a model id.
When no key is configured the caller gets OfflineModelError and the
hydraulic loop keeps running on the local physics policies.
"""

from __future__ import annotations

import json
import ssl
import time
from typing import Any

import httpx

from backend.config import settings


class OfflineModelError(RuntimeError):
    """Raised when a hosted model cannot be called."""


def _ssl_context() -> ssl.SSLContext:
    """Use the Windows certificate store. certifi's bundle fails on this machine."""
    return ssl.create_default_context()


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _endpoint(open_weight: bool) -> tuple[str, str]:
    if open_weight:
        if not settings.open_weight_enabled:
            raise OfflineModelError("open-weight endpoint is not configured")
        return settings.open_weight_base_url, settings.open_weight_api_key
    if not settings.meta_enabled:
        raise OfflineModelError("MODEL_API_KEY is not configured")
    return settings.META_BASE_URL, settings.META_API_KEY


async def create_response(
    model: str,
    text: str,
    *,
    extra_input: list[dict] | None = None,
    reasoning_effort: str | None = None,
    open_weight: bool = False,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """POST /v1/responses and return the parsed JSON plus latency."""
    base, key = _endpoint(open_weight)
    content: list[dict] = [{"type": "input_text", "text": text}]
    if extra_input:
        content.extend(extra_input)
    payload: dict[str, Any] = {
        "model": model,
        "input": [{"role": "user", "content": content}],
    }
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, verify=_ssl_context()) as client:
        response = await client.post(f"{base}/responses", headers=_headers(key), json=payload)
    latency_ms = (time.perf_counter() - started) * 1000.0
    if response.status_code >= 400:
        raise OfflineModelError(f"{model} HTTP {response.status_code}: {response.text[:400]}")
    body = response.json()
    body["_latency_ms"] = round(latency_ms, 1)
    return body


def response_text(body: dict) -> str:
    """Pull assistant text out of a Responses API payload."""
    if isinstance(body.get("output_text"), str):
        return body["output_text"]
    chunks: list[str] = []
    for item in body.get("output", []) or []:
        if isinstance(item, str):
            chunks.append(item)
            continue
        for part in item.get("content", []) or []:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict):
                if part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
    return "\n".join(chunks).strip()


async def chat_completion(
    model: str,
    text: str,
    *,
    base_url: str,
    api_key: str,
    max_tokens: int = 512,
    temperature: float = 0.2,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """POST an OpenAI-compatible /chat/completions call. Used for the NVIDIA catalog."""
    if not api_key:
        raise OfflineModelError("NVIDIA_API_KEY is not configured")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "temperature": temperature,
        "top_p": 0.95,
        "max_tokens": max_tokens,
        "stream": False,
    }
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, verify=_ssl_context()) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=_headers(api_key),
            json=payload,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0
    if response.status_code >= 400:
        raise OfflineModelError(f"{model} HTTP {response.status_code}: {response.text[:400]}")
    body = response.json()
    body["_latency_ms"] = round(latency_ms, 1)
    return body


def chat_message_text(body: dict) -> str:
    """Pull the assistant string out of a chat-completions payload."""
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "\n".join(parts).strip()
    return ""


def parse_json_block(text: str) -> dict | None:
    """Accept raw JSON or a fenced ```json block."""
    raw = text.strip()
    if "```" in raw:
        start = raw.find("```")
        rest = raw[start + 3 :]
        if rest.startswith("json"):
            rest = rest[4:]
        end = rest.find("```")
        raw = rest[:end] if end >= 0 else rest
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def stream_response_text(
    model: str,
    content: list[dict],
    *,
    open_weight: bool = False,
    timeout: float = 60.0,
) -> tuple[str, float]:
    """POST /responses with stream=true and concatenate SSE text deltas."""
    base, key = _endpoint(open_weight)
    payload = {"model": model, "input": [{"role": "user", "content": content}], "stream": True}
    started = time.perf_counter()
    pieces: list[str] = []
    async with httpx.AsyncClient(timeout=timeout, verify=_ssl_context()) as client:
        async with client.stream("POST", f"{base}/responses", headers=_headers(key), json=payload) as response:
            if response.status_code >= 400:
                detail = (await response.aread()).decode("utf-8", errors="replace")[:400]
                raise OfflineModelError(f"{model} HTTP {response.status_code}: {detail}")
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    pieces.append(data)
                    continue
                delta = event.get("delta") or event.get("text") or ""
                if isinstance(delta, str):
                    pieces.append(delta)
                for choice in event.get("output", []) or []:
                    if isinstance(choice, str):
                        pieces.append(choice)
    return "".join(pieces), (time.perf_counter() - started) * 1000.0
