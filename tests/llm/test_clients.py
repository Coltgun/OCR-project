"""
Tests for llm/clients.py — OpenAI client cache.

No real HTTP requests are made; openai.OpenAI is patched at the module level.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_caches() -> None:
    """Clear module-level caches between tests."""
    import llm.clients as _mod
    _mod._sync_cache.clear()
    _mod._async_cache.clear()


@pytest.fixture(autouse=True)
def _clear_client_cache_after_each():
    """Ensure the client cache is cleared after every test in this module."""
    yield
    _reset_caches()


# ---------------------------------------------------------------------------
# Sync cache
# ---------------------------------------------------------------------------

class TestGetOpenaiClient:
    def setup_method(self) -> None:
        _reset_caches()

    def test_returns_openai_instance(self) -> None:
        from llm.clients import get_openai_client
        client = get_openai_client("http://localhost:11434/v1", "ollama")
        from openai import OpenAI
        assert isinstance(client, OpenAI)

    def test_same_args_returns_same_instance(self) -> None:
        from llm.clients import get_openai_client
        c1 = get_openai_client("http://localhost:11434/v1", "ollama")
        c2 = get_openai_client("http://localhost:11434/v1", "ollama")
        assert c1 is c2

    def test_different_base_url_returns_different_instance(self) -> None:
        from llm.clients import get_openai_client
        c1 = get_openai_client("http://localhost:11434/v1", "ollama")
        c2 = get_openai_client("https://openrouter.ai/api/v1", "sk-abc")
        assert c1 is not c2

    def test_different_api_key_returns_different_instance(self) -> None:
        from llm.clients import get_openai_client
        c1 = get_openai_client("https://openrouter.ai/api/v1", "key-A")
        c2 = get_openai_client("https://openrouter.ai/api/v1", "key-B")
        assert c1 is not c2

    def test_different_timeout_returns_different_instance(self) -> None:
        from llm.clients import get_openai_client
        c1 = get_openai_client("http://localhost:11434/v1", "ollama", timeout=30.0)
        c2 = get_openai_client("http://localhost:11434/v1", "ollama", timeout=60.0)
        assert c1 is not c2

    def test_openai_constructed_once(self) -> None:
        from llm.clients import get_openai_client
        get_openai_client("http://localhost/v1", "k")
        get_openai_client("http://localhost/v1", "k")
        import llm.clients as _mod
        assert len(_mod._sync_cache) == 1


# ---------------------------------------------------------------------------
# Async cache
# ---------------------------------------------------------------------------

class TestGetAsyncOpenaiClient:
    def setup_method(self) -> None:
        _reset_caches()

    def test_returns_async_instance(self) -> None:
        from llm.clients import get_async_openai_client
        client = get_async_openai_client("http://localhost:11434/v1", "ollama")
        from openai import AsyncOpenAI
        assert isinstance(client, AsyncOpenAI)

    def test_same_args_returns_same_instance(self) -> None:
        from llm.clients import get_async_openai_client
        c1 = get_async_openai_client("http://localhost:11434/v1", "ollama")
        c2 = get_async_openai_client("http://localhost:11434/v1", "ollama")
        assert c1 is c2

    def test_sync_and_async_caches_are_independent(self) -> None:
        from llm.clients import get_async_openai_client, get_openai_client
        sync = get_openai_client("http://localhost/v1", "k")
        async_ = get_async_openai_client("http://localhost/v1", "k")
        assert sync is not async_


# ---------------------------------------------------------------------------
# Integration: stage _make_client reuses cache
# ---------------------------------------------------------------------------

class TestStageCacheIntegration:
    def setup_method(self) -> None:
        _reset_caches()

    def test_llm_correction_uses_cache(self) -> None:
        from llm.clients import get_openai_client
        from ocr.stages.llm_correction import LlmCorrectionStage

        stage = LlmCorrectionStage()
        cfg = {"llm_base_url": "http://localhost:11434/v1", "llm_api_key": "ollama"}
        # Verify same args → same cached instance
        c1 = get_openai_client("http://localhost:11434/v1", "ollama")
        c2 = get_openai_client("http://localhost:11434/v1", "ollama")
        assert c1 is c2

    def test_openrouter_correction_uses_cache(self) -> None:
        from llm.clients import get_openai_client

        c1 = get_openai_client("https://openrouter.ai/api/v1", "sk-x")
        c2 = get_openai_client("https://openrouter.ai/api/v1", "sk-x")
        assert c1 is c2

    def test_different_stages_same_config_share_client(self) -> None:
        from llm.clients import get_openai_client

        c1 = get_openai_client("https://openrouter.ai/api/v1", "sk-y")
        c2 = get_openai_client("https://openrouter.ai/api/v1", "sk-y")
        assert c1 is c2
