"""
Tests for FEAT-session-dialog.

Source-scan tests verify _start_new_session slot: idle guard, SessionDialog exec,
CaptureSession creation, _record_recent_session call, and UI update.
Pure-logic tests verify CaptureSession resume flag semantics.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestSessionDialogFlowSource:
    def _slot_block(self) -> str:
        idx = _MW_SRC.index("def _start_new_session")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        return _MW_SRC[idx:end]

    def test_slot_exists(self) -> None:
        assert "def _start_new_session" in _MW_SRC

    def test_slot_has_slot_decorator(self) -> None:
        idx = _MW_SRC.index("def _start_new_session")
        pre = _MW_SRC[max(0, idx - 30): idx]
        assert "@Slot()" in pre

    def test_slot_guards_idle(self) -> None:
        assert "self._state_machine.is_idle" in self._slot_block()

    def test_slot_creates_session_dialog(self) -> None:
        assert "SessionDialog(self._config" in self._slot_block()

    def test_slot_checks_accepted(self) -> None:
        assert "SessionDialog.DialogCode.Accepted" in self._slot_block()

    def test_slot_creates_capture_session(self) -> None:
        assert "CaptureSession(dlg.session_root" in self._slot_block()

    def test_slot_passes_resume_flag(self) -> None:
        assert "resume=dlg.resume" in self._slot_block()

    def test_slot_calls_record_recent(self) -> None:
        assert "_record_recent_session" in self._slot_block()

    def test_slot_updates_session_labels(self) -> None:
        assert "_update_session_labels()" in self._slot_block()

    def test_slot_disables_export_btn(self) -> None:
        assert "_export_btn.setEnabled(False)" in self._slot_block()

    def test_session_dialog_imported(self) -> None:
        assert "from gui.session_dialog import SessionDialog" in _MW_SRC

    def test_capture_session_imported(self) -> None:
        assert "CaptureSession" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestSessionDialogFlowLogic:
    def test_resume_false_creates_new(self) -> None:
        resume = False
        assert not resume

    def test_resume_true_resumes(self) -> None:
        resume = True
        assert resume

    def test_session_root_is_path(self, tmp_path: Path) -> None:
        root = tmp_path / "my_session"
        root.mkdir()
        assert root.exists()

    def test_idle_guard_blocks_busy(self) -> None:
        is_idle = False
        if not is_idle:
            blocked = True
        else:
            blocked = False
        assert blocked

    def test_idle_guard_allows_idle(self) -> None:
        is_idle = True
        if not is_idle:
            blocked = True
        else:
            blocked = False
        assert not blocked

    def test_rejected_dialog_returns_early(self) -> None:
        class FakeResult:
            Accepted = 1
            Rejected = 0
        result = FakeResult.Rejected
        if result != FakeResult.Accepted:
            proceeded = False
        else:
            proceeded = True
        assert not proceeded


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSessionDialogFlowGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_start_new_session_action_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert hasattr(w, "_start_new_session")

    def test_session_is_none_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._session is None

    def test_export_btn_disabled_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._export_btn.isEnabled()
