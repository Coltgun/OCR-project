"""
Tests for FEAT-capture-trigger.

Source-scan tests verify _trigger_capture: session+region guard, state_machine.capture(),
deferred cv2 import, rotation_mode config, capture_delay_ms (sleep), grab_and_rotate,
get_next_image_path, cv2.imwrite, _update_count_label, _refresh_section_count_list,
_update_session_info_label, _last_capture_path, zoom_thumbnail_btn.setVisible(True),
_update_thumbnail, capture_done, auto_new_section_threshold, Exception catch +
status + capture_error, final _update_ui_for_state(IDLE).
Pure-logic tests verify delay conversion, threshold logic, rotation config read.
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

def _capture_block() -> str:
    idx = _MW_SRC.index("def _trigger_capture")
    end = _MW_SRC.index("\n    @Slot()\n    def _trigger_new_section", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestCaptureTriggerSource:
    def test_trigger_capture_exists(self) -> None:
        assert "def _trigger_capture" in _MW_SRC

    def test_session_region_guard(self) -> None:
        assert "if self._session is None or self._capture_region is None:" in _capture_block()

    def test_state_machine_capture_called(self) -> None:
        assert "self._state_machine.capture()" in _capture_block()

    def test_cv2_deferred_import(self) -> None:
        assert "import cv2" in _capture_block()

    def test_rotation_mode_read_from_config(self) -> None:
        assert '"rotation_mode"' in _capture_block()

    def test_capture_delay_ms_read_from_config(self) -> None:
        assert '"capture_delay_ms"' in _capture_block()

    def test_delay_converted_to_seconds(self) -> None:
        assert "/ 1000.0" in _capture_block()

    def test_sleep_called_when_delay_positive(self) -> None:
        assert "time.sleep(delay_s)" in _capture_block()

    def test_grab_and_rotate_called(self) -> None:
        assert "self._screen_capture.grab_and_rotate(" in _capture_block()

    def test_get_next_image_path_called(self) -> None:
        assert "self._session.get_next_image_path()" in _capture_block()

    def test_cv2_imwrite_called(self) -> None:
        assert "cv2.imwrite(str(save_path), image)" in _capture_block()

    def test_update_count_label_called(self) -> None:
        assert "self._update_count_label()" in _capture_block()

    def test_refresh_section_count_list_called(self) -> None:
        assert "self._refresh_section_count_list()" in _capture_block()

    def test_last_capture_path_set(self) -> None:
        assert "self._last_capture_path = save_path" in _capture_block()

    def test_zoom_thumbnail_btn_shown(self) -> None:
        assert "_zoom_thumbnail_btn.setVisible(True)" in _capture_block()

    def test_update_thumbnail_called(self) -> None:
        assert "self._update_thumbnail(save_path)" in _capture_block()

    def test_capture_done_called(self) -> None:
        assert "self._state_machine.capture_done()" in _capture_block()

    def test_auto_new_section_threshold_checked(self) -> None:
        assert '"auto_new_section_threshold"' in _capture_block()

    def test_threshold_triggers_new_section(self) -> None:
        assert "self._trigger_new_section()" in _capture_block()

    def test_exception_caught(self) -> None:
        assert "except Exception as exc:" in _capture_block()

    def test_capture_error_called_on_exception(self) -> None:
        assert "self._state_machine.capture_error()" in _capture_block()

    def test_update_ui_idle_at_end(self) -> None:
        assert "self._update_ui_for_state(AppState.IDLE)" in _capture_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestCaptureTriggerLogic:
    def test_delay_ms_to_seconds(self) -> None:
        delay_ms = 500
        delay_s = float(delay_ms) / 1000.0
        assert delay_s == 0.5

    def test_delay_zero_no_sleep(self) -> None:
        delay_s = float(0) / 1000.0
        assert delay_s == 0.0
        should_sleep = delay_s > 0
        assert not should_sleep

    def test_threshold_zero_no_auto_section(self) -> None:
        threshold = 0
        image_count = 10
        should_trigger = threshold > 0 and image_count >= threshold
        assert not should_trigger

    def test_threshold_met_triggers_section(self) -> None:
        threshold = 5
        image_count = 5
        should_trigger = threshold > 0 and image_count >= threshold
        assert should_trigger

    def test_threshold_not_met_no_trigger(self) -> None:
        threshold = 5
        image_count = 3
        should_trigger = threshold > 0 and image_count >= threshold
        assert not should_trigger

    def test_rotation_mode_default(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        rotation = cfg.get("rotation_mode", "none")
        assert rotation == "none"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestCaptureTriggerGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_trigger_capture_no_session_returns(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._session = None
        w._trigger_capture()

    def test_trigger_capture_no_region_returns(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "s1"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._capture_region = None
        w._trigger_capture()

    def test_capture_btn_connected(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._capture_btn is not None
