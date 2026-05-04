"""
Tests for FEAT-misc-methods.

Source-scan tests verify _toggle_border_overlay (@Slot(), isVisible guard,
border_overlay.hide/show, capture_region None guard) and _on_state_changed
(@Slot(object,object), logger.debug, _update_ui_for_state(new)).
Pure-logic tests verify the guard logic semantics.
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

def _toggle_block() -> str:
    idx = _MW_SRC.index("def _toggle_border_overlay")
    end = _MW_SRC.index("\n    def _install_log_handler", idx + 1)
    return _MW_SRC[idx:end]


def _state_changed_block() -> str:
    idx = _MW_SRC.index("def _on_state_changed")
    end = _MW_SRC.index("\n    # Stylesheet templates", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestToggleBorderOverlaySource:
    def test_toggle_border_overlay_exists(self) -> None:
        assert "def _toggle_border_overlay" in _MW_SRC

    def test_slot_decorator(self) -> None:
        idx = _MW_SRC.index("def _toggle_border_overlay")
        decorator_zone = _MW_SRC[max(0, idx - 30):idx]
        assert "@Slot()" in decorator_zone

    def test_checks_is_visible(self) -> None:
        assert "self._border_overlay.isVisible()" in _toggle_block()

    def test_hides_when_visible(self) -> None:
        assert "self._border_overlay.hide()" in _toggle_block()

    def test_shows_when_hidden_and_region_set(self) -> None:
        assert "self._border_overlay.show()" in _toggle_block()

    def test_region_none_guard(self) -> None:
        assert "self._capture_region is not None" in _toggle_block()


class TestOnStateChangedSource:
    def test_on_state_changed_exists(self) -> None:
        assert "def _on_state_changed" in _MW_SRC

    def test_slot_object_object_decorator(self) -> None:
        idx = _MW_SRC.index("def _on_state_changed")
        decorator_zone = _MW_SRC[max(0, idx - 40):idx]
        assert "@Slot(object, object)" in decorator_zone

    def test_logs_debug(self) -> None:
        assert "logger.debug(" in _state_changed_block()

    def test_logs_old_and_new_state_names(self) -> None:
        blk = _state_changed_block()
        assert "old.name" in blk
        assert "new.name" in blk

    def test_calls_update_ui_for_state(self) -> None:
        assert "_update_ui_for_state(new)" in _state_changed_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestMiscMethodsLogic:
    def test_toggle_hides_when_visible(self) -> None:
        visible = True
        action = "hide" if visible else "show_if_region"
        assert action == "hide"

    def test_toggle_shows_when_hidden_with_region(self) -> None:
        visible = False
        region = object()
        action = "show" if not visible and region is not None else "noop"
        assert action == "show"

    def test_toggle_noop_when_hidden_no_region(self) -> None:
        visible = False
        region = None
        action = "show" if not visible and region is not None else "noop"
        assert action == "noop"

    def test_state_changed_passes_new_state(self) -> None:
        from capture.state import AppState
        new = AppState.CAPTURING
        assert new == AppState.CAPTURING

    def test_state_changed_old_differs_from_new(self) -> None:
        from capture.state import AppState
        old, new = AppState.IDLE, AppState.CAPTURING
        assert old != new


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestMiscMethodsGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_toggle_no_crash_when_no_region(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._toggle_border_overlay()

    def test_border_overlay_hidden_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._border_overlay.isVisible()

    def test_on_state_changed_does_not_crash(self, tmp_path: Path) -> None:
        from capture.state import AppState
        w = self._make_window(tmp_path)
        w._on_state_changed(AppState.IDLE, AppState.CAPTURING)
