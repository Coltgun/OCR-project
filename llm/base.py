"""
LLMProvider ABC — base class for all LLM provider implementations.

Register a new provider:
    class MyProvider(LLMProvider, register_as="myprovider"):
        ...

Retrieve at runtime:
    provider_cls = LLMProvider.get(config["llm_provider"])
    provider = provider_cls()
    if provider.is_available():
        response = provider.complete(messages, config)
"""

from __future__ import annotations

from abc import abstractmethod

from core.registry import Registrable


class LLMProvider(Registrable):
    """Abstract base for LLM provider implementations.

    Providers wrap a local (Ollama) or remote (OpenRouter) LLM API and
    expose a single unified interface for text completion.

    Implementations must handle their own retry logic, timeouts, and
    error wrapping. They should raise RuntimeError on unrecoverable failures
    so callers can fall back gracefully.
    """

    @abstractmethod
    def complete(self, messages: list[dict], config: dict) -> str:
        """Send *messages* to the LLM and return the assistant response text.

        Args:
            messages: OpenAI-format message list,
                      e.g. [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            config:   Full application config dict.

        Returns:
            The assistant's response as a plain string.

        Raises:
            RuntimeError: If the provider is unavailable or the request fails permanently.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is currently reachable/configured.

        For API providers: checks that an API key is set in config.
        For local providers: performs a lightweight connectivity check (e.g. ping Ollama).
        Should be fast — avoid loading models just to check availability.
        """
