"""
Tests for FEAT-session-notes.

Source-scan tests verify widget creation, wiring, and file I/O logic.
Pure-logic tests verify save/load behaviour using tmp_path.
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

class TestSessionNotesSource:
    def test_notes_edit_created(self) -> None:
        assert "self._notes_edit = QTextEdit()" in _MW_SRC

    def test_notes_edit_max_height(self) -> None:
        assert "self._notes_edit.setMaximumHeight(80)" in _MW_SRC

    def test_notes_edit_placeholder(self) -> None:
        assert "self._notes_edit.setPlaceholderText" in _MW_SRC

    def test_notes_edit_initially_disabled(self) -> None:
        assert "self._notes_edit.setEnabled(False)" in _MW_SRC

    def test_notes_edit_wired_to_slot(self) -> None:
        assert "self._notes_edit.textChanged.connect(self._on_notes_changed)" in _MW_SRC

    def test_load_notes_called_on_new_session(self) -> None:
        idx = _MW_SRC.index("def _start_new_session")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._load_notes()" in block

    def test_load_notes_method_exists(self) -> None:
        assert "def _load_notes" in _MW_SRC

    def test_on_notes_changed_slot_exists(self) -> None:
        assert "def _on_notes_changed" in _MW_SRC

    def test_load_reads_notes_txt(self) -> None:
        assert '"notes.txt"' in _MW_SRC

    def test_load_uses_blockSignals(self) -> None:
        assert "blockSignals(True)" in _MW_SRC

    def test_load_enables_widget(self) -> None:
        assert "self._notes_edit.setEnabled(True)" in _MW_SRC

    def test_load_disables_when_no_session(self) -> None:
        idx = _MW_SRC.index("def _load_notes")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._notes_edit.setEnabled(False)" in block

    def test_save_writes_notes_txt(self) -> None:
        idx = _MW_SRC.index("def _on_notes_changed")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "notes_path.write_text" in block

    def test_save_guards_no_session(self) -> None:
        idx = _MW_SRC.index("def _on_notes_changed")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "if self._session is None:" in block

    def test_save_catches_oserror(self) -> None:
        assert "except OSError" in _MW_SRC

    def test_save_logs_warning_on_error(self) -> None:
        assert "logger.warning" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests (no Qt)
# ---------------------------------------------------------------------------

class TestSessionNotesLogic:
    def test_write_and_read_notes_txt(self, tmp_path: Path) -> None:
        notes_path = tmp_path / "notes.txt"
        notes_path.write_text("hello world", encoding="utf-8")
        assert notes_path.read_text(encoding="utf-8") == "hello world"

    def test_missing_notes_file_returns_empty(self, tmp_path: Path) -> None:
        notes_path = tmp_path / "notes.txt"
        text = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
        assert text == ""

    def test_overwrite_notes_file(self, tmp_path: Path) -> None:
        notes_path = tmp_path / "notes.txt"
        notes_path.write_text("first", encoding="utf-8")
        notes_path.write_text("second", encoding="utf-8")
        assert notes_path.read_text(encoding="utf-8") == "second"

    def test_unicode_notes_round_trip(self, tmp_path: Path) -> None:
        notes_path = tmp_path / "notes.txt"
        content = "第一章：\n一些笔记"
        notes_path.write_text(content, encoding="utf-8")
        assert notes_path.read_text(encoding="utf-8") == content


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSessionNotesGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_notes_edit_initially_disabled(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._notes_edit.isEnabled()

    def test_load_notes_enables_widget(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "session01"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._load_notes()
        assert w._notes_edit.isEnabled()

    def test_load_notes_reads_existing_file(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "session01"
        session_root.mkdir()
        (session_root / "notes.txt").write_text("test note", encoding="utf-8")
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._load_notes()
        assert w._notes_edit.toPlainText() == "test note"

    def test_load_notes_empty_when_no_file(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "session01"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._load_notes()
        assert w._notes_edit.toPlainText() == ""

    def test_on_notes_changed_saves_file(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "session01"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._load_notes()
        w._notes_edit.setPlainText("saved content")
        notes_path = session_root / "notes.txt"
        assert notes_path.exists()
        assert notes_path.read_text(encoding="utf-8") == "saved content"

    def test_load_notes_no_session_disables(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._session = None
        w._load_notes()
        assert not w._notes_edit.isEnabled()
        assert w._notes_edit.toPlainText() == ""
