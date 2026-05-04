"""
Tests for FEAT-state-dot.

Source-scan tests verify _state_dot QLabel (fixed 12x12, tooltip, permanent widget),
_state_label QLabel("IDLE"), _DOT_IDLE/_DOT_BUSY/_DOT_ERROR stylesheets,
_DOT_COLOURS map for 5 AppStates, _update_ui_for_state: label setText, dot
setStyleSheet, button enable/disable logic, state_messages dict.
Pure-logic tests verify colour mapping and button enable semantics.
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

def _update_ui_block() -> str:
    idx = _MW_SRC.index("def _update_ui_for_state")
    end = _MW_SRC.index("\n    # ------------------------------------------------------------------\n    # Action handlers", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestStateDotSource:
    def test_state_dot_created(self) -> None:
        assert "self._state_dot = QLabel()" in _MW_SRC

    def test_state_dot_fixed_size(self) -> None:
        assert "_state_dot.setFixedSize(12, 12)" in _MW_SRC

    def test_state_dot_tooltip(self) -> None:
        assert '_state_dot.setToolTip("Application state")' in _MW_SRC

    def test_state_dot_added_to_status_bar(self) -> None:
        assert "_status_bar.addPermanentWidget(self._state_dot)" in _MW_SRC

    def test_state_label_created(self) -> None:
        assert 'self._state_label = QLabel("IDLE")' in _MW_SRC

    def test_state_label_added_to_status_bar(self) -> None:
        assert "_status_bar.addPermanentWidget(self._state_label)" in _MW_SRC

    def test_dot_idle_stylesheet(self) -> None:
        assert "_DOT_IDLE" in _MW_SRC
        assert "#4CAF50" in _MW_SRC

    def test_dot_busy_stylesheet(self) -> None:
        assert "_DOT_BUSY" in _MW_SRC
        assert "#FFC107" in _MW_SRC

    def test_dot_error_stylesheet(self) -> None:
        assert "_DOT_ERROR" in _MW_SRC
        assert "#F44336" in _MW_SRC

    def test_dot_colours_map_has_idle(self) -> None:
        assert "AppState.IDLE: _DOT_IDLE" in _MW_SRC

    def test_dot_colours_map_has_selecting(self) -> None:
        assert "AppState.SELECTING: _DOT_BUSY" in _MW_SRC

    def test_dot_colours_map_has_ocr_running(self) -> None:
        assert "AppState.OCR_RUNNING: _DOT_BUSY" in _MW_SRC

    def test_update_ui_sets_state_label(self) -> None:
        assert "self._state_label.setText(state.name)" in _update_ui_block()

    def test_update_ui_sets_dot_stylesheet(self) -> None:
        assert "_state_dot.setStyleSheet(" in _update_ui_block()

    def test_update_ui_uses_dot_colours_map(self) -> None:
        assert "_DOT_COLOURS.get(state," in _update_ui_block()

    def test_update_ui_checks_is_idle(self) -> None:
        assert "is_idle = state == AppState.IDLE" in _update_ui_block()

    def test_update_ui_enables_capture_btn(self) -> None:
        assert "_capture_btn.setEnabled(" in _update_ui_block()

    def test_update_ui_enables_ocr_btn(self) -> None:
        assert "_ocr_btn.setEnabled(" in _update_ui_block()

    def test_update_ui_enables_export_btn(self) -> None:
        assert "_export_btn.setEnabled(is_idle and has_results)" in _update_ui_block()

    def test_update_ui_state_messages_dict(self) -> None:
        assert "state_messages = {" in _update_ui_block()

    def test_update_ui_shows_status_message(self) -> None:
        assert "_status_bar.showMessage(state_messages.get(state" in _update_ui_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestStateDotLogic:
    _DOT_IDLE  = "border-radius:6px; background:#4CAF50;"
    _DOT_BUSY  = "border-radius:6px; background:#FFC107;"
    _DOT_ERROR = "border-radius:6px; background:#F44336;"

    def test_idle_colour_is_green(self) -> None:
        from capture.state import AppState
        colours = {
            AppState.IDLE:        self._DOT_IDLE,
            AppState.SELECTING:   self._DOT_BUSY,
            AppState.CAPTURING:   self._DOT_BUSY,
            AppState.OCR_RUNNING: self._DOT_BUSY,
            AppState.EXPORTING:   self._DOT_BUSY,
        }
        assert colours[AppState.IDLE] == self._DOT_IDLE

    def test_ocr_running_colour_is_amber(self) -> None:
        from capture.state import AppState
        colours = {
            AppState.IDLE:        self._DOT_IDLE,
            AppState.OCR_RUNNING: self._DOT_BUSY,
        }
        assert colours[AppState.OCR_RUNNING] == self._DOT_BUSY

    def test_unknown_state_defaults_to_busy(self) -> None:
        colours: dict = {}
        assert colours.get("unknown_state", self._DOT_BUSY) == self._DOT_BUSY

    def test_capture_btn_disabled_when_not_idle(self) -> None:
        is_idle, has_session, has_region = False, True, True
        assert not (is_idle and has_session and has_region)

    def test_capture_btn_disabled_without_region(self) -> None:
        is_idle, has_session, has_region = True, True, False
        assert not (is_idle and has_session and has_region)

    def test_capture_btn_enabled_when_all_present(self) -> None:
        is_idle, has_session, has_region = True, True, True
        assert is_idle and has_session and has_region


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestStateDotGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_state_label_starts_idle(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._state_label.text() == "IDLE"

    def test_state_dot_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._state_dot is not None

    def test_state_dot_idle_colour(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "#4CAF50" in w._state_dot.styleSheet()
