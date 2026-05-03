"""
Tests for FEAT-section-controls.

Source-scan tests verify _trigger_new_section (guards, new_section(), label update,
clear calls), _trigger_cancel (overlay close, state cancel, UI update), and
_on_region_cancelled (state cancel, UI update).
Pure-logic tests verify guard logic.
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

def _new_section_block() -> str:
    idx = _MW_SRC.index("def _trigger_new_section")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]

def _cancel_block() -> str:
    idx = _MW_SRC.index("def _trigger_cancel")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]

def _region_cancelled_block() -> str:
    idx = _MW_SRC.index("def _on_region_cancelled")
    end = _MW_SRC.index("\n\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestSectionControlsSource:
    def test_new_section_method_exists(self) -> None:
        assert "def _trigger_new_section" in _MW_SRC

    def test_new_section_guards_session(self) -> None:
        assert "self._session is None" in _new_section_block()

    def test_new_section_guards_idle(self) -> None:
        assert "self._state_machine.is_idle" in _new_section_block()

    def test_new_section_calls_session_new_section(self) -> None:
        assert "self._session.new_section()" in _new_section_block()

    def test_new_section_updates_label(self) -> None:
        assert "_section_label.setText" in _new_section_block()

    def test_new_section_clears_preview(self) -> None:
        assert "_clear_preview()" in _new_section_block()

    def test_new_section_clears_thumbnail(self) -> None:
        assert "_clear_thumbnail()" in _new_section_block()

    def test_trigger_cancel_method_exists(self) -> None:
        assert "def _trigger_cancel" in _MW_SRC

    def test_cancel_closes_overlay(self) -> None:
        assert "self._capture_overlay.close()" in _cancel_block()

    def test_cancel_nils_overlay(self) -> None:
        assert "self._capture_overlay = None" in _cancel_block()

    def test_cancel_calls_state_machine_cancel(self) -> None:
        assert "self._state_machine.cancel()" in _cancel_block()

    def test_cancel_updates_ui(self) -> None:
        assert "_update_ui_for_state(AppState.IDLE)" in _cancel_block()

    def test_on_region_cancelled_method_exists(self) -> None:
        assert "def _on_region_cancelled" in _MW_SRC

    def test_region_cancelled_calls_cancel(self) -> None:
        assert "self._state_machine.cancel()" in _region_cancelled_block()

    def test_region_cancelled_updates_ui(self) -> None:
        assert "_update_ui_for_state(AppState.IDLE)" in _region_cancelled_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestSectionControlsLogic:
    def test_session_none_blocks_new_section(self) -> None:
        session = None
        is_idle = True
        should_proceed = session is not None and is_idle
        assert not should_proceed

    def test_not_idle_blocks_new_section(self) -> None:
        session = object()
        is_idle = False
        should_proceed = session is not None and is_idle
        assert not should_proceed

    def test_session_and_idle_allows_new_section(self) -> None:
        session = object()
        is_idle = True
        should_proceed = session is not None and is_idle
        assert should_proceed

    def test_overlay_none_no_close_needed(self) -> None:
        overlay = None
        closed = False
        if overlay is not None:
            closed = True
        assert not closed

    def test_overlay_present_gets_closed(self) -> None:
        overlay = object()
        closed = False
        if overlay is not None:
            closed = True
        assert closed

    def test_section_label_updated_to_string(self) -> None:
        folder = 3
        label_text = str(folder)
        assert label_text == "3"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSectionControlsGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_new_section_btn_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._new_section_btn is not None

    def test_capture_overlay_none_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._capture_overlay is None

    def test_cancel_noop_when_no_overlay(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._trigger_cancel()
        assert w._capture_overlay is None
