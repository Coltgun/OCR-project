"""
MarkdownFormatter — serialises OCR chapters to UTF-8 Markdown.

Registered as "md" in the OutputFormatter registry.
"""

from __future__ import annotations

from core.types import Chapter
from output.base import OutputFormatter


class MarkdownFormatter(OutputFormatter, register_as="md"):
    """Write OCR results as plain Markdown (UTF-8).

    Each chapter is introduced by a ``## Chapter N`` heading.
    OCR result lines are separated by blank lines.
    """

    def format(self, chapters: list[Chapter], config: dict) -> bytes:
        """Serialise *chapters* to Markdown bytes (UTF-8).

        Args:
            chapters: Chapters in numeric order.
            config:   Application config dict (unused for Markdown).

        Returns:
            UTF-8 encoded bytes.
        """
        lines: list[str] = []
        for chapter in sorted(chapters, key=lambda c: c.number):
            lines.append(f"## Chapter {chapter.number}")
            lines.append("")
            for result in chapter.results:
                if result.text:
                    lines.append(result.text)
                    lines.append("")
            lines.append("")
        return "\n".join(lines).encode("utf-8")

    def file_extension(self) -> str:
        """Return the file extension for Markdown output."""
        return "md"
