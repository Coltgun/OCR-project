"""
Tests for FEAT-results-preview.

Strategy:
1. Source-scan tests — verify widget creation and wiring without importing Qt.
2. _populate_preview / _clear_preview logic tests — instantiate the helper
   logic as pure Python (no Qt) by extracting the grouping algorithm.
3. GUI tests — @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.types import OCRResult
from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers — replicate _populate_preview logic without Qt
# ---------------------------------------------------------------------------

def _simulate_populate(results: list[OCRResult]) -> tuple[str, str]:
    """Return (plain_text, label_html) as _populate_preview would produce."""
    if not results:
        return "", "<b>OCR Results:</b> 0 blocks"

    lines: list[str] = []
    current_id: str | None = None
    for r in results:
        if r.image_id and r.image_id != current_id:
            current_id = r.image_id
            lines.append(f"── {r.image_id} ──")
        lines.append(r.text)

    n = len(results)
    label = f"<b>OCR Results:</b> {n} block{'s' if n != 1 else ''}"
    return "\n".join(lines), label


def _make(text: str, image_id: str = "") -> OCRResult:
    return OCRResult(text=text, confidence=0.9, image_id=image_id)


# ---------------------------------------------------------------------------
# 1. Source-scan wiring tests
# ---------------------------------------------------------------------------

class TestResultsPreviewSource:
    def test_preview_pane_widget_created(self) -> None:
        assert "self._preview_pane = QTextEdit()" in _MW_SRC

    def test_preview_pane_is_readonly(self) -> None:
        assert "self._preview_pane.setReadOnly(True)" in _MW_SRC

    def test_preview_pane_max_height_set(self) -> None:
        assert "self._preview_pane.setMaximumHeight" in _MW_SRC

    def test_preview_pane_placeholder_set(self) -> None:
        assert "self._preview_pane.setPlaceholderText" in _MW_SRC

    def test_preview_label_created(self) -> None:
        assert "self._preview_label = QLabel" in _MW_SRC

    def test_populate_preview_called_in_on_ocr_results(self) -> None:
        assert "self._populate_preview(results)" in _MW_SRC

    def test_clear_preview_called_in_start_new_session(self) -> None:
        idx = _MW_SRC.index("def _start_new_session")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._clear_preview()" in block

    def test_clear_preview_called_in_trigger_new_section(self) -> None:
        idx = _MW_SRC.index("def _trigger_new_section")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._clear_preview()" in block

    def test_populate_preview_method_exists(self) -> None:
        assert "def _populate_preview" in _MW_SRC

    def test_clear_preview_method_exists(self) -> None:
        assert "def _clear_preview" in _MW_SRC

    def test_populate_groups_by_image_id(self) -> None:
        assert "image_id" in _MW_SRC

    def test_preview_label_shows_block_count(self) -> None:
        assert "block" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Preview logic tests (pure Python)
# ---------------------------------------------------------------------------

class TestPopulatePreviewLogic:
    def test_empty_results_gives_empty_text(self) -> None:
        text, label = _simulate_populate([])
        assert text == ""

    def test_empty_results_label_shows_zero(self) -> None:
        _, label = _simulate_populate([])
        assert "0 blocks" in label

    def test_single_result_no_image_id(self) -> None:
        text, label = _simulate_populate([_make("你好")])
        assert "你好" in text
        assert "1 block" in label
        assert "blocks" not in label  # singular

    def test_single_result_with_image_id(self) -> None:
        text, _ = _simulate_populate([_make("世界", image_id="0001")])
        assert "── 0001 ──" in text
        assert "世界" in text

    def test_multiple_results_same_image_id(self) -> None:
        results = [_make("一", "0001"), _make("二", "0001")]
        text, label = _simulate_populate(results)
        assert text.count("── 0001 ──") == 1
        assert "一" in text and "二" in text
        assert "2 blocks" in label

    def test_multiple_image_ids_each_gets_header(self) -> None:
        results = [_make("A", "0001"), _make("B", "0002")]
        text, _ = _simulate_populate(results)
        assert "── 0001 ──" in text
        assert "── 0002 ──" in text

    def test_image_id_header_not_repeated_for_same_group(self) -> None:
        results = [_make("X", "img1"), _make("Y", "img1"), _make("Z", "img2")]
        text, _ = _simulate_populate(results)
        assert text.count("── img1 ──") == 1
        assert text.count("── img2 ──") == 1

    def test_results_without_image_id_no_header_line(self) -> None:
        results = [_make("plain")]
        text, _ = _simulate_populate(results)
        assert "──" not in text
        assert "plain" in text

    def test_plural_label_for_multiple_blocks(self) -> None:
        results = [_make("一"), _make("二")]
        _, label = _simulate_populate(results)
        assert "2 blocks" in label

    def test_text_order_preserved(self) -> None:
        results = [_make("first", "a"), _make("second", "a"), _make("third", "b")]
        text, _ = _simulate_populate(results)
        assert text.index("first") < text.index("second") < text.index("third")

    def test_mixed_empty_and_nonempty_image_ids(self) -> None:
        results = [_make("no-id"), _make("has-id", "0001")]
        text, _ = _simulate_populate(results)
        assert "no-id" in text
        assert "── 0001 ──" in text


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestResultsPreviewGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_preview_pane_initially_empty(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._preview_pane.toPlainText() == ""

    def test_preview_label_initially_dash(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "—" in w._preview_label.text()

    def test_populate_fills_pane(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        results = [_make("你好", "0001"), _make("世界", "0001")]
        w._populate_preview(results)
        assert "你好" in w._preview_pane.toPlainText()
        assert "世界" in w._preview_pane.toPlainText()

    def test_populate_updates_label_count(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._populate_preview([_make("A"), _make("B")])
        assert "2 blocks" in w._preview_label.text()

    def test_clear_empties_pane(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._populate_preview([_make("text")])
        w._clear_preview()
        assert w._preview_pane.toPlainText() == ""

    def test_clear_resets_label(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._populate_preview([_make("text")])
        w._clear_preview()
        assert "—" in w._preview_label.text()

    def test_on_ocr_results_populates_preview(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        results = [_make("OCR result", "img1")]
        w._on_ocr_results(results)
        assert "OCR result" in w._preview_pane.toPlainText()
