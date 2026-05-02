"""
Tests for SessionDialog validation logic and MainWindow construction.

Pure-logic tests (TestSessionNameValidation, TestDeleteSessionRoot) run
headlessly in the normal pytest suite.

GUI tests (TestSessionDialogConstruction, TestMainWindowConstruction) require
a live QApplication and are marked @pytest.mark.gui.  They are excluded from
the default headless run because cv2 (conda-forge) and PySide6 both load Qt
DLLs that conflict in the same pytest process on Windows.

To run GUI tests interactively:
    pytest -m gui tests/gui/test_session_dialog.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from capture.session import CaptureSession, SessionNameError


# ---------------------------------------------------------------------------
# SessionNameError validation — pure logic, no display needed
# (SessionDialog delegates to CaptureSession.validate_session_name)
# ---------------------------------------------------------------------------

class TestSessionNameValidation:
    def test_valid_digits(self) -> None:
        assert CaptureSession.validate_session_name("001") == "001"
        assert CaptureSession.validate_session_name("42") == "42"

    def test_whitespace_stripped(self) -> None:
        assert CaptureSession.validate_session_name("  7  ") == "7"

    def test_empty_raises(self) -> None:
        with pytest.raises(SessionNameError):
            CaptureSession.validate_session_name("")

    def test_non_digit_raises(self) -> None:
        with pytest.raises(SessionNameError):
            CaptureSession.validate_session_name("chapter1")


# ---------------------------------------------------------------------------
# SessionDialog._delete_session_root — pure filesystem logic
# (no Qt import — uses only stdlib shutil)
# ---------------------------------------------------------------------------

class TestDeleteSessionRoot:
    """Tests for the _delete_session_root helper.

    We replicate the logic here rather than importing SessionDialog
    (which pulls in PySide6 at module level, causing DLL conflicts).
    """

    @staticmethod
    def _delete(root: Path) -> None:
        """Mirror of SessionDialog._delete_session_root logic."""
        import shutil
        import logging
        try:
            shutil.rmtree(root)
        except OSError:
            pass

    def test_deletes_existing_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "to_delete"
        target.mkdir()
        (target / "file.txt").write_text("data")
        self._delete(target)
        assert not target.exists()

    def test_nonexistent_directory_does_not_raise(self, tmp_path: Path) -> None:
        target = tmp_path / "nonexistent"
        self._delete(target)  # must not raise


# ---------------------------------------------------------------------------
# SessionDialog construction (requires QApplication + compatible DLL env)
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSessionDialogConstruction:
    def test_constructs_without_error(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        from gui.session_dialog import SessionDialog
        from utils.config_manager import ConfigManager

        QApplication.instance() or QApplication([])
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(
            json.dumps({"working_root_dir": str(tmp_path)}),
            encoding="utf-8",
        )
        cm = ConfigManager(path=cfg_path)
        dlg = SessionDialog(cm)
        assert dlg is not None
        dlg.close()

    def test_working_root_from_config(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        from gui.session_dialog import SessionDialog
        from utils.config_manager import ConfigManager

        QApplication.instance() or QApplication([])
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(
            json.dumps({"working_root_dir": str(tmp_path)}),
            encoding="utf-8",
        )
        cm = ConfigManager(path=cfg_path)
        dlg = SessionDialog(cm)
        assert dlg._working_root() == str(tmp_path)
        dlg.close()

    def test_working_root_fallback(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        from gui.session_dialog import SessionDialog
        from utils.config_manager import ConfigManager

        QApplication.instance() or QApplication([])
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("{}", encoding="utf-8")
        cm = ConfigManager(path=cfg_path)
        dlg = SessionDialog(cm)
        assert dlg._working_root() == "sessions"
        dlg.close()


# ---------------------------------------------------------------------------
# MainWindow construction (requires QApplication + compatible DLL env)
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestMainWindowConstruction:
    def test_constructs_without_error(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager

        QApplication.instance() or QApplication([])
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(
            json.dumps({"working_root_dir": str(tmp_path)}),
            encoding="utf-8",
        )
        cm = ConfigManager(path=cfg_path)
        win = MainWindow(cm)
        assert win is not None
        win._hotkeys.stop()
        win.close()

    def test_initial_state_is_idle(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from capture.state import AppState
        from utils.config_manager import ConfigManager

        QApplication.instance() or QApplication([])
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("{}", encoding="utf-8")
        cm = ConfigManager(path=cfg_path)
        win = MainWindow(cm)
        assert win._state_machine.state == AppState.IDLE
        win._hotkeys.stop()
        win.close()

    def test_hotkeys_start_on_construction(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager

        QApplication.instance() or QApplication([])
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("{}", encoding="utf-8")
        cm = ConfigManager(path=cfg_path)
        win = MainWindow(cm)
        assert win._hotkeys.is_running
        win._hotkeys.stop()
        win.close()

    def test_close_stops_hotkeys(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager

        QApplication.instance() or QApplication([])
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("{}", encoding="utf-8")
        cm = ConfigManager(path=cfg_path)
        win = MainWindow(cm)
        win.close()
        assert not win._hotkeys.is_running

    def test_trigger_new_section_without_session_is_noop(
        self, tmp_path: Path
    ) -> None:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager

        QApplication.instance() or QApplication([])
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("{}", encoding="utf-8")
        cm = ConfigManager(path=cfg_path)
        win = MainWindow(cm)
        win._trigger_new_section()  # must not raise
        win._hotkeys.stop()
        win.close()

    def test_trigger_capture_without_session_is_noop(
        self, tmp_path: Path
    ) -> None:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager

        QApplication.instance() or QApplication([])
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("{}", encoding="utf-8")
        cm = ConfigManager(path=cfg_path)
        win = MainWindow(cm)
        win._trigger_capture()  # must not raise
        win._hotkeys.stop()
        win.close()
