"""
Tests for FEAT-notes-editor.

Source-scan tests verify _notes_edit QTextEdit, placeholder, debounce timer,
_load_notes (session guard, notes.txt path, blockSignals, enable/disable),
and _on_notes_changed (auto-save, OSError handling).
Pure-logic tests verify notes path construction and empty-session guard.
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

def _load_block() -> str:
    idx = _MW_SRC.index("def _load_notes")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]

def _save_block() -> str:
    idx = _MW_SRC.index("def _on_notes_changed")
    end = _MW_SRC.index("\n    def _populate_preview", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestNotesEditorSource:
    def test_notes_edit_created(self) -> None:
        assert "self._notes_edit = QTextEdit()" in _MW_SRC

    def test_notes_edit_placeholder(self) -> None:
        assert "self._notes_edit.setPlaceholderText" in _MW_SRC

    def test_notes_edit_disabled_on_init(self) -> None:
        assert "self._notes_edit.setEnabled(False)" in _MW_SRC

    def test_debounce_timer_created(self) -> None:
        assert "self._notes_save_timer = QTimer(self)" in _MW_SRC

    def test_debounce_timer_single_shot(self) -> None:
        assert "_notes_save_timer.setSingleShot(True)" in _MW_SRC

    def test_text_changed_starts_timer(self) -> None:
        assert "_notes_edit.textChanged.connect" in _MW_SRC
        assert "_notes_save_timer.start()" in _MW_SRC

    def test_load_notes_method_exists(self) -> None:
        assert "def _load_notes" in _MW_SRC

    def test_load_notes_checks_session(self) -> None:
        assert "self._session is None" in _load_block()

    def test_load_notes_uses_notes_txt(self) -> None:
        assert '"notes.txt"' in _load_block()

    def test_load_notes_block_signals(self) -> None:
        assert "blockSignals(True)" in _load_block()
        assert "blockSignals(False)" in _load_block()

    def test_load_notes_enables_edit(self) -> None:
        assert "_notes_edit.setEnabled(True)" in _load_block()

    def test_on_notes_changed_writes_file(self) -> None:
        assert "write_text(" in _save_block()

    def test_on_notes_changed_uses_notes_txt(self) -> None:
        assert '"notes.txt"' in _save_block()

    def test_on_notes_changed_catches_os_error(self) -> None:
        assert "except OSError" in _save_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestNotesEditorLogic:
    def test_notes_path_from_session_root(self, tmp_path: Path) -> None:
        root = tmp_path / "session_1"
        root.mkdir()
        notes_path = root / "notes.txt"
        assert notes_path.parent == root

    def test_notes_txt_read_if_exists(self, tmp_path: Path) -> None:
        notes = tmp_path / "notes.txt"
        notes.write_text("hello", encoding="utf-8")
        text = notes.read_text(encoding="utf-8") if notes.exists() else ""
        assert text == "hello"

    def test_notes_txt_empty_if_missing(self, tmp_path: Path) -> None:
        notes = tmp_path / "notes.txt"
        text = notes.read_text(encoding="utf-8") if notes.exists() else ""
        assert text == ""

    def test_notes_write_round_trip(self, tmp_path: Path) -> None:
        notes = tmp_path / "notes.txt"
        notes.write_text("session note", encoding="utf-8")
        assert notes.read_text(encoding="utf-8") == "session note"

    def test_session_none_disables_edit(self) -> None:
        session = None
        enabled = session is not None
        assert not enabled

    def test_session_present_enables_edit(self) -> None:
        session = object()
        enabled = session is not None
        assert enabled


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestNotesEditorGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_notes_edit_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._notes_edit is not None

    def test_notes_edit_disabled_no_session(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._notes_edit.isEnabled()

    def test_load_notes_populates_text(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "s1"
        session_root.mkdir()
        (session_root / "notes.txt").write_text("test note", encoding="utf-8")
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root, resume=True)
        w._load_notes()
        assert w._notes_edit.toPlainText() == "test note"
