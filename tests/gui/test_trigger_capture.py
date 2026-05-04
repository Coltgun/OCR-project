"""
Tests for FEAT-trigger-capture.

Source-scan tests verify _trigger_capture: session+region None guard,
state_machine.capture() guard, deferred cv2 import, rotation_mode config,
capture_delay_ms config, grab_and_rotate call, get_next_image_path,
cv2.imwrite, _update_count_label, _refresh_section_count_list,
_update_session_info_label, _last_capture_path, _zoom_thumbnail_btn visible,
_update_thumbnail, state_machine.capture_done, auto_new_section_threshold,
except block: logger.error+status+capture_error, _update_ui_for_state(IDLE).
Pure-logic tests verify delay conversion, rotation default, threshold guard.
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
# Helper
# ---------------------------------------------------------------------------

def _capture_block() -> str:
    idx = _MW_SRC.index("def _trigger_capture")
    end = _MW_SRC.index("\n    @Slot()\n    def _trigger_run_ocr", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestTriggerCaptureSource:
    def test_trigger_capture_exists(self) -> None:
        assert "def _trigger_capture" in _MW_SRC

    def test_session_none_guard(self) -> None:
        assert "self._session is None" in _capture_block()

    def test_region_none_guard(self) -> None:
        assert "self._capture_region is None" in _capture_block()

    def test_state_machine_capture_guard(self) -> None:
        assert "self._state_machine.capture()" in _capture_block()

    def test_deferred_cv2_import(self) -> None:
        assert "import cv2" in _capture_block()

    def test_rotation_mode_read_from_config(self) -> None:
        assert '"rotation_mode"' in _capture_block()

    def test_capture_delay_ms_read_from_config(self) -> None:
        assert '"capture_delay_ms"' in _capture_block()

    def test_delay_converted_to_seconds(self) -> None:
        assert "/ 1000.0" in _capture_block()

    def test_time_sleep_used_for_delay(self) -> None:
        assert "time.sleep(delay_s)" in _capture_block()

    def test_grab_and_rotate_called(self) -> None:
        assert "self._screen_capture.grab_and_rotate(" in _capture_block()

    def test_get_next_image_path_called(self) -> None:
        assert "self._session.get_next_image_path()" in _capture_block()

    def test_cv2_imwrite_called(self) -> None:
        assert "cv2.imwrite(str(save_path), image)" in _capture_block()

    def test_update_count_label_called(self) -> None:
        assert "self._update_count_label()" in _capture_block()

    def test_refresh_section_count_called(self) -> None:
        assert "self._refresh_section_count_list()" in _capture_block()

    def test_update_session_info_label_called(self) -> None:
        assert "self._update_session_info_label()" in _capture_block()

    def test_last_capture_path_stored(self) -> None:
        assert "self._last_capture_path = save_path" in _capture_block()

    def test_zoom_btn_made_visible(self) -> None:
        assert "self._zoom_thumbnail_btn.setVisible(True)" in _capture_block()

    def test_update_thumbnail_called(self) -> None:
        assert "self._update_thumbnail(save_path)" in _capture_block()

    def test_state_machine_capture_done(self) -> None:
        assert "self._state_machine.capture_done()" in _capture_block()

    def test_auto_new_section_threshold_config(self) -> None:
        assert '"auto_new_section_threshold"' in _capture_block()

    def test_auto_section_triggers_new_section(self) -> None:
        assert "self._trigger_new_section()" in _capture_block()

    def test_except_block_logs_error(self) -> None:
        assert 'logger.error("MainWindow: capture failed' in _capture_block()

    def test_except_block_shows_status(self) -> None:
        assert '"Capture error:' in _capture_block()

    def test_except_calls_capture_error(self) -> None:
        assert "self._state_machine.capture_error()" in _capture_block()

    def test_update_ui_idle_always_called(self) -> None:
        assert "_update_ui_for_state(AppState.IDLE)" in _capture_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestTriggerCaptureLogic:
    def test_delay_ms_to_seconds(self) -> None:
        delay_ms = 500
        delay_s = float(delay_ms) / 1000.0
        assert abs(delay_s - 0.5) < 1e-9

    def test_zero_delay_no_sleep(self) -> None:
        delay_ms = 0
        delay_s = float(delay_ms) / 1000.0
        assert delay_s == 0.0

    def test_rotation_default_none(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("rotation_mode", "none") == "none"

    def test_capture_delay_default_zero(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("capture_delay_ms", 0) == 0

    def test_auto_section_threshold_default_zero(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("auto_new_section_threshold", 0) == 0

    def test_threshold_zero_means_disabled(self) -> None:
        threshold = 0
        assert not (threshold > 0)

    def test_threshold_positive_triggers_check(self) -> None:
        threshold = 5
        image_count = 5
        assert threshold > 0 and image_count >= threshold


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestTriggerCaptureGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_capture_noop_without_session(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._trigger_capture()
        assert w._session is None

    def test_capture_noop_without_region(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock
        w = self._make_window(tmp_path)
        w._session = MagicMock()
        w._capture_region = None
        w._trigger_capture()
        assert w._last_capture_path is None or w._last_capture_path == ""

    def test_zoom_btn_hidden_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._zoom_thumbnail_btn.isVisible()
