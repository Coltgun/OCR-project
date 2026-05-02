"""
Tests for MarkdownFormatter (FEAT-markdown-formatter).

Source-scan tests for formatter + MainWindow wiring.
Unit tests for output correctness.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.types import Chapter, OCRResult
from output.markdown_formatter import MarkdownFormatter
from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
_MDF_SRC = (_ROOT / "output" / "markdown_formatter.py").read_text(encoding="utf-8")
_MW_SRC = (_ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan: MarkdownFormatter
# ---------------------------------------------------------------------------

class TestMarkdownFormatterSource:
    def test_registered_as_md(self) -> None:
        assert 'register_as="md"' in _MDF_SRC

    def test_subclasses_output_formatter(self) -> None:
        assert "OutputFormatter" in _MDF_SRC

    def test_format_method_defined(self) -> None:
        assert "def format" in _MDF_SRC

    def test_file_extension_returns_md(self) -> None:
        assert 'return "md"' in _MDF_SRC

    def test_encodes_utf8(self) -> None:
        assert 'encode("utf-8")' in _MDF_SRC

    def test_sorts_chapters_numerically(self) -> None:
        assert "sorted(chapters" in _MDF_SRC

    def test_uses_h2_heading(self) -> None:
        assert '"## Chapter' in _MDF_SRC


# ---------------------------------------------------------------------------
# 2. Source-scan: MainWindow wiring
# ---------------------------------------------------------------------------

class TestMarkdownFormatterMainWindowSource:
    def test_markdown_formatter_imported(self) -> None:
        assert "from output.markdown_formatter import MarkdownFormatter" in _MW_SRC

    def test_markdown_item_in_combo(self) -> None:
        assert '"Markdown"' in _MW_SRC and 'userData="md"' in _MW_SRC

    def test_formatter_map_includes_md(self) -> None:
        assert '"md": MarkdownFormatter' in _MW_SRC

    def test_filter_map_includes_md(self) -> None:
        assert '"md": "Markdown files (*.md)"' in _MW_SRC

    def test_title_map_includes_md(self) -> None:
        assert '"md": "Save Markdown"' in _MW_SRC


# ---------------------------------------------------------------------------
# 3. Unit tests
# ---------------------------------------------------------------------------

def _make_result(text: str) -> OCRResult:
    return OCRResult(text=text, confidence=1.0, bbox=(0, 0, 100, 20), image_id="img_0001")


def _make_chapter(number: int, texts: list[str]) -> Chapter:
    return Chapter(number=number, title=f"Chapter {number}", results=[_make_result(t) for t in texts])


class TestMarkdownFormatterUnit:
    def test_returns_bytes(self) -> None:
        assert isinstance(MarkdownFormatter().format([], {}), bytes)

    def test_file_extension_is_md(self) -> None:
        assert MarkdownFormatter().file_extension() == "md"

    def test_registered_in_registry(self) -> None:
        from output.base import OutputFormatter
        assert OutputFormatter.get("md") is MarkdownFormatter

    def test_h2_heading_present(self) -> None:
        ch = _make_chapter(1, ["line"])
        output = MarkdownFormatter().format([ch], {}).decode("utf-8")
        assert "## Chapter 1" in output

    def test_text_present(self) -> None:
        ch = _make_chapter(1, ["第一行"])
        output = MarkdownFormatter().format([ch], {}).decode("utf-8")
        assert "第一行" in output

    def test_numeric_chapter_order(self) -> None:
        chapters = [_make_chapter(3, ["c3"]), _make_chapter(1, ["c1"]), _make_chapter(2, ["c2"])]
        output = MarkdownFormatter().format(chapters, {}).decode("utf-8")
        assert output.index("c1") < output.index("c2") < output.index("c3")

    def test_empty_chapters_minimal_output(self) -> None:
        output = MarkdownFormatter().format([], {}).decode("utf-8").strip()
        assert output == ""

    def test_blank_line_between_results(self) -> None:
        ch = _make_chapter(1, ["first", "second"])
        output = MarkdownFormatter().format([ch], {}).decode("utf-8")
        lines = output.splitlines()
        first_idx = lines.index("first")
        assert lines[first_idx + 1] == ""

    def test_empty_result_text_excluded(self) -> None:
        ch = Chapter(number=1, title="ch1", results=[_make_result("")])
        output = MarkdownFormatter().format([ch], {}).decode("utf-8")
        content_lines = [l for l in output.splitlines() if l and not l.startswith("#")]
        assert content_lines == []

    def test_multi_chapter_two_headings(self) -> None:
        chapters = [_make_chapter(1, ["a"]), _make_chapter(2, ["b"])]
        output = MarkdownFormatter().format(chapters, {}).decode("utf-8")
        assert output.count("## Chapter") == 2

    def test_utf8_chinese_round_trip(self) -> None:
        ch = _make_chapter(1, ["汉字内容"])
        output = MarkdownFormatter().format([ch], {}).decode("utf-8")
        assert "汉字内容" in output

    def test_no_separator_lines(self) -> None:
        ch = _make_chapter(1, ["text"])
        output = MarkdownFormatter().format([ch], {}).decode("utf-8")
        assert "──" not in output


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestMarkdownFormatterGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_combo_has_three_items(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._export_fmt_combo.count() == 3

    def test_third_item_is_md(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._export_fmt_combo.setCurrentIndex(2)
        assert w._export_fmt_combo.currentData() == "md"
