"""
client.py — Unified LLM client for DevRAG.

Primary provider is Claude (claude-sonnet-5 by default, claude-haiku-4-5 for
cheap steps). Groq, Mistral, and Ollama are available as fallbacks through
their OpenAI-compatible endpoints, so the same call sites work regardless of
which key is configured.

The public contract is intentionally identical to the old DevAgent client:

    msg, tokens = chat(messages, tools=..., system=..., json_mode=...)
    msg.content            -> str
    msg.tool_calls         -> list of ToolCall
    tc.id                  -> str
    tc.function.name       -> str
    tc.function.arguments  -> dict (already parsed)

Messages are accepted in OpenAI style (system / user / assistant with
tool_calls / tool) and converted to the Claude Messages API shape internally.

Notes on the Claude implementation:
  - No temperature/top_p (rejected on claude-sonnet-5); adaptive thinking is
    the model default, so the thinking parameter is omitted.
  - JSON output uses output_config.format with a json_schema when a schema is
    provided; otherwise a strict system instruction is used.
  - Prompt caching: cache_control is set on the system block and the first
    user block, which are stable across tool-loop iterations.
"""
from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, field
from typing import Generator, Optional

import httpx
from loguru import logger

from devrag import config

# ---------------------------------------------------------------------------
# Return types — shape-compatible with what the agent nodes expect
# ---------------------------------------------------------------------------


@dataclass
class ToolFunction:
    name: str
    arguments: dict


@dataclass
class ToolCall:
    id: str
    function: ToolFunction


@dataclass
class LLMMessage:
    content: str = ""
    tool_calls: Optional[list[ToolCall]] = None


# ---------------------------------------------------------------------------
# Usage / cost tracking
# ---------------------------------------------------------------------------

# USD per million tokens (input, output)
MODEL_PRICES = {
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-8": (5.00, 25.00),
}


