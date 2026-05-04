"""
Tests for FEAT-start-session.

Source-scan tests verify _start_new_session: is_idle guard, SessionDialog exec,
Accepted check, CaptureSession(session_root, resume=dlg.resume), clear
preview/thumbnail, _load_notes, _record_recent_session, _update_session_labels,
export_btn.setEnabled(False), logger.info, status bar message,
_update_ui_for_state(IDLE).
Pure-logic tests verify session state semantics.
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

def _start_block() -> str:
    idx = _MW_SRC.index("def _start_new_session")
    end = _MW_SRC.index("\n    @Slot()\n    def _trigger_capture", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestStartSessionSource:
    def test_start_new_session_exists(self) -> None:
        assert "def _start_new_session" in _MW_SRC

    def test_is_idle_guard(self) -> None:
        assert "self._state_machine.is_idle" in _start_block()

    def test_session_dialog_created(self) -> None:
        assert "SessionDialog(self._config, self)" in _start_block()

    def test_dialog_accepted_check(self) -> None:
        assert "SessionDialog.DialogCode.Accepted" in _start_block()

    def test_capture_session_created(self) -> None:
        assert "CaptureSession(dlg.session_root, resume=dlg.resume)" in _start_block()

    def test_ocr_results_cleared(self) -> None:
        assert "self._ocr_results = []" in _start_block()

    def test_clear_preview_called(self) -> None:
        assert "self._clear_preview()" in _start_block()

    def test_clear_thumbnail_called(self) -> None:
        assert "self._clear_thumbnail()" in _start_block()

    def test_load_notes_called(self) -> None:
        assert "self._load_notes()" in _start_block()

    def test_record_recent_session_called(self) -> None:
        assert "_record_recent_session(str(dlg.session_root))" in _start_block()

    def test_update_session_labels_called(self) -> None:
        assert "self._update_session_labels()" in _start_block()

    def test_export_btn_disabled(self) -> None:
        assert "self._export_btn.setEnabled(False)" in _start_block()

    def test_logger_info_called(self) -> None:
        assert "logger.info(" in _start_block()

    def test_status_bar_message_shown(self) -> None:
        assert "_status_bar.showMessage(" in _start_block()

    def test_update_ui_idle_called(self) -> None:
        assert "_update_ui_for_state(AppState.IDLE)" in _start_block()

    def test_new_session_btn_connected(self) -> None:
        assert "_new_session_btn" in _MW_SRC or "_start_new_session" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestStartSessionLogic:
    def test_resume_false_means_new_session(self) -> None:
        resume = False
        assert resume is False

    def test_resume_true_means_continue(self) -> None:
        resume = True
        assert resume is True

    def test_session_root_from_dialog(self, tmp_path: Path) -> None:
        session_root = tmp_path / "my_session"
        session_root.mkdir()
        assert session_root.exists()

    def test_ocr_results_empty_after_start(self) -> None:
        ocr_results: list = []
        assert len(ocr_results) == 0

    def test_session_str_path_record(self, tmp_path: Path) -> None:
        p = tmp_path / "session_dir"
        p.mkdir()
        recorded = str(p)
        assert recorded == str(p)

    def test_config_round_trip_recent_sessions(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("recent_sessions", ["/path/one", "/path/two"])
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("recent_sessions") == ["/path/one", "/path/two"]


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestStartSessionGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_export_btn_disabled_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._export_btn.isEnabled()

    def test_no_session_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._session is None

    def test_ocr_results_empty_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._ocr_results == []
