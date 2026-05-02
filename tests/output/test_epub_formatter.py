"""Tests for EpubFormatter."""

from __future__ import annotations

import io
import zipfile

import pytest

from core.types import Chapter, OCRResult
from output.base import OutputFormatter
from output.epub_formatter import EpubFormatter, _DEFAULT_CSS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_chapter(number: int, texts: list[str], title: str = "") -> Chapter:
    """Create a Chapter with OCRResult entries for each text string."""
    results = [OCRResult(text=t, confidence=0.9) for t in texts]
    return Chapter(number=number, results=results, title=title)


def parse_epub_bytes(data: bytes) -> zipfile.ZipFile:
    """Return a ZipFile from raw EPUB bytes (EPUB is a ZIP)."""
    return zipfile.ZipFile(io.BytesIO(data))


def get_epub_names(data: bytes) -> list[str]:
    """Return the list of file names inside the EPUB ZIP."""
    with parse_epub_bytes(data) as zf:
        return zf.namelist()


def read_epub_file(data: bytes, name: str) -> str:
    """Read a specific file from the EPUB as a UTF-8 string."""
    with parse_epub_bytes(data) as zf:
        return zf.read(name).decode("utf-8")


def format_epub(chapters: list[Chapter], **cfg) -> bytes:
    config = {"epub_title": "Test", "epub_identifier": "test-001", **cfg}
    return EpubFormatter().format(chapters, config)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_epub(self) -> None:
        assert OutputFormatter.get("epub") is EpubFormatter

    def test_file_extension(self) -> None:
        assert EpubFormatter().file_extension() == "epub"

    def test_is_subclass_of_output_formatter(self) -> None:
        assert issubclass(EpubFormatter, OutputFormatter)


# ---------------------------------------------------------------------------
# format() — basic output
# ---------------------------------------------------------------------------

class TestFormat:
    def test_returns_bytes(self) -> None:
        chapters = [make_chapter(1, ["你好世界"])]
        result = format_epub(chapters)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_output_is_valid_zip(self) -> None:
        chapters = [make_chapter(1, ["你好世界"])]
        result = format_epub(chapters)
        assert zipfile.is_zipfile(io.BytesIO(result))

    def test_empty_chapters_returns_valid_epub(self) -> None:
        result = format_epub([])
        assert isinstance(result, bytes)
        assert zipfile.is_zipfile(io.BytesIO(result))

    def test_epub_contains_mimetype(self) -> None:
        result = format_epub([make_chapter(1, ["测试"])])
        names = get_epub_names(result)
        assert "mimetype" in names

    def test_epub_contains_css(self) -> None:
        result = format_epub([make_chapter(1, ["测试"])])
        names = get_epub_names(result)
        assert any("default.css" in n for n in names)

    def test_css_content_present(self) -> None:
        result = format_epub([make_chapter(1, ["测试"])])
        css = read_epub_file(result, "EPUB/style/default.css")
        assert "font-family" in css
        assert "line-height" in css

    def test_custom_css_used(self) -> None:
        custom = "body { color: red; }"
        result = format_epub([make_chapter(1, ["测试"])], epub_css=custom)
        css = read_epub_file(result, "EPUB/style/default.css")
        assert "color: red" in css


# ---------------------------------------------------------------------------
# Chapter content
# ---------------------------------------------------------------------------

class TestChapterContent:
    def test_chapter_file_present(self) -> None:
        result = format_epub([make_chapter(1, ["第一章内容"])])
        names = get_epub_names(result)
        assert any("chapter_0001.xhtml" in n for n in names)

    def test_chapter_file_zero_padded(self) -> None:
        result = format_epub([make_chapter(5, ["内容"])])
        names = get_epub_names(result)
        assert any("chapter_0005.xhtml" in n for n in names)

    def test_chapter_text_in_html(self) -> None:
        result = format_epub([make_chapter(1, ["你好世界"])])
        html = read_epub_file(result, "EPUB/chapter_0001.xhtml")
        assert "你好世界" in html

    def test_multiple_results_all_present(self) -> None:
        result = format_epub([make_chapter(1, ["第一段", "第二段", "第三段"])])
        html = read_epub_file(result, "EPUB/chapter_0001.xhtml")
        assert "第一段" in html
        assert "第二段" in html
        assert "第三段" in html

    def test_multiline_result_uses_br(self) -> None:
        r = OCRResult(text="第一行\n第二行", confidence=0.9)
        chapter = Chapter(number=1, results=[r])
        result = format_epub([chapter])
        html = read_epub_file(result, "EPUB/chapter_0001.xhtml")
        assert "<br/>" in html
        assert "第一行" in html
        assert "第二行" in html

    def test_empty_result_text_skipped(self) -> None:
        r1 = OCRResult(text="  ", confidence=0.9)
        r2 = OCRResult(text="有内容", confidence=0.9)
        chapter = Chapter(number=1, results=[r1, r2])
        result = format_epub([chapter])
        html = read_epub_file(result, "EPUB/chapter_0001.xhtml")
        assert "有内容" in html

    def test_custom_title_used(self) -> None:
        chapter = Chapter(number=1, results=[], title="序章")
        result = format_epub([chapter])
        html = read_epub_file(result, "EPUB/chapter_0001.xhtml")
        assert "序章" in html

    def test_default_title_generated(self) -> None:
        chapter = Chapter(number=3, results=[])
        result = format_epub([chapter])
        html = read_epub_file(result, "EPUB/chapter_0003.xhtml")
        assert "第3章" in html


