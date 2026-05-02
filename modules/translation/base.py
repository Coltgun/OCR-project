"""
TranslationPipeline ABC — stub for future LLM-based translation with per-story memory.

Do NOT implement this class until the translation module is formally scoped.
"""

from __future__ import annotations

from abc import abstractmethod

from core.registry import Registrable


class TranslationPipeline(Registrable):
    """Abstract base for translation pipeline implementations (future feature)."""

    @abstractmethod
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: dict,
    ) -> str:
        """Translate *text* from *source_lang* to *target_lang*.

        Args:
            text:        Source text to translate.
            source_lang: BCP-47 language code, e.g. 'zh-CN'.
            target_lang: BCP-47 language code, e.g. 'en'.
            context:     Optional context dict (story_id, character names, etc.).

        Returns:
            Translated text string.
        """
