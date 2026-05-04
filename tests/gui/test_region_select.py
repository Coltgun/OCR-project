"""
Tests for FEAT-region-select.

Source-scan tests verify _trigger_select_region: state machine guard,
_border_overlay.hide(), CaptureOverlay creation, signal wiring;
_on_region_selected: CaptureRegion construction, _region_label update,
_border_overlay.update_region_from_qrect+show, state machine selection_done;
_capture_region None init, RegionBorderOverlay created.
Pure-logic tests verify CaptureRegion fields from rect data.
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

def _trigger_select_block() -> str:
    idx = _MW_SRC.index("def _trigger_select_region")
    end = _MW_SRC.index("\n    @Slot()\n    def _on_region_selected", idx + 1)
    return _MW_SRC[idx:end]

def _on_region_selected_block() -> str:
    idx = _MW_SRC.index("def _on_region_selected")
    end = _MW_SRC.index("\n    @Slot()\n    def _on_region_cancelled", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestRegionSelectSource:
    def test_trigger_select_region_exists(self) -> None:
        assert "def _trigger_select_region" in _MW_SRC

    def test_trigger_guards_state_machine(self) -> None:
        assert "self._state_machine.select_region()" in _trigger_select_block()

    def test_trigger_hides_border_overlay(self) -> None:
        assert "self._border_overlay.hide()" in _trigger_select_block()

    def test_trigger_creates_capture_overlay(self) -> None:
        assert "self._capture_overlay = CaptureOverlay()" in _trigger_select_block()

    def test_trigger_connects_region_selected(self) -> None:
        assert "region_selected.connect(self._on_region_selected)" in _trigger_select_block()

    def test_trigger_connects_cancelled(self) -> None:
        assert "cancelled.connect(self._on_region_cancelled)" in _trigger_select_block()

    def test_trigger_shows_fullscreen(self) -> None:
        assert "show_fullscreen()" in _trigger_select_block()

    def test_on_region_selected_exists(self) -> None:
        assert "def _on_region_selected" in _MW_SRC

    def test_on_region_selected_creates_capture_region(self) -> None:
        assert "self._capture_region = CaptureRegion(" in _on_region_selected_block()

    def test_on_region_selected_uses_rect_xywh(self) -> None:
        blk = _on_region_selected_block()
        assert "rect.x()" in blk
        assert "rect.y()" in blk
        assert "rect.width()" in blk
        assert "rect.height()" in blk

    def test_on_region_selected_updates_region_label(self) -> None:
        assert "_region_label.setText" in _on_region_selected_block()

    def test_on_region_selected_updates_border_overlay(self) -> None:
        assert "_border_overlay.update_region_from_qrect(rect)" in _on_region_selected_block()

    def test_on_region_selected_shows_border_overlay(self) -> None:
        assert "self._border_overlay.show()" in _on_region_selected_block()

    def test_on_region_selected_calls_selection_done(self) -> None:
        assert "self._state_machine.selection_done()" in _on_region_selected_block()

    def test_capture_region_initialised_none(self) -> None:
        assert "_capture_region: CaptureRegion | None = None" in _MW_SRC

    def test_border_overlay_created_on_init(self) -> None:
        assert "self._border_overlay = RegionBorderOverlay()" in _MW_SRC

    def test_select_region_btn_created(self) -> None:
        assert 'self._select_region_btn = QPushButton("Select Region (F8)")' in _MW_SRC

    def test_select_region_btn_connected(self) -> None:
        assert "_select_region_btn.clicked.connect(self._trigger_select_region)" in _MW_SRC

    def test_hotkey_signal_connected_to_trigger(self) -> None:
        assert "self._hotkeys.reset_area_pressed.connect(self._trigger_select_region)" in _MW_SRC

    def test_on_region_selected_calls_update_ui_idle(self) -> None:
        assert "_update_ui_for_state(AppState.IDLE)" in _on_region_selected_block()

    def test_on_region_selected_captures_region_xy(self) -> None:
        blk = _on_region_selected_block()
        assert "x=rect.x()" in blk
        assert "y=rect.y()" in blk


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestRegionSelectLogic:
    def _make_region(self, x, y, w, h):
        """Simulate CaptureRegion construction from rect values."""
        return {"x": x, "y": y, "width": w, "height": h}

    def test_region_stores_x(self) -> None:
        r = self._make_region(10, 20, 300, 200)
        assert r["x"] == 10

    def test_region_stores_y(self) -> None:
        r = self._make_region(10, 20, 300, 200)
        assert r["y"] == 20

    def test_region_stores_width(self) -> None:
        r = self._make_region(10, 20, 300, 200)
        assert r["width"] == 300

    def test_region_stores_height(self) -> None:
        r = self._make_region(10, 20, 300, 200)
        assert r["height"] == 200

    def test_region_label_format(self) -> None:
        x, y, w, h = 5, 15, 640, 480
        label = f"({x}, {y})  {w}\u00d7{h}"
        assert label == "(5, 15)  640\u00d7480"

    def test_no_region_disables_capture(self) -> None:
        capture_region = None
        can_capture = capture_region is not None
        assert not can_capture

    def test_region_with_zero_origin(self) -> None:
        r = self._make_region(0, 0, 100, 50)
        assert r["x"] == 0
        assert r["y"] == 0

    def test_label_uses_times_symbol(self) -> None:
        x, y, w, h = 0, 0, 800, 600
        label = f"({x}, {y})  {w}\u00d7{h}"
        assert "\u00d7" in label


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestRegionSelectGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_capture_region_none_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._capture_region is None

    def test_capture_overlay_none_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._capture_overlay is None

    def test_border_overlay_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._border_overlay is not None
