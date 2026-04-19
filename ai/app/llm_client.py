"""
Unified multi-provider LLM client with automatic fallback.

Provider chain:
  Primary:   OpenAI GPT-4o
  Fallback 1: Anthropic Claude (claude-sonnet-4-20250514)
  Fallback 2: OpenAI GPT-4o-mini

Supports both text-only and vision calls. Tracks which model actually
succeeded in the response metadata.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardised response from any LLM provider."""
    content: str
    model_used: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    fallback_used: bool = False
    errors: list[str] = field(default_factory=list)


# Provider configurations
_PROVIDERS = [
    {
        "name": "openai",
        "model": "gpt-4o",
        "vision": True,
        "env_key": "OPENAI_API_KEY",
    },
    {
        "name": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "vision": True,
        "env_key": "ANTHROPIC_API_KEY",
    },
    {
        "name": "openai",
        "model": "gpt-4o-mini",
        "vision": True,
        "env_key": "OPENAI_API_KEY",
    },
]

# Singleton clients
_openai_client = None
_anthropic_client = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI()
    return _openai_client


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
            key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if not key:
                return None
            _anthropic_client = anthropic.AsyncAnthropic(api_key=key)
        except ImportError:
            logger.warning("anthropic package not installed — Claude fallback unavailable")
            return None
    return _anthropic_client


async def _call_openai(
    model: str,
    system: str,
    messages: list[dict],
    response_format: dict | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> LLMResponse:
    """Call OpenAI API (works for both GPT-4o and GPT-4o-mini)."""
    oai = _get_openai()
    start = time.time()

    api_messages = [{"role": "system", "content": system}] + messages

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": api_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    resp = await oai.chat.completions.create(**kwargs)
    latency = int((time.time() - start) * 1000)

    usage = resp.usage
    return LLMResponse(
        content=resp.choices[0].message.content or "",
        model_used=model,
        provider="openai",
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        latency_ms=latency,
    )


async def _call_anthropic(
    model: str,
    system: str,
    messages: list[dict],
    response_format: dict | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> LLMResponse:
    """Call Anthropic Claude API, translating OpenAI message format."""
    client = _get_anthropic()
    if client is None:
        raise RuntimeError("Anthropic client not available")

    start = time.time()

    # Translate OpenAI-format messages to Anthropic format
    anthropic_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            # Vision message — translate content blocks
            blocks = []
            for block in content:
                if block.get("type") == "text":
                    blocks.append({"type": "text", "text": block["text"]})
                elif block.get("type") == "image_url":
                    url = block["image_url"]["url"]
                    if url.startswith("data:"):
                        # Extract base64 data
                        media_type = url.split(";")[0].split(":")[1]
                        b64_data = url.split(",", 1)[1]
                        blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_data,
                            },
                        })
            anthropic_messages.append({"role": role, "content": blocks})
        else:
            anthropic_messages.append({"role": role, "content": content})

    # If JSON output is requested, add instruction to system prompt
    effective_system = system
    if response_format:
        effective_system += "\n\nYou MUST respond with valid JSON only. No markdown fences or commentary."

    resp = await client.messages.create(
        model=model,
        system=effective_system,
        messages=anthropic_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    latency = int((time.time() - start) * 1000)
    content_text = ""
    for block in resp.content:
        if hasattr(block, "text"):
            content_text += block.text

    return LLMResponse(
        content=content_text,
        model_used=model,
        provider="anthropic",
        prompt_tokens=resp.usage.input_tokens if resp.usage else 0,
        completion_tokens=resp.usage.output_tokens if resp.usage else 0,
        latency_ms=latency,
    )


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════


async def complete(
    system: str,
    messages: list[dict],
    response_format: dict | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
    require_vision: bool = False,
) -> LLMResponse:
    """Call the LLM with automatic provider fallback.

    Tries primary (GPT-4o) -> fallback 1 (Claude) -> fallback 2 (GPT-4o-mini).
    Returns LLMResponse with model_used and fallback_used metadata.
    """
    errors: list[str] = []

    for i, provider in enumerate(_PROVIDERS):
        if require_vision and not provider["vision"]:
            continue

        # Skip providers without API keys
        env_key = provider["env_key"]
        if not os.environ.get(env_key, "").strip():
            errors.append(f"{provider['name']}/{provider['model']}: no {env_key}")
            continue

        try:
            if provider["name"] == "openai":
                resp = await _call_openai(
                    model=provider["model"],
                    system=system,
                    messages=messages,
                    response_format=response_format,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            elif provider["name"] == "anthropic":
                resp = await _call_anthropic(
                    model=provider["model"],
                    system=system,
                    messages=messages,
                    response_format=response_format,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                continue

            resp.fallback_used = i > 0
            resp.errors = errors
            if i > 0:
                logger.info(
                    "LLM fallback: %s/%s succeeded after %d failures",
                    provider["name"], provider["model"], i,
                )
            return resp

        except Exception as e:
            error_msg = f"{provider['name']}/{provider['model']}: {type(e).__name__}: {str(e)[:200]}"
            errors.append(error_msg)
            logger.warning("LLM provider failed: %s", error_msg)
            continue

    raise RuntimeError(
        f"All LLM providers failed. Errors: {'; '.join(errors)}"
    )
