"""Anthropic chat model from env (.env in project or parent)."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from pathlib import Path
from typing import Any
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent
_ENV_LOADED = False


def load_llm_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    dotenv_path = find_dotenv()
    if dotenv_path:
        load_dotenv(dotenv_path)
    _ENV_LOADED = True


def get_llm_api_key() -> str:
    load_llm_env()
    for name in ("ANTHROPIC_API_KEY", "LLM_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        v = (os.environ.get(name) or "").strip()
        if v:
            return v
    return ""


def get_chat_model() -> Any:
    load_llm_env()
    key = get_llm_api_key()
    if not key:
        raise RuntimeError(
            "No LLM API key: set ANTHROPIC_API_KEY or LLM_API_KEY in .env"
        )
    model = (
        (os.environ.get("LLM_MODEL") or "").strip()
        or (os.environ.get("ANTHROPIC_MODEL") or "").strip()
        or "claude-sonnet-4-20250514"
    )
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, anthropic_api_key=key, max_tokens=4096)


def _retryable_llm_error(exc: BaseException) -> bool:
    try:
        from langchain_anthropic import (
            RateLimitError,
            InternalServerError,
            APIStatusError,
        )
    except ImportError:
        return False
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, RateLimitError):
            return True
        if isinstance(cur, InternalServerError):
            return True
        if isinstance(cur, APIStatusError):
            code = getattr(cur, "status_code", None)
            if code in (429, 500, 502, 503, 529):
                return True
        cur = cur.__cause__
    return False


async def ainvoke_with_retry(
    chain: Any, input_data: Any, *, max_attempts: int = 6
) -> Any:
    """Retry on Anthropic overload / rate limits / 5xx (transient)."""
    delay = 2.0
    last: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await chain.ainvoke(input_data)
        except BaseException as e:
            last = e
            if not _retryable_llm_error(e) or attempt >= max_attempts:
                raise
            jitter = random.uniform(0, 1.5)
            wait = delay + jitter
            logger.warning(
                "LLM transient error (%s), retry %d/%d in %.1fs",
                type(e).__name__,
                attempt,
                max_attempts,
                wait,
            )
            await asyncio.sleep(wait)
            delay = min(delay * 2, 60.0)
    raise last  # pragma: no cover