class UsageTracker:
    """Thread-safe token and cost accounting across a process.

    Prompt caching economics (Claude): cache writes bill at 1.25x the input
    rate, cache reads at 0.1x — so cache_savings_usd shows what repeated
    context would have cost at the full rate minus what it actually cost.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with getattr(self, "_lock", threading.Lock()):
            self.input_tokens = 0
            self.output_tokens = 0
            self.cache_write_tokens = 0
            self.cache_read_tokens = 0
            self.requests = 0
            self.cost_usd = 0.0
            self.cache_savings_usd = 0.0

    def record(self, model: str, tokens_in: int, tokens_out: int,
               cache_write: int = 0, cache_read: int = 0):
        prices = MODEL_PRICES.get(model, (0.0, 0.0))
        in_rate, out_rate = prices[0] / 1e6, prices[1] / 1e6
        with self._lock:
            self.input_tokens += tokens_in
            self.output_tokens += tokens_out
            self.cache_write_tokens += cache_write
            self.cache_read_tokens += cache_read
            self.requests += 1
            self.cost_usd += (
                tokens_in * in_rate
                + tokens_out * out_rate
                + cache_write * in_rate * 1.25
                + cache_read * in_rate * 0.10
            )
            # What the cached tokens would have cost uncached, minus actual
            self.cache_savings_usd += cache_read * in_rate * 0.90 - cache_write * in_rate * 0.25

    def stats(self) -> dict:
        with self._lock:
            return {
                "requests": self.requests,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "cache_write_tokens": self.cache_write_tokens,
                "cache_read_tokens": self.cache_read_tokens,
                "cost_usd": round(self.cost_usd, 4),
                "cache_savings_usd": round(self.cache_savings_usd, 4),
            }


usage = UsageTracker()

# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

_anthropic_client = None
_provider: Optional[str] = None
# Providers that failed hard (e.g. invalid key) — skipped for the process lifetime
_dead_providers: set[str] = set()

_PROVIDER_ORDER = ("anthropic", "groq", "mistral", "ollama")


def get_provider() -> str:
    global _provider
    if _provider is None:
        _provider = config.get_primary_provider()
    return _provider


def _provider_chain() -> list[str]:
    """Providers to try, in order. A forced (non-auto) provider disables failover."""
    if config.LLM_PROVIDER != "auto":
        return [config.LLM_PROVIDER]
    available = config.get_available_providers()
    chain = [p for p in _PROVIDER_ORDER if available.get(p) and p not in _dead_providers]
    return chain or [get_provider()]


def _is_auth_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "401" in text or "authentication" in text or "invalid x-api-key" in text or "invalid api key" in text


def _is_unreachable(exc: Exception) -> bool:
    """Provider endpoint is down (e.g. Ollama daemon not running)."""
    text = str(exc).lower()
    return "connection refused" in text or "connecterror" in type(exc).__name__.lower()


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        key = config.ANTHROPIC_API_KEY or None
        _anthropic_client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    return _anthropic_client


# ---------------------------------------------------------------------------
# Message and tool conversion (OpenAI style -> Claude style)
# ---------------------------------------------------------------------------


def _parse_arguments(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _openai_tools_to_claude(tools: list[dict]) -> list[dict]:
    out = []
    for t in tools:
        fn = t.get("function", t)
        out.append(
            {
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return out


def _normalize_history(messages: list[dict], system: Optional[str]) -> tuple[str, list[dict]]:
    """Split out the system prompt and produce a valid Claude message list."""
    system_parts = [system] if system else []
    claude_msgs: list[dict] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""

        if role == "system":
            if content:
                system_parts.append(content)
            continue

        if role == "user":
            if content:
                claude_msgs.append({"role": "user", "content": content})
            continue

        if role == "assistant":
            blocks: list[dict] = []
            if content:
                blocks.append({"type": "text", "text": content})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": _parse_arguments(fn.get("arguments", {})),
                    }
                )
            if blocks:
                claude_msgs.append({"role": "assistant", "content": blocks})
            continue

        if role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id", ""),
                "content": str(content),
            }
            # Parallel tool results must land in ONE user message
            if claude_msgs and claude_msgs[-1]["role"] == "user" and isinstance(
                claude_msgs[-1]["content"], list
            ) and claude_msgs[-1]["content"] and claude_msgs[-1]["content"][0].get("type") == "tool_result":
                claude_msgs[-1]["content"].append(block)
            else:
                claude_msgs.append({"role": "user", "content": [block]})
            continue

    # An assistant message with tool_use blocks must be followed by tool_results.
    # Some nodes drop tool results from history, so strip orphaned tool_use blocks.
    for i, m in enumerate(claude_msgs):
        if m["role"] != "assistant" or not isinstance(m["content"], list):
            continue
        has_answer = (
            i + 1 < len(claude_msgs)
            and claude_msgs[i + 1]["role"] == "user"
            and isinstance(claude_msgs[i + 1]["content"], list)
            and any(b.get("type") == "tool_result" for b in claude_msgs[i + 1]["content"])
        )
        if not has_answer:
            kept = [b for b in m["content"] if b.get("type") != "tool_use"]
            m["content"] = kept or [{"type": "text", "text": "(continuing)"}]

    # First message must be user
    if not claude_msgs or claude_msgs[0]["role"] != "user":
        claude_msgs.insert(0, {"role": "user", "content": "Begin."})
    # No assistant prefill: never end on an assistant turn
    if claude_msgs[-1]["role"] == "assistant":
        claude_msgs.append({"role": "user", "content": "Continue."})

    return "\n\n".join(system_parts), claude_msgs


# ---------------------------------------------------------------------------
# Claude implementation
# ---------------------------------------------------------------------------


def _mark_prefix_cache(claude_msgs: list[dict]) -> None:
    """Set a cache breakpoint on the last content block of the conversation.

    In the coder/debugger tool loops the same history is resent every
    iteration with one new message appended, so caching the prefix turns
    each iteration's input from full price into a 0.1x cache read.
    """
    if not claude_msgs:
        return
    last = claude_msgs[-1]
    if isinstance(last["content"], str):
        last["content"] = [{"type": "text", "text": last["content"]}]
    if isinstance(last["content"], list) and last["content"]:
        last["content"][-1]["cache_control"] = {"type": "ephemeral"}


def _chat_claude(
    messages: list[dict],
    tools: Optional[list[dict]],
    system: Optional[str],
    max_tokens: int,
    json_mode: bool,
    json_schema: Optional[dict],
    model: str,
) -> tuple[LLMMessage, int]:
    client = _get_anthropic()
    system_text, claude_msgs = _normalize_history(messages, system)
    _mark_prefix_cache(claude_msgs)

    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": claude_msgs,
    }

    if system_text:
        # Cache the stable system prompt across loop iterations
        kwargs["system"] = [
            {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
        ]

    if tools:
        claude_tools = _openai_tools_to_claude(tools)
        # Tool definitions are static per loop — cache them too
        claude_tools[-1]["cache_control"] = {"type": "ephemeral"}
        kwargs["tools"] = claude_tools

    if json_schema:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": json_schema}}
    elif json_mode:
        instruction = "Respond with ONLY a valid JSON object. No markdown fences, no prose."
        if system_text:
            kwargs["system"][0]["text"] = system_text + "\n\n" + instruction
        else:
            kwargs["system"] = instruction

    response = client.messages.create(**kwargs)

    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(
                ToolCall(id=block.id, function=ToolFunction(name=block.name, arguments=dict(block.input)))
            )

    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cache_write = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
    usage.record(model, tokens_in, tokens_out, cache_write=cache_write, cache_read=cache_read)

    total = tokens_in + tokens_out + cache_write + cache_read
    return LLMMessage(content="".join(text_parts), tool_calls=tool_calls or None), total


def _stream_claude(
    messages: list[dict],
    system: Optional[str],
    max_tokens: int,
    model: str,
) -> Generator[str, None, None]:
    client = _get_anthropic()
    system_text, claude_msgs = _normalize_history(messages, system)
    _mark_prefix_cache(claude_msgs)
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": claude_msgs}
    if system_text:
        kwargs["system"] = [
            {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
        ]
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            yield text
        final = stream.get_final_message()
        usage.record(
            model,
            final.usage.input_tokens,
            final.usage.output_tokens,
            cache_write=getattr(final.usage, "cache_creation_input_tokens", 0) or 0,
            cache_read=getattr(final.usage, "cache_read_input_tokens", 0) or 0,
        )


# ---------------------------------------------------------------------------
# OpenAI-compatible fallback (Groq / Mistral / Ollama)
# ---------------------------------------------------------------------------

_OPENAI_COMPAT = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", lambda: config.GROQ_API_KEY, lambda: config.GROQ_MODEL),
    "mistral": ("https://api.mistral.ai/v1/chat/completions", lambda: config.MISTRAL_API_KEY, lambda: config.MISTRAL_MODEL),
    "ollama": (None, lambda: "ollama", lambda: config.OLLAMA_MODEL),  # URL built from host
}


def _chat_openai_compat(
    provider: str,
    messages: list[dict],
    tools: Optional[list[dict]],
    system: Optional[str],
    max_tokens: int,
    json_mode: bool,
) -> tuple[LLMMessage, int]:
    url, key_fn, model_fn = _OPENAI_COMPAT[provider]
    if provider == "ollama":
        url = f"{config.OLLAMA_HOST}/v1/chat/completions"

    full = ([{"role": "system", "content": system}] if system else []) + list(messages)
    body: dict = {"model": model_fn(), "messages": full, "max_tokens": max_tokens, "temperature": 0.0}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {key_fn()}", "Content-Type": "application/json"}

    for attempt in range(4):
        resp = httpx.post(url, json=body, headers=headers, timeout=120)
        if resp.status_code == 429:
            time.sleep(2 * (2 ** attempt))
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"{provider} HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        break
    else:
        raise RuntimeError(f"{provider} rate limited after retries")

    choice = data["choices"][0]["message"]
    tool_calls = [
        ToolCall(
            id=tc.get("id", f"call_{i}"),
            function=ToolFunction(
                name=tc["function"]["name"],
                arguments=_parse_arguments(tc["function"].get("arguments", "{}")),
            ),
        )
        for i, tc in enumerate(choice.get("tool_calls") or [])
    ]
    u = data.get("usage") or {}
    usage.record(model_fn(), u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
    return LLMMessage(content=choice.get("content") or "", tool_calls=tool_calls or None), u.get("total_tokens", 0)


def _stream_openai_compat(
    provider: str, messages: list[dict], system: Optional[str], max_tokens: int
) -> Generator[str, None, None]:
    url, key_fn, model_fn = _OPENAI_COMPAT[provider]
    if provider == "ollama":
        url = f"{config.OLLAMA_HOST}/v1/chat/completions"
    full = ([{"role": "system", "content": system}] if system else []) + list(messages)
    body = {"model": model_fn(), "messages": full, "max_tokens": max_tokens, "stream": True}
    headers = {"Authorization": f"Bearer {key_fn()}", "Content-Type": "application/json"}
    with httpx.stream("POST", url, json=body, headers=headers, timeout=120) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: ") or line.endswith("[DONE]"):
                continue
            try:
                delta = json.loads(line[6:])["choices"][0]["delta"].get("content")
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
            if delta:
                yield delta


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chat(
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: float = 0.0,  # accepted for compatibility; ignored on Claude
    json_mode: bool = False,
    json_schema: Optional[dict] = None,
    model: Optional[str] = None,
    fast: bool = False,
) -> tuple[LLMMessage, int]:
    """Unified chat completion with provider failover. Returns (message, total_tokens)."""
    max_tokens = max_tokens or config.MAX_TOKENS

    last_error: Optional[Exception] = None
    for provider in _provider_chain():
        try:
            if provider == "anthropic":
                resolved = model or (config.MODEL_FAST if fast else config.MODEL_PRIMARY)
                return _chat_claude(messages, tools, system, max_tokens, json_mode, json_schema, resolved)
            return _chat_openai_compat(
                provider, messages, tools, system, max_tokens, json_mode or bool(json_schema)
            )
        except Exception as e:
            last_error = e
            if _is_auth_error(e):
                _dead_providers.add(provider)
                logger.warning(f"{provider}: authentication failed — disabled for this process. "
                               f"Falling back to the next provider.")
            elif _is_unreachable(e):
                _dead_providers.add(provider)
                logger.warning(f"{provider}: unreachable — disabled for this process.")
            else:
                logger.warning(f"{provider}: request failed ({e}). Trying next provider.")

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}") from last_error


def stream_chat(
    messages: list[dict],
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> Generator[str, None, None]:
    """Streaming text generation (no tools), with provider failover.

    Failover only applies before the first chunk is yielded — once tokens
    are flowing, a mid-stream error propagates to the caller.
    """
    max_tokens = max_tokens or config.MAX_TOKENS

    last_error: Optional[Exception] = None
    for provider in _provider_chain():
        if provider == "anthropic":
            gen = _stream_claude(messages, system, max_tokens, model or config.MODEL_PRIMARY)
        else:
            gen = _stream_openai_compat(provider, messages, system, max_tokens)
        try:
            first = next(gen)
        except StopIteration:
            return
        except Exception as e:
            last_error = e
            if _is_auth_error(e):
                _dead_providers.add(provider)
                logger.warning(f"{provider}: authentication failed — disabled for this process. "
                               f"Falling back to the next provider.")
            elif _is_unreachable(e):
                _dead_providers.add(provider)
                logger.warning(f"{provider}: unreachable — disabled for this process.")
            else:
                logger.warning(f"{provider}: stream failed ({e}). Trying next provider.")
            continue
        yield first
        yield from gen
        return

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}") from last_error


# Backwards-compatible helpers (DevAgent call sites)


def call_llm(
    messages: list[dict],
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.0,
    json_mode: bool = False,
) -> tuple[str, int]:
    msg, tokens = chat(messages, tools=None, system=system, max_tokens=max_tokens, json_mode=json_mode)
    return msg.content or "", tokens


def call_llm_with_tools(
    messages: list[dict],
    tools: list[dict],
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.0,
) -> tuple[LLMMessage, int]:
    return chat(messages, tools=tools, system=system, max_tokens=max_tokens)
