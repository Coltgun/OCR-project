"""
llm/clients — cached OpenAI and AsyncOpenAI client factory.

Module-level caches keyed by (base_url, api_key, timeout, max_retries) so
that the underlying httpx connection pool is shared across stage instances
and across Pipeline.process() calls.

Usage:
    from llm.clients import get_openai_client, get_async_openai_client

    client = get_openai_client(base_url="https://openrouter.ai/api/v1", api_key="sk-...")
    async_client = get_async_openai_client(base_url=..., api_key=...)
"""

from __future__ import annotations

from typing import Optional

from openai import AsyncOpenAI, OpenAI

_sync_cache: dict[tuple, OpenAI] = {}
_async_cache: dict[tuple, AsyncOpenAI] = {}

_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_RETRIES = 3


def get_openai_client(
    base_url: str,
    api_key: str,
    timeout: float = _DEFAULT_TIMEOUT,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> OpenAI:
    """Return a cached synchronous OpenAI client for the given parameters.

    Args:
        base_url:    Provider base URL (e.g. https://openrouter.ai/api/v1).
        api_key:     API key.
        timeout:     Per-request timeout in seconds.
        max_retries: Number of retries on transient errors.

    Returns:
        A shared OpenAI instance (new on first call for this key, cached after).
    """
    key = (base_url, api_key, timeout, max_retries)
    if key not in _sync_cache:
        _sync_cache[key] = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
    return _sync_cache[key]


def get_async_openai_client(
    base_url: str,
    api_key: str,
    timeout: float = _DEFAULT_TIMEOUT,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> AsyncOpenAI:
    """Return a cached asynchronous AsyncOpenAI client.

    Args:
        base_url:    Provider base URL.
        api_key:     API key.
        timeout:     Per-request timeout in seconds.
        max_retries: Number of retries on transient errors.

    Returns:
        A shared AsyncOpenAI instance.
    """
    key = (base_url, api_key, timeout, max_retries)
    if key not in _async_cache:
        _async_cache[key] = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
    return _async_cache[key]
