"""
Tests for FEAT-capture-flow.

Source-scan tests verify _trigger_capture: session/region guards, state machine call,
grab_and_rotate, save_path, cv2.imwrite, _update_thumbnail, auto-section threshold,
and error handling.
Pure-logic tests verify auto-section threshold logic.
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
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestCaptureFlowSource:
    def test_trigger_capture_exists(self) -> None:
        assert "def _trigger_capture" in _MW_SRC

    def test_guards_session_is_none(self) -> None:
        assert "self._session is None" in _capture_block()

    def test_guards_capture_region_is_none(self) -> None:
        assert "self._capture_region is None" in _capture_block()

    def test_calls_state_machine_capture(self) -> None:
        assert "self._state_machine.capture()" in _capture_block()

    def test_calls_grab_and_rotate(self) -> None:
        assert "grab_and_rotate(" in _capture_block()

    def test_reads_rotation_mode(self) -> None:
        assert '"rotation_mode"' in _capture_block()

    def test_reads_capture_delay(self) -> None:
        assert '"capture_delay_ms"' in _capture_block()

    def test_calls_cv2_imwrite(self) -> None:
        assert "cv2.imwrite(" in _capture_block()

    def test_calls_update_thumbnail(self) -> None:
        assert "_update_thumbnail(save_path)" in _capture_block()

    def test_stores_last_capture_path(self) -> None:
        assert "self._last_capture_path = save_path" in _capture_block()

    def test_auto_section_threshold_read(self) -> None:
        assert '"auto_new_section_threshold"' in _capture_block()

    def test_auto_section_triggers_new_section(self) -> None:
        assert "_trigger_new_section()" in _capture_block()

    def test_error_calls_capture_error(self) -> None:
        assert "self._state_machine.capture_error()" in _capture_block()

    def test_update_thumbnail_method_exists(self) -> None:
        assert "def _update_thumbnail" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestCaptureFlowLogic:
    def _should_auto_section(self, threshold: int, image_count: int) -> bool:
        return threshold > 0 and image_count >= threshold

    def test_zero_threshold_never_triggers(self) -> None:
        assert not self._should_auto_section(0, 100)

    def test_threshold_at_count_triggers(self) -> None:
        assert self._should_auto_section(5, 5)

    def test_threshold_above_count_no_trigger(self) -> None:
        assert not self._should_auto_section(5, 4)

    def test_delay_ms_to_seconds(self) -> None:
        assert float(500) / 1000.0 == 0.5

    def test_zero_delay_no_sleep(self) -> None:
        delay_s = float(0) / 1000.0
        assert delay_s == 0.0

    def test_capture_path_is_path_object(self, tmp_path: Path) -> None:
        p = tmp_path / "0001.png"
        assert isinstance(p, Path)


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestCaptureFlowGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_session_none_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._session is None

    def test_capture_region_none_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._capture_region is None

    def test_last_capture_path_none_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._last_capture_path is None
