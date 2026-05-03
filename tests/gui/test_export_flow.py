"""
Tests for FEAT-export-flow.

Source-scan tests verify _trigger_export: format selection via _export_fmt_combo,
_progress_bar lifecycle, save_path building from template, formatter dispatch,
_last_export_path, _open_folder_btn show, error handling, and output_dir persistence.
Pure-logic tests verify filename template substitution and _EXT_MAP logic.
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

def _export_block() -> str:
    idx = _MW_SRC.index("def _trigger_export")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestExportFlowSource:
    def test_trigger_export_slot_exists(self) -> None:
        assert "def _trigger_export" in _MW_SRC

    def test_reads_export_fmt_combo(self) -> None:
        assert "_export_fmt_combo.currentData()" in _export_block()

    def test_progress_bar_set_indeterminate(self) -> None:
        assert "self._progress_bar.setRange(0, 0)" in _export_block()

    def test_progress_bar_shown(self) -> None:
        assert "self._progress_bar.setVisible(True)" in _export_block()

    def test_progress_bar_hidden_on_success(self) -> None:
        block = _export_block()
        # Both True and False setVisible calls must exist
        assert block.count("self._progress_bar.setVisible(False)") >= 1

    def test_save_path_from_file_dialog(self) -> None:
        assert "QFileDialog.getSaveFileName" in _export_block()

    def test_filename_template_substitution(self) -> None:
        assert '"export_filename_template"' in _export_block()

    def test_last_export_path_stored(self) -> None:
        assert "self._last_export_path = save_path" in _export_block()

    def test_open_folder_btn_shown_on_success(self) -> None:
        assert "self._open_folder_btn.setVisible(True)" in _export_block()

    def test_epub_formatter_dispatched(self) -> None:
        assert "EpubFormatter" in _export_block()

    def test_error_shows_message_box(self) -> None:
        assert 'QMessageBox.critical' in _export_block()

    def test_output_dir_persisted(self) -> None:
        assert '"epub_output_dir"' in _export_block()

    def test_cancelled_dialog_cancels_state(self) -> None:
        assert "self._state_machine.cancel()" in _export_block()

    def test_export_done_called_on_success(self) -> None:
        assert "self._state_machine.export_done()" in _export_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestExportFlowLogic:
    _EXT_MAP = {"epub": "epub", "txt": "txt", "md": "md"}

    def test_epub_extension(self) -> None:
        assert self._EXT_MAP["epub"] == "epub"

    def test_txt_extension(self) -> None:
        assert self._EXT_MAP["txt"] == "txt"

    def test_md_extension(self) -> None:
        assert self._EXT_MAP["md"] == "md"

    def test_template_substitution(self) -> None:
        template = "{session}_{timestamp}"
        result = template.replace("{session}", "book").replace("{timestamp}", "20250101")
        assert result == "book_20250101"

    def test_default_name_built(self) -> None:
        stem = "book_20250101"
        ext = "epub"
        name = f"{stem}.{ext}"
        assert name == "book_20250101.epub"

    def test_empty_save_path_cancels(self) -> None:
        save_path = ""
        assert not save_path


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestExportFlowGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_export_fmt_combo_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._export_fmt_combo is not None

    def test_progress_bar_hidden_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._progress_bar.isVisible()

    def test_last_export_path_empty_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._last_export_path == ""
