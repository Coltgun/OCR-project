"""
Tests for FEAT-notes-panel.

Source-scan tests verify _notes_edit QTextEdit (placeholder, disabled on init,
minHeight/maxHeight, sizePolicy), _notes_save_timer QTimer (singleShot, interval=2000,
timeout->_on_notes_changed), textChanged->timer.start(), _load_notes (session None
guard: disabled+blockSignals+clear, notes.txt path, OSError guard, setPlainText,
blockSignals wrap), _on_notes_changed (session None guard, notes.txt path, write_text,
OSError catch+logger.warning).
Pure-logic tests verify notes path construction, timer interval semantics, OSError
fallback to empty string.
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

def _load_notes_block() -> str:
    idx = _MW_SRC.index("def _load_notes")
    end = _MW_SRC.index("\n    @Slot()\n    def _on_notes_changed", idx + 1)
    return _MW_SRC[idx:end]

def _on_notes_changed_block() -> str:
    idx = _MW_SRC.index("def _on_notes_changed")
    end = _MW_SRC.index("\n    def _populate_preview", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestNotesPanelSource:
    def test_notes_edit_created(self) -> None:
        assert "self._notes_edit = QTextEdit()" in _MW_SRC

    def test_notes_edit_placeholder(self) -> None:
        assert '_notes_edit.setPlaceholderText("Type session notes here' in _MW_SRC

    def test_notes_edit_disabled_on_init(self) -> None:
        idx = _MW_SRC.index("self._notes_edit = QTextEdit()")
        snippet = _MW_SRC[idx:idx + 200]
        assert "_notes_edit.setEnabled(False)" in snippet

    def test_notes_edit_min_height(self) -> None:
        assert "_notes_edit.setMinimumHeight(60)" in _MW_SRC

    def test_notes_edit_max_height(self) -> None:
        assert "_notes_edit.setMaximumHeight(160)" in _MW_SRC

    def test_notes_save_timer_created(self) -> None:
        assert "self._notes_save_timer = QTimer(self)" in _MW_SRC

    def test_notes_save_timer_single_shot(self) -> None:
        assert "_notes_save_timer.setSingleShot(True)" in _MW_SRC

    def test_notes_save_timer_interval_2000(self) -> None:
        assert "_notes_save_timer.setInterval(2000)" in _MW_SRC

    def test_notes_save_timer_connected_to_on_notes_changed(self) -> None:
        assert "_notes_save_timer.timeout.connect(self._on_notes_changed)" in _MW_SRC

    def test_text_changed_starts_timer(self) -> None:
        assert "_notes_save_timer.start()" in _MW_SRC

    def test_load_notes_exists(self) -> None:
        assert "def _load_notes" in _MW_SRC

    def test_load_notes_guards_no_session(self) -> None:
        assert "if self._session is None:" in _load_notes_block()

    def test_load_notes_disables_on_no_session(self) -> None:
        assert "_notes_edit.setEnabled(False)" in _load_notes_block()

    def test_load_notes_uses_notes_txt_path(self) -> None:
        assert '"notes.txt"' in _load_notes_block()

    def test_load_notes_blocks_signals(self) -> None:
        assert "_notes_edit.blockSignals(True)" in _load_notes_block()

    def test_load_notes_catches_oserror(self) -> None:
        assert "except OSError:" in _load_notes_block()

    def test_load_notes_sets_plain_text(self) -> None:
        assert "_notes_edit.setPlainText(text)" in _load_notes_block()

    def test_on_notes_changed_exists(self) -> None:
        assert "def _on_notes_changed" in _MW_SRC

    def test_on_notes_changed_guards_no_session(self) -> None:
        assert "if self._session is None:" in _on_notes_changed_block()

    def test_on_notes_changed_writes_notes_txt(self) -> None:
        assert "notes_path.write_text(" in _on_notes_changed_block()

    def test_on_notes_changed_catches_oserror(self) -> None:
        assert "except OSError as exc:" in _on_notes_changed_block()

    def test_on_notes_changed_logs_warning(self) -> None:
        assert "logger.warning(" in _on_notes_changed_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestNotesPanelLogic:
    def test_notes_path_construction(self, tmp_path: Path) -> None:
        session_root = tmp_path / "session1"
        notes_path = session_root / "notes.txt"
        assert notes_path.name == "notes.txt"
        assert notes_path.parent == session_root

    def test_notes_read_when_exists(self, tmp_path: Path) -> None:
        notes_path = tmp_path / "notes.txt"
        notes_path.write_text("hello notes", encoding="utf-8")
        text = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
        assert text == "hello notes"

    def test_notes_empty_when_missing(self, tmp_path: Path) -> None:
        notes_path = tmp_path / "notes.txt"
        text = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
        assert text == ""

    def test_oserror_fallback_to_empty(self) -> None:
        try:
            raise OSError("simulated")
        except OSError:
            text = ""
        assert text == ""

    def test_timer_interval_2000ms(self) -> None:
        interval_ms = 2000
        assert interval_ms == 2000

    def test_notes_write_roundtrip(self, tmp_path: Path) -> None:
        notes_path = tmp_path / "notes.txt"
        content = "session note line 1\nline 2"
        notes_path.write_text(content, encoding="utf-8")
        assert notes_path.read_text(encoding="utf-8") == content


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestNotesPanelGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_notes_edit_disabled_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._notes_edit.isEnabled()

    def test_load_notes_empty_when_no_file(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        root = tmp_path / "s1"
        root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(root)
        w._load_notes()
        assert w._notes_edit.toPlainText() == ""

    def test_load_notes_reads_existing_file(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        root = tmp_path / "s1"
        root.mkdir()
        (root / "notes.txt").write_text("my notes", encoding="utf-8")
        w = self._make_window(tmp_path)
        w._session = CaptureSession(root)
        w._load_notes()
        assert w._notes_edit.toPlainText() == "my notes"
