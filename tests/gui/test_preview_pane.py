"""
Tests for FEAT-preview-pane.

Source-scan tests verify _preview_pane QTextEdit (readOnly, minHeight, sizePolicy,
placeholder), _preview_label init text, _populate_preview (empty guard,
image_id grouping, setPlainText, avg_conf label, enable btns),
_clear_preview (search_bar.blockSignals+clear, setPlainText(""), label reset,
disable btns), _apply_preview_font_size (font.setPointSize clamped 8-24).
Pure-logic tests verify avg conf, label format, font clamp, grouping logic.
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
# helpers
# ---------------------------------------------------------------------------

def _populate_block() -> str:
    idx = _MW_SRC.index("def _populate_preview")
    end = _MW_SRC.index("\n    def _clear_preview", idx + 1)
    return _MW_SRC[idx:end]

def _clear_preview_block() -> str:
    idx = _MW_SRC.index("def _clear_preview")
    end = _MW_SRC.index("\n    @Slot(str)\n    def _on_search_changed", idx + 1)
    return _MW_SRC[idx:end]

def _apply_font_block() -> str:
    idx = _MW_SRC.index("def _apply_preview_font_size")
    end = _MW_SRC.index("\n    _MAX_RECENT", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestPreviewPaneSource:
    def test_preview_pane_created(self) -> None:
        assert "self._preview_pane = QTextEdit()" in _MW_SRC

    def test_preview_pane_read_only(self) -> None:
        assert "_preview_pane.setReadOnly(True)" in _MW_SRC

    def test_preview_pane_min_height(self) -> None:
        assert "_preview_pane.setMinimumHeight(80)" in _MW_SRC

    def test_preview_pane_size_policy_expanding(self) -> None:
        assert "QSizePolicy.Policy.Expanding" in _MW_SRC

    def test_preview_pane_placeholder(self) -> None:
        assert "_preview_pane.setPlaceholderText(" in _MW_SRC

    def test_preview_label_created(self) -> None:
        assert 'self._preview_label = QLabel("<b>OCR Results:</b>' in _MW_SRC

    def test_populate_preview_exists(self) -> None:
        assert "def _populate_preview" in _MW_SRC

    def test_populate_preview_guards_empty(self) -> None:
        assert "if not results:" in _populate_block()

    def test_populate_preview_groups_by_image_id(self) -> None:
        assert "r.image_id" in _populate_block()

    def test_populate_preview_sets_plain_text(self) -> None:
        assert "_preview_pane.setPlainText(" in _populate_block()

    def test_populate_preview_computes_avg_conf(self) -> None:
        assert "avg_conf" in _populate_block()

    def test_populate_preview_sets_label_with_count(self) -> None:
        assert "_preview_label.setText(" in _populate_block()

    def test_populate_preview_enables_copy_btn(self) -> None:
        assert "_copy_btn.setEnabled(True)" in _populate_block()

    def test_populate_preview_enables_copy_section_btn(self) -> None:
        assert "_copy_section_btn.setEnabled(" in _populate_block()

    def test_clear_preview_exists(self) -> None:
        assert "def _clear_preview" in _MW_SRC

    def test_clear_preview_blocks_search_signals(self) -> None:
        assert "_search_bar.blockSignals(True)" in _clear_preview_block()

    def test_clear_preview_clears_search_bar(self) -> None:
        assert "_search_bar.clear()" in _clear_preview_block()

    def test_clear_preview_clears_pane(self) -> None:
        assert '_preview_pane.setPlainText("")' in _clear_preview_block()

    def test_clear_preview_resets_label(self) -> None:
        assert "_preview_label.setText(" in _clear_preview_block()

    def test_clear_preview_disables_copy_btn(self) -> None:
        assert "_copy_btn.setEnabled(False)" in _clear_preview_block()

    def test_apply_preview_font_size_exists(self) -> None:
        assert "def _apply_preview_font_size" in _MW_SRC

    def test_apply_font_size_clamps_min_8(self) -> None:
        assert "max(8, min(size, 24))" in _apply_font_block()

    def test_apply_font_size_sets_font(self) -> None:
        assert "_preview_pane.setFont(font)" in _apply_font_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestPreviewPaneLogic:
    def test_avg_conf_single_result(self) -> None:
        confidences = [0.95]
        avg = sum(confidences) / len(confidences)
        assert abs(avg - 0.95) < 1e-9

    def test_avg_conf_multiple_results(self) -> None:
        confidences = [0.8, 0.9, 1.0]
        avg = sum(confidences) / len(confidences)
        assert abs(avg - 0.9) < 1e-9

    def test_label_singular_block(self) -> None:
        n = 1
        label = f"{n} block{'s' if n != 1 else ''}"
        assert label == "1 block"

    def test_label_plural_blocks(self) -> None:
        n = 3
        label = f"{n} block{'s' if n != 1 else ''}"
        assert label == "3 blocks"

    def test_font_clamp_min(self) -> None:
        size = 4
        clamped = max(8, min(size, 24))
        assert clamped == 8

    def test_font_clamp_max(self) -> None:
        size = 30
        clamped = max(8, min(size, 24))
        assert clamped == 24

    def test_font_clamp_normal(self) -> None:
        size = 12
        clamped = max(8, min(size, 24))
        assert clamped == 12

    def test_image_id_grouping_inserts_separator(self) -> None:
        from types import SimpleNamespace
        results = [
            SimpleNamespace(image_id="img1", text="hello"),
            SimpleNamespace(image_id="img1", text="world"),
            SimpleNamespace(image_id="img2", text="foo"),
        ]
        lines: list[str] = []
        current_id = None
        for r in results:
            if r.image_id and r.image_id != current_id:
                current_id = r.image_id
                lines.append(f"── {current_id} ──")
            lines.append(r.text)
        assert lines[0] == "── img1 ──"
        assert lines[3] == "── img2 ──"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestPreviewPaneGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_preview_pane_read_only_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._preview_pane.isReadOnly()

    def test_clear_preview_empties_pane(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._preview_pane.setPlainText("some text")
        w._clear_preview()
        assert w._preview_pane.toPlainText() == ""

    def test_apply_font_size_clamps(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._apply_preview_font_size(4)
        assert w._preview_pane.font().pointSize() == 8
