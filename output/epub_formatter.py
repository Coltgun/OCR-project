"""
EpubFormatter — EPUB output formatter using ebooklib.

Registration key: "epub"

Usage (via registry):
    from output.base import OutputFormatter
    formatter = OutputFormatter.get("epub")()
    epub_bytes = formatter.format(chapters, config)
    Path("output.epub").write_bytes(epub_bytes)

P0 CORRECTNESS: Chapters MUST be ordered by numeric chapter.number.
Never sort by str(chapter.number) — that produces lexicographic order:
1, 10, 11, 2 … which is a fatal bug in EPUB spine ordering.

Config keys consumed:
    epub_title         (str)  override auto-generated title
    epub_language      (str)  default "zh-CN"
    epub_identifier    (str)  override auto-generated UUID identifier
    epub_css           (str)  override full CSS content
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime

from ebooklib import epub

from core.types import Chapter
from output.base import OutputFormatter

logger = logging.getLogger(__name__)

_DEFAULT_CSS = """\
body {
    font-family: "Noto Serif CJK SC", "Source Han Serif CN", serif;
    line-height: 1.8;
    text-indent: 2em;
}
p { margin: 0.5em 0; text-indent: 2em; }
"""


class EpubFormatter(OutputFormatter, register_as="epub"):
    """Serialises an ordered list of Chapter objects into EPUB bytes.

    Each Chapter becomes one EPUB HTML chapter file. The spine is assembled
    in ascending numeric order of chapter.number (P0 correctness requirement).

    EPUB structure:
        style/default.css
        chapter_0001.xhtml, chapter_0002.xhtml, …  (4-digit zero-padded)
        nav.xhtml  (navigation document)
        toc.ncx    (NCX table of contents)
    """

    def file_extension(self) -> str:
        """File extension for EPUB output."""
        return "epub"

    def format(self, chapters: list[Chapter], config: dict) -> bytes:
        """Serialise *chapters* into EPUB bytes.

        Chapters are re-sorted by chapter.number (numeric) for safety even if
        the caller already sorted them.

        Args:
            chapters: Chapter objects to include, in any order.
            config:   Full application config dict.

        Returns:
            Raw EPUB bytes ready to write to disk.
        """
        if not chapters:
            logger.warning("EpubFormatter: no chapters provided — producing empty EPUB.")

        # P0: always sort numerically, never lexicographically
        ordered = sorted(chapters, key=lambda c: c.number)

        book = epub.EpubBook()
        self._set_metadata(book, ordered, config)
        css_item = self._add_css(book, config)
        epub_chapters = self._add_chapters(book, ordered, css_item)
        self._build_toc_and_spine(book, epub_chapters)

        return self._write_to_bytes(book)

    # ------------------------------------------------------------------
    # Internal build steps
    # ------------------------------------------------------------------

    @staticmethod
    def _set_metadata(
        book: epub.EpubBook,
        chapters: list[Chapter],
        config: dict,
    ) -> None:
        """Set EPUB metadata: identifier, title, language."""
        identifier = config.get(
            "epub_identifier",
            f"ocr-{uuid.uuid4().hex[:12]}",
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title = config.get("epub_title", f"OCR Export — {timestamp}")
        language = config.get("epub_language", "zh-CN")

        book.set_identifier(identifier)
        book.set_title(title)
        book.set_language(language)
        logger.debug(
            "EpubFormatter: metadata — id=%s, title=%r, lang=%s",
            identifier, title, language,
        )

    @staticmethod
    def _add_css(book: epub.EpubBook, config: dict) -> epub.EpubItem:
        """Create and add the CSS stylesheet to the book."""
        css_content = config.get("epub_css", _DEFAULT_CSS)
        css_item = epub.EpubItem(
            uid="style_default",
            file_name="style/default.css",
            media_type="text/css",
            content=css_content,
        )
        book.add_item(css_item)
        return css_item

    @staticmethod
    def _add_chapters(
        book: epub.EpubBook,
        chapters: list[Chapter],
        css_item: epub.EpubItem,
    ) -> list[epub.EpubHtml]:
        """Convert each Chapter to an EpubHtml item and add it to the book."""
        epub_chapters: list[epub.EpubHtml] = []

        for chapter in chapters:
            html_body = EpubFormatter._chapter_to_html_body(chapter)
            file_name = f"chapter_{chapter.number:04d}.xhtml"
            title = chapter.title or f"第{chapter.number}章"

            ep_chapter = epub.EpubHtml(
                title=title,
                file_name=file_name,
                lang="zh-CN",
            )
            ep_chapter.content = (
                '<html xmlns="http://www.w3.org/1999/xhtml" '
                'lang="zh-CN" xml:lang="zh-CN">'
                f"<head><title>{title}</title>"
                '<link rel="stylesheet" type="text/css" '
                'href="../style/default.css"/>'
                f"</head><body>{html_body}</body></html>"
            )
            ep_chapter.add_item(css_item)
            book.add_item(ep_chapter)
            epub_chapters.append(ep_chapter)
            logger.debug(
                "EpubFormatter: added chapter %d ('%s') → %s",
                chapter.number, title, file_name,
            )

        return epub_chapters

    @staticmethod
    def _chapter_to_html_body(chapter: Chapter) -> str:
        """Convert a Chapter's OCR results into an HTML body string.

        Each OCRResult becomes a <p> element. Newlines within a result
        are converted to <br/> elements.
        """
        parts: list[str] = []
        for result in chapter.results:
            text = result.text.strip()
            if not text:
                continue
            lines = text.split("\n")
            inner = "<br/>".join(lines)
            parts.append(f"<p>{inner}</p>")

        if not parts:
            parts.append("<p></p>")

        return "\n".join(parts)

    @staticmethod
    def _build_toc_and_spine(
        book: epub.EpubBook,
        epub_chapters: list[epub.EpubHtml],
    ) -> None:
        """Set the TOC, NCX, Nav, and spine on the book."""
        book.toc = tuple(
            epub.Link(c.file_name, c.title, c.id)
            for c in epub_chapters
        )
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        # P0: spine order follows epub_chapters which is already numeric-sorted
        book.spine = ["nav"] + epub_chapters

    @staticmethod
    def _write_to_bytes(book: epub.EpubBook) -> bytes:
        """Serialise the EpubBook to bytes using an in-memory buffer."""
        buf = io.BytesIO()
        epub.write_epub(buf, book)
        return buf.getvalue()
