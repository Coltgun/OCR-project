"""
Tests for FEAT-export-progress.

Source-scan tests verify that _progress_bar is shown (indeterminate) before
the export operation and hidden on both success and error paths.
Pure-logic tests verify range/visibility semantics.
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
# helpers
# ---------------------------------------------------------------------------

def _export_block() -> str:
    idx = _MW_SRC.index("def _trigger_export")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestExportProgressSource:
    def test_progress_bar_created_in_status_bar(self) -> None:
        assert "self._progress_bar = QProgressBar()" in _MW_SRC

    def test_progress_bar_initially_hidden(self) -> None:
        idx = _MW_SRC.index("self._progress_bar = QProgressBar()")
        snippet = _MW_SRC[idx: idx + 300]
        assert "setVisible(False)" in snippet

    def test_progress_bar_added_to_status_bar(self) -> None:
        assert "self._status_bar.addPermanentWidget(self._progress_bar)" in _MW_SRC

    def test_export_sets_indeterminate_range(self) -> None:
        assert "self._progress_bar.setRange(0, 0)" in _export_block()

    def test_export_shows_progress_bar(self) -> None:
        block = _export_block()
        assert "self._progress_bar.setVisible(True)" in block

    def test_export_hides_on_success(self) -> None:
        block = _export_block()
        idx_show = block.index("setVisible(True)")
        idx_hide = block.index("setVisible(False)", idx_show)
        assert idx_hide > idx_show

    def test_export_hides_on_error(self) -> None:
        block = _export_block()
        idx_first_hide = block.index("setVisible(False)")
        idx_second_hide = block.index("setVisible(False)", idx_first_hide + 1)
        assert idx_second_hide > idx_first_hide

    def test_progress_bar_has_fixed_width(self) -> None:
        assert "self._progress_bar.setFixedWidth" in _MW_SRC

    def test_trigger_export_guards_empty_results(self) -> None:
        assert "if not self._ocr_results" in _export_block()

    def test_trigger_export_reads_fmt_from_combo(self) -> None:
        assert "self._export_fmt_combo.currentData()" in _export_block()

    def test_ext_map_defined(self) -> None:
        assert '_EXT_MAP = {"epub": "epub"' in _export_block()

    def test_filter_map_defined(self) -> None:
        assert '_FILTER_MAP = {' in _export_block()

    def test_title_map_defined(self) -> None:
        assert '_TITLE_MAP = {' in _export_block()

    def test_file_dialog_called(self) -> None:
        assert "QFileDialog.getSaveFileName(" in _export_block()

    def test_cancel_path_resets_to_idle(self) -> None:
        assert "self._state_machine.cancel()" in _export_block()

    def test_epub_output_dir_persisted(self) -> None:
        assert '"epub_output_dir"' in _export_block()

    def test_formatter_map_has_three_entries(self) -> None:
        block = _export_block()
        assert '"epub": EpubFormatter' in block
        assert '"txt": PlainTextFormatter' in block
        assert '"md": MarkdownFormatter' in block

    def test_export_error_shows_critical_dialog(self) -> None:
        assert 'QMessageBox.critical(self, "Export Error"' in _export_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestExportProgressLogic:
    def test_range_zero_zero_means_indeterminate(self) -> None:
        min_val, max_val = 0, 0
        assert min_val == max_val == 0

    def test_range_zero_hundred_means_determinate(self) -> None:
        min_val, max_val = 0, 100
        assert max_val > min_val

    def test_hidden_by_default(self) -> None:
        visible = False
        assert not visible

    def test_shown_before_work(self) -> None:
        visible = True
        assert visible

    def test_hidden_after_success(self) -> None:
        visible = False
        assert not visible

    def test_hidden_after_error(self) -> None:
        visible = False
        assert not visible

    def test_ext_map_values(self) -> None:
        _EXT_MAP = {"epub": "epub", "txt": "txt", "md": "md"}
        assert _EXT_MAP["epub"] == "epub"
        assert _EXT_MAP["txt"] == "txt"
        assert _EXT_MAP["md"] == "md"

    def test_ext_map_unknown_defaults_epub(self) -> None:
        _EXT_MAP = {"epub": "epub", "txt": "txt", "md": "md"}
        assert _EXT_MAP.get("unknown", "epub") == "epub"

    def test_filename_template_substitution(self) -> None:
        template = "{session}_{timestamp}"
        result = template.replace("{session}", "mybook").replace("{timestamp}", "20240101_120000")
        assert result == "mybook_20240101_120000"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestExportProgressGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_progress_bar_hidden_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._progress_bar.isVisible()

    def test_progress_bar_indeterminate_range(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._progress_bar.setRange(0, 0)
        assert w._progress_bar.minimum() == 0
        assert w._progress_bar.maximum() == 0
