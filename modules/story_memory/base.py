"""
StoryMemory ABC — stub for per-story LLM memory for translation consistency.

Do NOT implement this class until the story_memory module is formally scoped.
"""

from __future__ import annotations

from abc import abstractmethod

from core.registry import Registrable


class StoryMemory(Registrable):
    """Abstract base for per-story translation memory implementations (future feature)."""

    @abstractmethod
    def store_term(self, story_id: str, original: str, translation: str) -> None:
        """Persist a term translation for *story_id*.

        Args:
            story_id:    Unique identifier for the story/novel.
            original:    Source-language term (Chinese).
            translation: Target-language translation.
        """

    @abstractmethod
    def lookup_term(self, story_id: str, original: str) -> str | None:
        """Return the stored translation for *original* in *story_id*, or None.

        Args:
            story_id: Unique identifier for the story/novel.
            original: Source-language term to look up.
        """

    @abstractmethod
    def get_context(self, story_id: str, n_recent: int = 5) -> list[str]:
        """Return the *n_recent* most recent translated segments for *story_id*.

        Used to provide LLM context for translation consistency.
        """