# ---------------------------------------------------------------------------
# P0: Numeric chapter ordering
# ---------------------------------------------------------------------------

class TestNumericOrdering:
    def test_chapters_ordered_numerically_not_lexicographically(self) -> None:
        """P0: chapters 1-11 must appear in order 1,2,...,10,11 in the spine."""
        chapters = [make_chapter(n, [f"第{n}章内容"]) for n in range(1, 12)]
        import random
        shuffled = chapters[:]
        random.shuffle(shuffled)
        result = format_epub(shuffled)

        names = get_epub_names(result)
        chapter_files = sorted(
            [n for n in names if "chapter_" in n and n.endswith(".xhtml")],
        )
        expected = [f"EPUB/chapter_{n:04d}.xhtml" for n in range(1, 12)]
        assert chapter_files == expected, (
            f"Chapter files not in numeric order.\n"
            f"Got: {chapter_files}\nExpected: {expected}"
        )

    def test_chapter_numbers_not_reordered_lexicographically(self) -> None:
        """Lexicographic sort would put 10 before 2 — verify this doesn't happen."""
        chapters = [
            make_chapter(2, ["第二章"]),
            make_chapter(10, ["第十章"]),
            make_chapter(1, ["第一章"]),
        ]
        result = format_epub(chapters)
        names = get_epub_names(result)
        chapter_files = sorted(
            [n for n in names if "chapter_" in n and n.endswith(".xhtml")]
        )
        assert chapter_files[0].endswith("chapter_0001.xhtml")
        assert chapter_files[1].endswith("chapter_0002.xhtml")
        assert chapter_files[2].endswith("chapter_0010.xhtml")

    def test_single_chapter_no_ordering_issue(self) -> None:
        result = format_epub([make_chapter(7, ["内容"])])
        names = get_epub_names(result)
        assert any("chapter_0007.xhtml" in n for n in names)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_custom_title_in_config(self) -> None:
        result = format_epub(
            [make_chapter(1, ["内容"])],
            epub_title="我的小说",
        )
        opf = read_epub_file(result, "EPUB/content.opf")
        assert "我的小说" in opf

    def test_custom_language(self) -> None:
        result = format_epub(
            [make_chapter(1, ["内容"])],
            epub_language="zh-TW",
        )
        opf = read_epub_file(result, "EPUB/content.opf")
        assert "zh-TW" in opf

    def test_custom_identifier(self) -> None:
        result = format_epub(
            [make_chapter(1, ["内容"])],
            epub_identifier="my-book-001",
        )
        opf = read_epub_file(result, "EPUB/content.opf")
        assert "my-book-001" in opf

    def test_default_language_is_zh_cn(self) -> None:
        result = format_epub([make_chapter(1, ["内容"])])
        opf = read_epub_file(result, "EPUB/content.opf")
        assert "zh-CN" in opf or "zh-cn" in opf.lower()


# ---------------------------------------------------------------------------
# _chapter_to_html_body()
# ---------------------------------------------------------------------------

class TestChapterToHtmlBody:
    def test_single_result(self) -> None:
        ch = make_chapter(1, ["你好"])
        body = EpubFormatter._chapter_to_html_body(ch)
        assert "<p>你好</p>" in body

    def test_multiple_results(self) -> None:
        ch = make_chapter(1, ["第一", "第二"])
        body = EpubFormatter._chapter_to_html_body(ch)
        assert "<p>第一</p>" in body
        assert "<p>第二</p>" in body

    def test_empty_chapter_produces_empty_p(self) -> None:
        ch = Chapter(number=1, results=[])
        body = EpubFormatter._chapter_to_html_body(ch)
        assert "<p></p>" in body

    def test_whitespace_only_result_skipped(self) -> None:
        r = OCRResult(text="   ", confidence=0.9)
        ch = Chapter(number=1, results=[r])
        body = EpubFormatter._chapter_to_html_body(ch)
        assert "<p></p>" in body

    def test_newline_in_result_becomes_br(self) -> None:
        r = OCRResult(text="行一\n行二", confidence=0.9)
        ch = Chapter(number=1, results=[r])
        body = EpubFormatter._chapter_to_html_body(ch)
        assert "行一<br/>行二" in body
