"""
PlainTextFormatter — serialises OCR chapters to UTF-8 plain text.

Registered as "txt" in the OutputFormatter registry.
"""

from __future__ import annotations

from core.types import Chapter
from output.base import OutputFormatter


class PlainTextFormatter(OutputFormatter, register_as="txt"):
    """Write OCR results as plain UTF-8 text.

    Each chapter is preceded by a separator line and its number.
    OCR result lines are written in numeric order.
    """

    def format(self, chapters: list[Chapter], config: dict) -> bytes:
        """Serialise *chapters* to plain text bytes (UTF-8).

        Args:
            chapters: Chapters in numeric order.
            config:   Application config dict (unused for plain text).

        Returns:
            UTF-8 encoded bytes.
        """
        lines: list[str] = []
        for chapter in sorted(chapters, key=lambda c: c.number):
            lines.append(f"── Chapter {chapter.number} ──")
            for result in chapter.results:
                if result.text:
                    lines.append(result.text)
            lines.append("")
        return "\n".join(lines).encode("utf-8")

    def file_extension(self) -> str:
        """Return the file extension for plain text output."""
        return "txt"
