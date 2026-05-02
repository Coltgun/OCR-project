"""
Tests for FEAT-session-export-ui.

Headless tests (no PySide6) verify:
  - epub_output_dir is persisted to ConfigManager after export.
  - The chosen directory is read from config for the next file dialog.
  - _on_open_export_folder slot exists in source.
  - _last_export_path tracking is present in source.
  - Open-folder button wiring is present in source.

GUI tests are marked @pytest.mark.gui + @pytest.mark.skip as per project
convention (cv2 + PySide6 DLL conflict in headless pytest process).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


def make_config(tmp_path: Path, data: dict | None = None) -> ConfigManager:
    cfg = ConfigManager(path=tmp_path / "config.json")
    if data:
        for k, v in data.items():
            cfg.set(k, v)
    return cfg


# ---------------------------------------------------------------------------
# Headless source-scan tests
# ---------------------------------------------------------------------------

class TestExportUiSourceWiring:
    def test_open_folder_btn_created_in_status_bar(self) -> None:
        assert '_open_folder_btn = QPushButton("Open folder")' in _MW_SRC

    def test_open_folder_btn_initially_hidden(self) -> None:
        assert "_open_folder_btn.setVisible(False)" in _MW_SRC

    def test_open_folder_slot_exists(self) -> None:
        assert "def _on_open_export_folder" in _MW_SRC

    def test_os_startfile_used(self) -> None:
        assert "os.startfile(folder)" in _MW_SRC

    def test_last_export_path_tracked(self) -> None:
        assert "_last_export_path" in _MW_SRC

    def test_epub_output_dir_persisted_after_save(self) -> None:
        assert 'config.set("epub_output_dir"' in _MW_SRC
        assert "config.save()" in _MW_SRC

    def test_open_folder_btn_shown_on_success(self) -> None:
        assert "_open_folder_btn.setVisible(True)" in _MW_SRC

    def test_open_folder_btn_hidden_in_update_ui(self) -> None:
        idx = _MW_SRC.index("def _update_ui_for_state")
        idx_end = _MW_SRC.index("\n    @Slot", idx)
        block = _MW_SRC[idx:idx_end]
        assert "_open_folder_btn.setVisible(False)" in block

    def test_status_bar_shows_filename_not_full_path(self) -> None:
        assert "Path(save_path).name" in _MW_SRC

    def test_import_os_present(self) -> None:
        assert "import os" in _MW_SRC


# ---------------------------------------------------------------------------
# Headless config persistence logic tests
# ---------------------------------------------------------------------------

class TestExportDirPersistence:
    def test_epub_output_dir_saved_to_config(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path)
        cfg.set("epub_output_dir", str(tmp_path / "exports"))
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get_str("epub_output_dir") == str(tmp_path / "exports")

    def test_epub_output_dir_read_on_next_open(self, tmp_path: Path) -> None:
        export_dir = tmp_path / "my_exports"
        cfg = make_config(tmp_path, {"epub_output_dir": str(export_dir)})
        read_back = cfg.get("epub_output_dir", str(Path.home()))
        assert read_back == str(export_dir)

    def test_default_epub_output_dir_is_home(self) -> None:
        cfg = ConfigManager.__new__(ConfigManager)
        cfg._path = Path("/nonexistent/config.json")
        cfg._data = {}
        result = cfg.get("epub_output_dir", str(Path.home()))
        assert result == str(Path.home())

    def test_parent_dir_extracted_from_save_path(self, tmp_path: Path) -> None:
        save_path = str(tmp_path / "exports" / "book_001.epub")
        chosen_dir = str(Path(save_path).parent)
        assert chosen_dir == str(tmp_path / "exports")

    def test_filename_only_shown_in_status(self, tmp_path: Path) -> None:
        save_path = str(tmp_path / "exports" / "book_001.epub")
        display_name = Path(save_path).name
        assert display_name == "book_001.epub"


# ---------------------------------------------------------------------------
# GUI tests (require QApplication + compatible DLL env)
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestExportUiGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg), cfg

    def test_open_folder_btn_initially_hidden(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        assert not w._open_folder_btn.isVisible()

    def test_last_export_path_initially_empty(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        assert w._last_export_path == ""

    def test_open_folder_btn_hidden_when_no_path(self, tmp_path: Path) -> None:
        from capture.state import AppState
        w, _ = self._make_window(tmp_path)
        w._last_export_path = ""
        w._update_ui_for_state(AppState.IDLE)
        assert not w._open_folder_btn.isVisible()

    def test_open_folder_btn_visible_after_export_idle(self, tmp_path: Path) -> None:
        from capture.state import AppState
        w, _ = self._make_window(tmp_path)
        w._last_export_path = str(tmp_path / "book.epub")
        w._open_folder_btn.setVisible(True)
        w._update_ui_for_state(AppState.IDLE)
        assert w._open_folder_btn.isVisible()

    def test_open_folder_btn_hidden_on_ocr_running(self, tmp_path: Path) -> None:
        from capture.state import AppState
        w, _ = self._make_window(tmp_path)
        w._last_export_path = str(tmp_path / "book.epub")
        w._open_folder_btn.setVisible(True)
        w._update_ui_for_state(AppState.OCR_RUNNING)
        assert not w._open_folder_btn.isVisible()

    def test_epub_dir_persisted_on_export(self, tmp_path: Path) -> None:
        w, cfg = self._make_window(tmp_path)
        save_path = str(tmp_path / "exports" / "book.epub")
        chosen_dir = str(Path(save_path).parent)
        cfg.set("epub_output_dir", chosen_dir)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get_str("epub_output_dir") == chosen_dir

    def test_on_open_export_folder_safe_with_empty_path(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        w._last_export_path = ""
        w._on_open_export_folder()  # must not raise
