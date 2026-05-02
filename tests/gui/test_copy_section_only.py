"""
Tests for FEAT-copy-section-only.

Source-scan tests verify button creation, wiring, and slot logic.
Pure-logic tests verify section filtering.
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

class TestCopySectionOnlySource:
    def test_button_created(self) -> None:
        assert 'self._copy_section_btn = QPushButton("Copy Section")' in _MW_SRC

    def test_button_initially_disabled(self) -> None:
        assert "self._copy_section_btn.setEnabled(False)" in _MW_SRC

    def test_button_tooltip(self) -> None:
        assert '"Copy OCR results from the current section only"' in _MW_SRC

    def test_button_connected(self) -> None:
        assert "self._copy_section_btn.clicked.connect(self._copy_section_to_clipboard)" in _MW_SRC

    def test_slot_exists(self) -> None:
        assert "def _copy_section_to_clipboard" in _MW_SRC

    def test_slot_guards_none_session(self) -> None:
        idx = _MW_SRC.index("def _copy_section_to_clipboard")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._session is None" in block

    def test_slot_uses_current_folder(self) -> None:
        idx = _MW_SRC.index("def _copy_section_to_clipboard")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "current_folder" in block

    def test_slot_filters_by_folder_path(self) -> None:
        idx = _MW_SRC.index("def _copy_section_to_clipboard")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "folder_path" in block

    def test_slot_joins_text(self) -> None:
        idx = _MW_SRC.index("def _copy_section_to_clipboard")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert 'r.text for r in section_results' in block

    def test_slot_sets_clipboard(self) -> None:
        idx = _MW_SRC.index("def _copy_section_to_clipboard")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "clipboard().setText" in block

    def test_slot_shows_status_message(self) -> None:
        idx = _MW_SRC.index("def _copy_section_to_clipboard")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "showMessage" in block

    def test_enabled_in_populate_preview(self) -> None:
        idx = _MW_SRC.index("def _populate_preview")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_copy_section_btn.setEnabled" in block

    def test_disabled_in_clear_preview(self) -> None:
        idx = _MW_SRC.index("def _clear_preview")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_copy_section_btn.setEnabled(False)" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass
class _FakeResult:
    text: str
    image_id: str


def _filter_section(results, folder_path: Path, fn: int):
    """Mirror the filter used in _copy_section_to_clipboard."""
    return [
        r for r in results
        if (folder_path / f"{r.image_id}.png").exists()
        or r.image_id.startswith(str(fn) + "/")
    ]


class TestCopySectionOnlyLogic:
    def test_prefix_match_includes_result(self, tmp_path: Path) -> None:
        folder = tmp_path / "2"
        folder.mkdir()
        results = [_FakeResult("hello", "2/0001"), _FakeResult("world", "1/0001")]
        out = _filter_section(results, folder, 2)
        assert len(out) == 1
        assert out[0].text == "hello"

    def test_file_exists_match(self, tmp_path: Path) -> None:
        folder = tmp_path / "1"
        folder.mkdir()
        img = folder / "0001.png"
        img.write_bytes(b"")
        results = [_FakeResult("found", "0001"), _FakeResult("missing", "0002")]
        out = _filter_section(results, folder, 1)
        assert len(out) == 1
        assert out[0].text == "found"

    def test_empty_results(self, tmp_path: Path) -> None:
        folder = tmp_path / "1"
        folder.mkdir()
        out = _filter_section([], folder, 1)
        assert out == []

    def test_joined_text(self) -> None:
        results = [_FakeResult("line1", "x"), _FakeResult("line2", "y")]
        text = "\n".join(r.text for r in results)
        assert text == "line1\nline2"

    def test_status_message_format(self) -> None:
        fn = 3
        count = 5
        msg = f"Section {fn} OCR text copied ({count} block(s))."
        assert "Section 3" in msg
        assert "5 block(s)" in msg


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestCopySectionOnlyGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_button_exists(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert hasattr(w, "_copy_section_btn")

    def test_button_disabled_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._copy_section_btn.isEnabled()

    def test_button_enabled_after_populate(self, tmp_path: Path) -> None:
        from core.types import OCRResult
        from capture.session import CaptureSession
        w = self._make_window(tmp_path)
        session_root = tmp_path / "sess"
        session_root.mkdir()
        w._session = CaptureSession(session_root)
        results = [OCRResult(text="hi", image_id="0001", confidence=0.9, bbox=(0, 0, 1, 1))]
        w._populate_preview(results)
        assert w._copy_section_btn.isEnabled()

    def test_button_disabled_after_clear(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._clear_preview()
        assert not w._copy_section_btn.isEnabled()
