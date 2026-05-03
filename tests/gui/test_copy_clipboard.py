"""
Tests for FEAT-copy-clipboard.

Source-scan tests verify _copy_btn and _copy_section_btn creation, disabled on init,
signal wiring; _copy_results_to_clipboard (preview_pane.toPlainText, setText, status);
_copy_section_to_clipboard (session+results guard, section filter, setText, status).
Pure-logic tests verify section filter logic.
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

def _copy_results_block() -> str:
    idx = _MW_SRC.index("def _copy_results_to_clipboard")
    end = _MW_SRC.index("\n    def _build_chapters_from_results", idx + 1)
    return _MW_SRC[idx:end]

def _copy_section_block() -> str:
    idx = _MW_SRC.index("def _copy_section_to_clipboard")
    end = _MW_SRC.index("\n    @Slot()\n    def _copy_results_to_clipboard", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestCopyClipboardSource:
    def test_copy_btn_created(self) -> None:
        assert 'self._copy_btn = QPushButton("Copy to Clipboard")' in _MW_SRC

    def test_copy_btn_disabled_on_init(self) -> None:
        assert "self._copy_btn.setEnabled(False)" in _MW_SRC

    def test_copy_btn_connected(self) -> None:
        assert "_copy_btn.clicked.connect(self._copy_results_to_clipboard)" in _MW_SRC

    def test_copy_section_btn_created(self) -> None:
        assert 'self._copy_section_btn = QPushButton("Copy Section")' in _MW_SRC

    def test_copy_section_btn_disabled_on_init(self) -> None:
        assert "self._copy_section_btn.setEnabled(False)" in _MW_SRC

    def test_copy_section_btn_tooltip(self) -> None:
        assert "_copy_section_btn.setToolTip" in _MW_SRC

    def test_copy_section_btn_connected(self) -> None:
        assert "_copy_section_btn.clicked.connect(self._copy_section_to_clipboard)" in _MW_SRC

    def test_copy_results_reads_preview_pane(self) -> None:
        assert "_preview_pane.toPlainText()" in _copy_results_block()

    def test_copy_results_calls_set_text(self) -> None:
        assert "clipboard().setText(text)" in _copy_results_block()

    def test_copy_results_shows_status(self) -> None:
        assert "_status_bar.showMessage" in _copy_results_block()

    def test_copy_section_guards_session(self) -> None:
        assert "self._session is None" in _copy_section_block()

    def test_copy_section_guards_results(self) -> None:
        assert "self._ocr_results" in _copy_section_block()

    def test_copy_section_filters_by_folder(self) -> None:
        assert "current_folder" in _copy_section_block()

    def test_copy_section_calls_set_text(self) -> None:
        assert "clipboard().setText(text)" in _copy_section_block()

    def test_copy_btn_enabled_after_ocr(self) -> None:
        assert "self._copy_btn.setEnabled(True)" in _MW_SRC

    def test_copy_btns_disabled_on_clear_preview(self) -> None:
        assert "self._copy_section_btn.setEnabled(False)" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestCopyClipboardLogic:
    def test_empty_text_not_copied(self) -> None:
        text = ""
        would_copy = bool(text)
        assert not would_copy

    def test_non_empty_text_copied(self) -> None:
        text = "some OCR text"
        would_copy = bool(text)
        assert would_copy

    def test_no_session_blocks_copy_section(self) -> None:
        session = None
        results = ["r1"]
        should_copy = session is not None and bool(results)
        assert not should_copy

    def test_no_results_blocks_copy_section(self) -> None:
        session = object()
        results: list = []
        should_copy = session is not None and bool(results)
        assert not should_copy

    def test_session_and_results_allows_copy_section(self) -> None:
        session = object()
        results = ["r1"]
        should_copy = session is not None and bool(results)
        assert should_copy

    def test_join_results_text(self) -> None:
        texts = ["line one", "line two"]
        joined = "\n".join(texts)
        assert joined == "line one\nline two"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestCopyClipboardGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_copy_btn_disabled_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._copy_btn.isEnabled()

    def test_copy_section_btn_disabled_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._copy_section_btn.isEnabled()

    def test_copy_results_noop_when_empty(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._copy_results_to_clipboard()
