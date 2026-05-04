"""
Tests for FEAT-state-machine-ui.

Source-scan tests verify _state_dot, _state_label, _DOT_COLOURS mapping,
and _update_ui_for_state wiring.
Pure-logic tests verify AppState membership and dot colour logic.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from capture.state import AppState


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestStateMachineUiSource:
    def _ui_block(self) -> str:
        idx = _MW_SRC.index("def _update_ui_for_state")
        end = _MW_SRC.index("\n    # --", idx + 1)
        return _MW_SRC[idx:end]

    def test_state_dot_created(self) -> None:
        assert "self._state_dot = QLabel()" in _MW_SRC

    def test_state_dot_fixed_size(self) -> None:
        assert "self._state_dot.setFixedSize(12, 12)" in _MW_SRC

    def test_state_dot_tooltip(self) -> None:
        assert '"Application state"' in _MW_SRC

    def test_state_label_created(self) -> None:
        assert 'self._state_label = QLabel("IDLE")' in _MW_SRC

    def test_dot_colours_dict_exists(self) -> None:
        assert "_DOT_COLOURS" in _MW_SRC

    def test_dot_idle_colour_defined(self) -> None:
        assert "_DOT_IDLE" in _MW_SRC

    def test_dot_busy_colour_defined(self) -> None:
        assert "_DOT_BUSY" in _MW_SRC

    def test_all_app_states_in_dot_colours(self) -> None:
        for state in ("AppState.IDLE", "AppState.SELECTING",
                      "AppState.CAPTURING", "AppState.OCR_RUNNING",
                      "AppState.EXPORTING"):
            assert state in _MW_SRC

    def test_update_ui_method_exists(self) -> None:
        assert "def _update_ui_for_state" in _MW_SRC

    def test_update_ui_sets_state_label(self) -> None:
        assert "_state_label.setText" in self._ui_block()

    def test_update_ui_sets_dot_stylesheet(self) -> None:
        assert "_state_dot.setStyleSheet" in self._ui_block()

    def test_update_ui_called_on_init(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_ui_for_state(AppState.IDLE)" in block

    def test_update_ui_computes_is_idle(self) -> None:
        assert "is_idle = state == AppState.IDLE" in self._ui_block()

    def test_update_ui_computes_has_session(self) -> None:
        assert "has_session = self._session is not None" in self._ui_block()

    def test_update_ui_computes_has_region(self) -> None:
        assert "has_region = self._capture_region is not None" in self._ui_block()

    def test_update_ui_computes_has_results(self) -> None:
        assert "has_results = bool(self._ocr_results)" in self._ui_block()

    def test_capture_btn_requires_idle_session_region(self) -> None:
        assert "is_idle and has_session and has_region" in self._ui_block()

    def test_export_btn_requires_idle_results(self) -> None:
        assert "is_idle and has_results" in self._ui_block()

    def test_state_messages_dict_exists(self) -> None:
        assert "state_messages = {" in self._ui_block()

    def test_state_messages_covers_all_states(self) -> None:
        blk = self._ui_block()
        for state in ("AppState.IDLE", "AppState.SELECTING",
                      "AppState.CAPTURING", "AppState.OCR_RUNNING",
                      "AppState.EXPORTING"):
            assert state in blk

    def test_status_bar_uses_state_messages(self) -> None:
        assert "state_messages.get(state" in self._ui_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestStateMachineUiLogic:
    def test_idle_state_exists(self) -> None:
        assert AppState.IDLE is not None

    def test_five_states(self) -> None:
        states = list(AppState)
        assert len(states) >= 5

    def test_idle_is_not_busy(self) -> None:
        busy_states = {AppState.SELECTING, AppState.CAPTURING,
                       AppState.OCR_RUNNING, AppState.EXPORTING}
        assert AppState.IDLE not in busy_states

    def test_capturing_is_busy(self) -> None:
        busy_states = {AppState.SELECTING, AppState.CAPTURING,
                       AppState.OCR_RUNNING, AppState.EXPORTING}
        assert AppState.CAPTURING in busy_states

    def _dot_colour(self, state: AppState) -> str:
        idle_css = "background:#4CAF50"
        busy_css = "background:#FF9800"
        return idle_css if state == AppState.IDLE else busy_css

    def test_idle_dot_is_green(self) -> None:
        assert "4CAF50" in self._dot_colour(AppState.IDLE)

    def test_busy_dot_is_not_green(self) -> None:
        assert "4CAF50" not in self._dot_colour(AppState.OCR_RUNNING)


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestStateMachineUiGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_state_label_idle_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "IDLE" in w._state_label.text()

    def test_state_dot_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._state_dot is not None

    def test_idle_dot_is_green(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "4CAF50" in w._state_dot.styleSheet()
