"""
Tests for PlainTextFormatter (FEAT-export-formats).

Unit-tests for the formatter logic, source-scan for MainWindow wiring.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.types import Chapter, OCRResult
from output.plain_text_formatter import PlainTextFormatter
from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path helpers
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
_PTF_SRC = (_ROOT / "output" / "plain_text_formatter.py").read_text(encoding="utf-8")
_MW_SRC = (_ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan: PlainTextFormatter
# ---------------------------------------------------------------------------

class TestPlainTextFormatterSource:
    def test_registered_as_txt(self) -> None:
        assert 'register_as="txt"' in _PTF_SRC

    def test_subclasses_output_formatter(self) -> None:
        assert "OutputFormatter" in _PTF_SRC

    def test_format_method_defined(self) -> None:
        assert "def format" in _PTF_SRC

    def test_file_extension_returns_txt(self) -> None:
        assert 'return "txt"' in _PTF_SRC

    def test_encodes_utf8(self) -> None:
        assert 'encode("utf-8")' in _PTF_SRC

    def test_sorts_chapters_numerically(self) -> None:
        assert "sorted(chapters" in _PTF_SRC


# ---------------------------------------------------------------------------
# 2. Source-scan: MainWindow wiring
# ---------------------------------------------------------------------------

class TestExportFormatsMainWindowSource:
    def test_qcombobox_imported(self) -> None:
        assert "QComboBox" in _MW_SRC

    def test_plain_text_formatter_imported(self) -> None:
        assert "from output.plain_text_formatter import PlainTextFormatter" in _MW_SRC

    def test_export_fmt_combo_created(self) -> None:
        assert "self._export_fmt_combo = QComboBox()" in _MW_SRC

    def test_epub_item_added(self) -> None:
        assert '"EPUB"' in _MW_SRC and 'userData="epub"' in _MW_SRC

    def test_txt_item_added(self) -> None:
        assert '"Plain Text"' in _MW_SRC and 'userData="txt"' in _MW_SRC

    def test_dispatch_on_fmt(self) -> None:
        assert 'fmt = self._export_fmt_combo.currentData()' in _MW_SRC

    def test_epub_formatter_used_for_epub(self) -> None:
        assert "EpubFormatter() if is_epub else PlainTextFormatter()" in _MW_SRC

    def test_txt_extension_in_default_name(self) -> None:
        assert '"epub" if is_epub else "txt"' in _MW_SRC

    def test_file_filter_switches_by_format(self) -> None:
        assert '"EPUB files (*.epub)" if is_epub else "Text files (*.txt)"' in _MW_SRC

    def test_export_btn_text_updated(self) -> None:
        assert '"Export\u2026"' in _MW_SRC


# ---------------------------------------------------------------------------
# 3. Unit tests for PlainTextFormatter
# ---------------------------------------------------------------------------

def _make_result(text: str, image_id: str = "img_0001") -> OCRResult:
    return OCRResult(
        text=text,
        confidence=1.0,
        bbox=(0, 0, 100, 20),
        image_id=image_id,
    )


def _make_chapter(number: int, texts: list[str]) -> Chapter:
    return Chapter(
        number=number,
        title=f"Chapter {number}",
        results=[_make_result(t) for t in texts],
    )


class TestPlainTextFormatterUnit:
    def test_returns_bytes(self) -> None:
        fmt = PlainTextFormatter()
        result = fmt.format([], {})
        assert isinstance(result, bytes)

    def test_file_extension_is_txt(self) -> None:
        assert PlainTextFormatter().file_extension() == "txt"

    def test_registered_in_registry(self) -> None:
        from output.base import OutputFormatter
        assert OutputFormatter.get("txt") is PlainTextFormatter

    def test_single_chapter_text_present(self) -> None:
        ch = _make_chapter(1, ["第一行", "第二行"])
        output = PlainTextFormatter().format([ch], {}).decode("utf-8")
        assert "第一行" in output
        assert "第二行" in output

    def test_chapter_header_included(self) -> None:
        ch = _make_chapter(1, ["text"])
        output = PlainTextFormatter().format([ch], {}).decode("utf-8")
        assert "Chapter 1" in output

    def test_numeric_chapter_order(self) -> None:
        chapters = [_make_chapter(3, ["c3"]), _make_chapter(1, ["c1"]), _make_chapter(2, ["c2"])]
        output = PlainTextFormatter().format(chapters, {}).decode("utf-8")
        pos1 = output.index("c1")
        pos2 = output.index("c2")
        pos3 = output.index("c3")
        assert pos1 < pos2 < pos3

    def test_empty_chapters_produces_empty_output(self) -> None:
        output = PlainTextFormatter().format([], {}).decode("utf-8").strip()
        assert output == ""

    def test_multi_chapter_separators(self) -> None:
        chapters = [_make_chapter(1, ["a"]), _make_chapter(2, ["b"])]
        output = PlainTextFormatter().format(chapters, {}).decode("utf-8")
        assert output.count("Chapter") == 2

    def test_utf8_chinese_round_trip(self) -> None:
        ch = _make_chapter(1, ["汉字测试"])
        output = PlainTextFormatter().format([ch], {}).decode("utf-8")
        assert "汉字测试" in output

    def test_empty_result_text_excluded(self) -> None:
        ch = Chapter(number=1, title="ch1", results=[_make_result("")])
        output = PlainTextFormatter().format([ch], {}).decode("utf-8")
        lines = [l for l in output.splitlines() if l and "Chapter" not in l and "──" not in l]
        assert lines == []


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestExportFormatsGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_combo_has_two_items(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._export_fmt_combo.count() == 2

    def test_combo_default_is_epub(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._export_fmt_combo.currentData() == "epub"

    def test_combo_second_item_is_txt(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._export_fmt_combo.setCurrentIndex(1)
        assert w._export_fmt_combo.currentData() == "txt"
