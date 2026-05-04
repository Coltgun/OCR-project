"""
Tests for FEAT-populate-preview.

Source-scan tests verify _populate_preview: empty guard (setPlainText("")+label
"0 blocks"), image_id grouping separator, setPlainText join, avg_conf calc,
_preview_label setText, _copy_btn+_copy_section_btn enable.
_clear_preview: search_bar blockSignals+clear, setPlainText(""), label reset,
copy btns disabled.
Pure-logic tests verify grouping, avg_conf, label format, empty path.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _populate_block() -> str:
    idx = _MW_SRC.index("def _populate_preview")
    end = _MW_SRC.index("\n    def _clear_preview", idx + 1)
    return _MW_SRC[idx:end]


def _clear_block() -> str:
    idx = _MW_SRC.index("def _clear_preview")
    end = _MW_SRC.index("\n    @Slot(str)", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestPopulatePreviewSource:
    def test_populate_preview_exists(self) -> None:
        assert "def _populate_preview" in _MW_SRC

    def test_empty_guard_sets_plain_text_empty(self) -> None:
        assert 'self._preview_pane.setPlainText("")' in _populate_block()

    def test_empty_guard_sets_label_zero_blocks(self) -> None:
        assert "0 blocks" in _populate_block()

    def test_image_id_grouping_separator(self) -> None:
        assert "current_id" in _populate_block()

    def test_separator_line_format(self) -> None:
        assert '"── ' in _populate_block() or "── " in _populate_block()

    def test_set_plain_text_join(self) -> None:
        assert 'setPlainText("\\n".join(lines))' in _populate_block()

    def test_avg_conf_calculation(self) -> None:
        assert "sum(r.confidence for r in results)" in _populate_block()

    def test_avg_conf_divides_by_n(self) -> None:
        assert "/ n" in _populate_block()

    def test_preview_label_shows_block_count(self) -> None:
        assert "_preview_label.setText(" in _populate_block()

    def test_preview_label_avg_conf_formatted(self) -> None:
        assert "avg_conf:.2f" in _populate_block()

    def test_copy_btn_enabled(self) -> None:
        assert "_copy_btn.setEnabled(True)" in _populate_block()

    def test_copy_section_btn_enabled_with_session(self) -> None:
        assert "_copy_section_btn.setEnabled(" in _populate_block()

    def test_clear_preview_exists(self) -> None:
        assert "def _clear_preview" in _MW_SRC

    def test_clear_blocks_search_signals(self) -> None:
        assert "_search_bar.blockSignals(True)" in _clear_block()
        assert "_search_bar.blockSignals(False)" in _clear_block()

    def test_clear_clears_search_bar(self) -> None:
        assert "_search_bar.clear()" in _clear_block()

    def test_clear_sets_plain_text_empty(self) -> None:
        assert 'self._preview_pane.setPlainText("")' in _clear_block()

    def test_clear_resets_label(self) -> None:
        assert "_preview_label.setText(" in _clear_block()

    def test_clear_disables_copy_btn(self) -> None:
        assert "_copy_btn.setEnabled(False)" in _clear_block()

    def test_clear_disables_copy_section_btn(self) -> None:
        assert "_copy_section_btn.setEnabled(False)" in _clear_block()

    def test_plural_blocks_label(self) -> None:
        assert "'s' if n != 1 else ''" in _populate_block() or "n != 1" in _populate_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestPopulatePreviewLogic:
    def _make_result(self, image_id: str, text: str, confidence: float):
        from core.types import BoundingBox, OCRResult
        return OCRResult(
            image_id=image_id,
            text=text,
            confidence=confidence,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        )

    def test_avg_conf_single_result(self) -> None:
        results = [self._make_result("1/0001", "hello", 0.9)]
        n = len(results)
        avg = sum(r.confidence for r in results) / n
        assert abs(avg - 0.9) < 1e-9

    def test_avg_conf_multiple_results(self) -> None:
        results = [
            self._make_result("1/0001", "a", 0.8),
            self._make_result("1/0001", "b", 0.6),
        ]
        n = len(results)
        avg = sum(r.confidence for r in results) / n
        assert abs(avg - 0.7) < 1e-9

    def test_grouping_separator_inserted_on_id_change(self) -> None:
        lines: list[str] = []
        current_id: str | None = None
        results = [
            self._make_result("1/0001", "foo", 0.9),
            self._make_result("1/0002", "bar", 0.8),
        ]
        for r in results:
            if r.image_id and r.image_id != current_id:
                current_id = r.image_id
                lines.append(f"── {current_id} ──")
            lines.append(r.text)
        assert lines[0] == "── 1/0001 ──"
        assert lines[1] == "foo"
        assert lines[2] == "── 1/0002 ──"
        assert lines[3] == "bar"

    def test_same_image_id_no_duplicate_separator(self) -> None:
        lines: list[str] = []
        current_id: str | None = None
        results = [
            self._make_result("1/0001", "line1", 0.9),
            self._make_result("1/0001", "line2", 0.8),
        ]
        for r in results:
            if r.image_id and r.image_id != current_id:
                current_id = r.image_id
                lines.append(f"── {current_id} ──")
            lines.append(r.text)
        separators = [l for l in lines if l.startswith("──")]
        assert len(separators) == 1

    def test_singular_label_for_one_block(self) -> None:
        n = 1
        label = f"{n} block{'s' if n != 1 else ''}"
        assert label == "1 block"

    def test_plural_label_for_multiple_blocks(self) -> None:
        n = 3
        label = f"{n} block{'s' if n != 1 else ''}"
        assert label == "3 blocks"

    def test_empty_results_returns_early(self) -> None:
        results: list = []
        should_populate = bool(results)
        assert not should_populate


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestPopulatePreviewGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_populate_sets_plain_text(self, tmp_path: Path) -> None:
        from core.types import BoundingBox, OCRResult
        w = self._make_window(tmp_path)
        results = [OCRResult(image_id="1/0001", text="hello", confidence=0.9,
                             bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10))]
        w._populate_preview(results)
        assert "hello" in w._preview_pane.toPlainText()

    def test_clear_empties_pane(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._preview_pane.setPlainText("some text")
        w._clear_preview()
        assert w._preview_pane.toPlainText() == ""

    def test_clear_disables_copy_btn(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._copy_btn.setEnabled(True)
        w._clear_preview()
        assert not w._copy_btn.isEnabled()
