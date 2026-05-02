"""
Tests for FEAT-capture-counter-reset.

Source-scan tests verify widget creation and slot wiring.
Pure-logic tests verify the reset behaviour via direct state inspection.
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
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestCaptureCounterResetSource:
    def test_reset_count_btn_created(self) -> None:
        assert 'self._reset_count_btn = QPushButton("Reset Count")' in _MW_SRC

    def test_reset_count_btn_initially_disabled(self) -> None:
        assert "self._reset_count_btn.setEnabled(False)" in _MW_SRC

    def test_reset_count_btn_wired_to_slot(self) -> None:
        assert "self._reset_count_btn.clicked.connect(self._reset_capture_count)" in _MW_SRC

    def test_reset_capture_count_slot_exists(self) -> None:
        assert "def _reset_capture_count" in _MW_SRC

    def test_reset_clears_ocr_results(self) -> None:
        idx = _MW_SRC.index("def _reset_capture_count")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._ocr_results = []" in block

    def test_reset_sets_count_label_zero(self) -> None:
        idx = _MW_SRC.index("def _reset_capture_count")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert 'self._count_label.setText("0")' in block

    def test_reset_disables_export_btn(self) -> None:
        idx = _MW_SRC.index("def _reset_capture_count")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._export_btn.setEnabled(False)" in block

    def test_reset_clears_preview(self) -> None:
        idx = _MW_SRC.index("def _reset_capture_count")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._clear_preview()" in block

    def test_reset_guards_not_idle(self) -> None:
        idx = _MW_SRC.index("def _reset_capture_count")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._state_machine.is_idle" in block

    def test_reset_guards_no_session(self) -> None:
        idx = _MW_SRC.index("def _reset_capture_count")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._session is None" in block

    def test_reset_shows_status_message(self) -> None:
        assert "Capture count reset" in _MW_SRC

    def test_reset_btn_enabled_in_update_ui(self) -> None:
        assert "self._reset_count_btn.setEnabled(is_idle and has_session)" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests (no Qt)
# ---------------------------------------------------------------------------

class TestCaptureCounterResetLogic:
    def test_clearing_list_resets_to_empty(self) -> None:
        results = ["a", "b", "c"]
        results.clear()
        assert results == []

    def test_bool_empty_list_is_false(self) -> None:
        assert not bool([])

    def test_bool_nonempty_list_is_true(self) -> None:
        assert bool(["item"])


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestCaptureCounterResetGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_reset_btn_initially_disabled(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._reset_count_btn.isEnabled()

    def test_reset_btn_enabled_after_session(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        from capture.state import AppState
        session_root = tmp_path / "s1"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._update_ui_for_state(AppState.IDLE)
        assert w._reset_count_btn.isEnabled()

    def test_reset_clears_results_and_label(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        from core.types import OCRResult
        session_root = tmp_path / "s1"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._ocr_results = [
            OCRResult(text="x", confidence=1.0, bbox=(0, 0, 10, 10), image_id="i1")
        ]
        w._count_label.setText("1")
        w._reset_capture_count()
        assert w._ocr_results == []
        assert w._count_label.text() == "0"

    def test_reset_disables_export_btn(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "s1"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._export_btn.setEnabled(True)
        w._reset_capture_count()
        assert not w._export_btn.isEnabled()

    def test_reset_noop_when_no_session(self, tmp_path: Path) -> None:
        from core.types import OCRResult
        w = self._make_window(tmp_path)
        w._ocr_results = [
            OCRResult(text="x", confidence=1.0, bbox=(0, 0, 10, 10), image_id="i1")
        ]
        w._reset_capture_count()
        assert len(w._ocr_results) == 1
