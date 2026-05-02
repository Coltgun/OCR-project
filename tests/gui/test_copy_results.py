"""
Tests for FEAT-copy-results.

Strategy:
1. Source-scan tests — verify button creation, wiring, enable/disable logic.
2. GUI tests — @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.types import OCRResult
from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan wiring tests
# ---------------------------------------------------------------------------

class TestCopyResultsSource:
    def test_copy_btn_created(self) -> None:
        assert 'self._copy_btn = QPushButton("Copy to Clipboard")' in _MW_SRC

    def test_copy_btn_initially_disabled(self) -> None:
        assert "self._copy_btn.setEnabled(False)" in _MW_SRC

    def test_copy_btn_wired_to_slot(self) -> None:
        assert "self._copy_btn.clicked.connect(self._copy_results_to_clipboard)" in _MW_SRC

    def test_copy_btn_in_preview_header(self) -> None:
        idx = _MW_SRC.index("# Results preview pane")
        end = _MW_SRC.index("self._preview_pane = QTextEdit()", idx)
        block = _MW_SRC[idx:end]
        assert "self._copy_btn" in block

    def test_copy_results_to_clipboard_slot_exists(self) -> None:
        assert "def _copy_results_to_clipboard" in _MW_SRC

    def test_slot_uses_qapplication_clipboard(self) -> None:
        assert "QApplication.clipboard().setText(text)" in _MW_SRC

    def test_slot_shows_status_message(self) -> None:
        assert "copied to clipboard" in _MW_SRC

    def test_status_message_has_timeout(self) -> None:
        assert "showMessage(\"OCR text copied to clipboard.\", 3000)" in _MW_SRC

    def test_copy_btn_enabled_in_populate_preview(self) -> None:
        idx = _MW_SRC.index("def _populate_preview")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._copy_btn.setEnabled(True)" in block

    def test_copy_btn_disabled_in_clear_preview(self) -> None:
        idx = _MW_SRC.index("def _clear_preview")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._copy_btn.setEnabled(False)" in block

    def test_slot_guards_empty_text(self) -> None:
        idx = _MW_SRC.index("def _copy_results_to_clipboard")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "if text:" in block


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestCopyResultsGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def _make(self, text: str, image_id: str = "") -> OCRResult:
        return OCRResult(text=text, confidence=0.9, image_id=image_id)

    def test_copy_btn_initially_disabled(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._copy_btn.isEnabled()

    def test_copy_btn_enabled_after_populate(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._populate_preview([self._make("hello")])
        assert w._copy_btn.isEnabled()

    def test_copy_btn_disabled_after_clear(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._populate_preview([self._make("hello")])
        w._clear_preview()
        assert not w._copy_btn.isEnabled()

    def test_clipboard_contains_text_after_copy(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        w = self._make_window(tmp_path)
        w._populate_preview([self._make("你好"), self._make("世界")])
        w._copy_results_to_clipboard()
        text = QApplication.clipboard().text()
        assert "你好" in text
        assert "世界" in text

    def test_copy_empty_pane_does_not_set_clipboard(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        w = self._make_window(tmp_path)
        QApplication.clipboard().setText("sentinel")
        w._copy_results_to_clipboard()
        assert QApplication.clipboard().text() == "sentinel"

    def test_status_bar_shows_message_after_copy(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._populate_preview([self._make("text")])
        w._copy_results_to_clipboard()
        assert "clipboard" in w._status_bar.currentMessage().lower()
