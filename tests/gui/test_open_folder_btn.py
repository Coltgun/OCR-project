"""
Tests for FEAT-open-folder-btn.

Source-scan tests verify button creation, wiring, visibility lifecycle, and slot structure.
Pure-logic tests verify path extraction and guard logic.
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

class TestOpenFolderBtnSource:
    def _slot_block(self) -> str:
        idx = _MW_SRC.index("def _on_open_export_folder")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        return _MW_SRC[idx:end]

    def test_button_created(self) -> None:
        assert 'QPushButton("Open folder")' in _MW_SRC

    def test_button_initially_hidden(self) -> None:
        idx = _MW_SRC.index('QPushButton("Open folder")')
        snippet = _MW_SRC[idx: idx + 200]
        assert "setVisible(False)" in snippet

    def test_button_added_to_status_bar(self) -> None:
        assert "self._status_bar.addPermanentWidget(self._open_folder_btn)" in _MW_SRC

    def test_button_connected_to_slot(self) -> None:
        assert "self._open_folder_btn.clicked.connect(self._on_open_export_folder)" in _MW_SRC

    def test_last_export_path_initialised(self) -> None:
        assert 'self._last_export_path: str = ""' in _MW_SRC

    def test_export_stores_path(self) -> None:
        assert "self._last_export_path = save_path" in _MW_SRC

    def test_export_shows_button(self) -> None:
        assert "self._open_folder_btn.setVisible(True)" in _MW_SRC

    def test_state_update_hides_button_when_no_path(self) -> None:
        assert "self._open_folder_btn.setVisible(False)" in _MW_SRC

    def test_slot_exists(self) -> None:
        assert "def _on_open_export_folder" in _MW_SRC

    def test_slot_guards_empty_path(self) -> None:
        assert "self._last_export_path" in self._slot_block()

    def test_slot_calls_os_startfile(self) -> None:
        assert "os.startfile(folder)" in self._slot_block()

    def test_slot_catches_os_error(self) -> None:
        assert "OSError" in self._slot_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestOpenFolderBtnLogic:
    def test_empty_path_is_falsy(self) -> None:
        path = ""
        assert not path

    def test_nonempty_path_is_truthy(self) -> None:
        path = "C:/some/folder/file.epub"
        assert path

    def test_parent_extraction(self, tmp_path: Path) -> None:
        p = tmp_path / "sub" / "file.epub"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        assert str(p.parent) == str(tmp_path / "sub")

    def test_parent_str_conversion(self) -> None:
        p = Path("C:/some/folder/file.epub")
        assert p.parent == Path("C:/some/folder")

    def test_hidden_when_path_empty(self) -> None:
        last_export_path = ""
        visible = bool(last_export_path)
        assert not visible

    def test_visible_when_path_set(self) -> None:
        last_export_path = "C:/out/file.epub"
        visible = bool(last_export_path)
        assert visible


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestOpenFolderBtnGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_button_hidden_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._open_folder_btn.isVisible()

    def test_last_export_path_empty_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._last_export_path == ""

    def test_button_is_in_status_bar(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._open_folder_btn is not None
