"""
Tests for FEAT-notes-autosave.

Source-scan tests verify widget creation, timer wiring, load/save logic.
Pure-logic tests verify file I/O helpers.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestNotesAutosaveSource:
    def test_notes_edit_created(self) -> None:
        assert "self._notes_edit = QTextEdit()" in _MW_SRC

    def test_placeholder_text(self) -> None:
        assert "auto-saved" in _MW_SRC

    def test_initially_disabled(self) -> None:
        assert "self._notes_edit.setEnabled(False)" in _MW_SRC

    def test_timer_created_singleshot(self) -> None:
        assert "self._notes_save_timer = QTimer(self)" in _MW_SRC
        assert "self._notes_save_timer.setSingleShot(True)" in _MW_SRC

    def test_timer_interval_2000ms(self) -> None:
        assert "self._notes_save_timer.setInterval(2000)" in _MW_SRC

    def test_timer_connected_to_slot(self) -> None:
        assert "self._notes_save_timer.timeout.connect(self._on_notes_changed)" in _MW_SRC

    def test_text_changed_starts_timer(self) -> None:
        assert "_notes_save_timer.start()" in _MW_SRC

    def test_qtimer_imported(self) -> None:
        assert "QTimer" in _MW_SRC

    def test_load_notes_method_exists(self) -> None:
        assert "def _load_notes" in _MW_SRC

    def test_load_notes_uses_block_signals(self) -> None:
        idx = _MW_SRC.index("def _load_notes")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "blockSignals" in block

    def test_load_notes_reads_notes_txt(self) -> None:
        idx = _MW_SRC.index("def _load_notes")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert '"notes.txt"' in block

    def test_on_notes_changed_slot_exists(self) -> None:
        assert "def _on_notes_changed" in _MW_SRC

    def test_on_notes_changed_writes_notes_txt(self) -> None:
        idx = _MW_SRC.index("def _on_notes_changed")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "write_text" in block

    def test_load_notes_called_on_new_session(self) -> None:
        idx = _MW_SRC.index("def _start_new_session")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_load_notes()" in block

    def test_load_notes_called_on_resume(self) -> None:
        idx = _MW_SRC.index("def _open_recent_session")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_load_notes()" in block

    def _load_block(self) -> str:
        idx = _MW_SRC.index("def _load_notes")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        return _MW_SRC[idx:end]

    def _changed_block(self) -> str:
        idx = _MW_SRC.index("def _on_notes_changed")
        end = _MW_SRC.index("\n    def _populate_preview", idx + 1)
        return _MW_SRC[idx:end]

    def test_load_blocks_signals_when_no_session(self) -> None:
        blk = self._load_block()
        assert "blockSignals(True)" in blk
        assert "blockSignals(False)" in blk

    def test_load_handles_oserror(self) -> None:
        assert "except OSError" in self._load_block()

    def test_on_notes_changed_guards_no_session(self) -> None:
        assert "self._session is None" in self._changed_block()

    def test_on_notes_changed_handles_oserror(self) -> None:
        assert "except OSError" in self._changed_block()

    def test_on_notes_changed_logs_warning_on_error(self) -> None:
        assert "logger.warning(" in self._changed_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

def _write_notes(root: Path, text: str) -> None:
    (root / "notes.txt").write_text(text, encoding="utf-8")


def _read_notes(root: Path) -> str:
    p = root / "notes.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""


class TestNotesAutosaveLogic:
    def test_write_and_read(self, tmp_path: Path) -> None:
        _write_notes(tmp_path, "hello notes")
        assert _read_notes(tmp_path) == "hello notes"

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert _read_notes(tmp_path) == ""

    def test_overwrite_replaces_content(self, tmp_path: Path) -> None:
        _write_notes(tmp_path, "old")
        _write_notes(tmp_path, "new")
        assert _read_notes(tmp_path) == "new"

    def test_empty_string_written(self, tmp_path: Path) -> None:
        _write_notes(tmp_path, "")
        assert _read_notes(tmp_path) == ""

    def test_unicode_content(self, tmp_path: Path) -> None:
        _write_notes(tmp_path, "你好世界")
        assert _read_notes(tmp_path) == "你好世界"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestNotesAutosaveGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_notes_edit_disabled_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._notes_edit.isEnabled()

    def test_load_notes_enables_edit(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "sess"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._load_notes()
        assert w._notes_edit.isEnabled()

    def test_load_reads_existing_file(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "sess"
        session_root.mkdir()
        (session_root / "notes.txt").write_text("stored notes", encoding="utf-8")
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._load_notes()
        assert w._notes_edit.toPlainText() == "stored notes"

    def test_on_notes_changed_writes_file(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "sess"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._notes_edit.setEnabled(True)
        w._notes_edit.blockSignals(True)
        w._notes_edit.setPlainText("my notes")
        w._notes_edit.blockSignals(False)
        w._on_notes_changed()
        assert (session_root / "notes.txt").read_text(encoding="utf-8") == "my notes"
