"""
OutputFormatter ABC — base class for all output format implementations.

Register a new formatter:
    class MyFormatter(OutputFormatter, register_as="myformat"):
        ...

Select at runtime:
    formatter_cls = OutputFormatter.get(config["output_format"])
    formatter = formatter_cls()
    data = formatter.format(chapters, config)
    Path(output_path).write_bytes(data)
"""

from __future__ import annotations

from abc import abstractmethod

from core.registry import Registrable
from core.types import Chapter


class OutputFormatter(Registrable):
    """Abstract base for output format implementations.

    Implementations convert an ordered list of Chapter objects into
    serialised bytes in the target format (EPUB, TXT, Markdown, etc.).
    """

    @abstractmethod
    def format(self, chapters: list[Chapter], config: dict) -> bytes:
        """Serialise *chapters* into the target format.

        Chapters MUST be sorted numerically by chapter.number before
        this method is called. Implementations may assert this or
        silently re-sort for safety.

        Args:
            chapters: Chapters in numeric order.
            config:   Full application config dict.

        Returns:
            Raw bytes ready to be written to a file.
        """

    @abstractmethod
    def file_extension(self) -> str:
        """File extension for this format, without the leading dot (e.g. 'epub', 'txt')."""
