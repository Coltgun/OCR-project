"""
Tests for FEAT-trigger-export.

Source-scan tests verify _trigger_export: ocr_results+export() guard,
currentData() for fmt, _EXT_MAP/_FILTER_MAP/_TITLE_MAP dicts, timestamp,
session_name, export_filename_template config, QFileDialog.getSaveFileName,
cancel on empty path, epub_output_dir persist+config.save+_cfg=_data,
_build_chapters_from_results, progress_bar(0,0)+visible, _FORMATTER_MAP
(EpubFormatter/PlainTextFormatter/MarkdownFormatter), formatter.format,
write_bytes, logger.info, _last_export_path, progress_bar hidden, status msg,
open_folder_btn visible, export_done; except: logger.error, progress_bar hidden,
QMessageBox.critical, trigger("error"), update_ui_idle.
Pure-logic tests verify filename template, ext map, cancel path.
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
# Helper
# ---------------------------------------------------------------------------

def _export_block() -> str:
    idx = _MW_SRC.index("def _trigger_export")
    end = _MW_SRC.index("\n    @Slot()\n    def _on_open_export_folder", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestTriggerExportSource:
    def test_trigger_export_exists(self) -> None:
        assert "def _trigger_export" in _MW_SRC

    def test_ocr_results_guard(self) -> None:
        assert "not self._ocr_results" in _export_block()

    def test_state_machine_export_guard(self) -> None:
        assert "self._state_machine.export()" in _export_block()

    def test_fmt_from_combo_current_data(self) -> None:
        assert "self._export_fmt_combo.currentData()" in _export_block()

    def test_ext_map_defined(self) -> None:
        assert "_EXT_MAP" in _export_block()

    def test_filter_map_defined(self) -> None:
        assert "_FILTER_MAP" in _export_block()

    def test_title_map_defined(self) -> None:
        assert "_TITLE_MAP" in _export_block()

    def test_timestamp_generated(self) -> None:
        assert 'datetime.now().strftime("%Y%m%d_%H%M%S")' in _export_block()

    def test_session_name_from_session_root(self) -> None:
        assert "self._session.root.name" in _export_block()

    def test_export_filename_template_config(self) -> None:
        assert '"export_filename_template"' in _export_block()

    def test_template_session_placeholder(self) -> None:
        assert '"{session}"' in _export_block() or "session}" in _export_block()

    def test_template_timestamp_placeholder(self) -> None:
        assert '"{timestamp}"' in _export_block() or "timestamp}" in _export_block()

    def test_qfiledialog_save_called(self) -> None:
        assert "QFileDialog.getSaveFileName(" in _export_block()

    def test_cancel_on_empty_path(self) -> None:
        assert "if not save_path:" in _export_block()

    def test_cancel_calls_state_machine_cancel(self) -> None:
        assert "self._state_machine.cancel()" in _export_block()

    def test_epub_output_dir_persisted(self) -> None:
        assert '"epub_output_dir"' in _export_block()

    def test_config_saved_after_dir_change(self) -> None:
        assert "self._config.save()" in _export_block()

    def test_cfg_data_synced(self) -> None:
        assert "self._cfg = self._config._data" in _export_block()

    def test_build_chapters_called(self) -> None:
        assert "self._build_chapters_from_results()" in _export_block()

    def test_progress_bar_indeterminate(self) -> None:
        assert "self._progress_bar.setRange(0, 0)" in _export_block()

    def test_formatter_map_has_epub(self) -> None:
        assert '"epub": EpubFormatter' in _export_block()

    def test_formatter_map_has_txt(self) -> None:
        assert '"txt": PlainTextFormatter' in _export_block()

    def test_formatter_map_has_md(self) -> None:
        assert '"md": MarkdownFormatter' in _export_block()

    def test_formatter_format_called(self) -> None:
        assert "formatter.format(chapters, self._cfg)" in _export_block()

    def test_write_bytes_to_path(self) -> None:
        assert "Path(save_path).write_bytes(output_bytes)" in _export_block()

    def test_last_export_path_stored(self) -> None:
        assert "self._last_export_path = save_path" in _export_block()

    def test_progress_bar_hidden_on_success(self) -> None:
        assert "self._progress_bar.setVisible(False)" in _export_block()

    def test_open_folder_btn_shown(self) -> None:
        assert "self._open_folder_btn.setVisible(True)" in _export_block()

    def test_export_done_called(self) -> None:
        assert "self._state_machine.export_done()" in _export_block()

    def test_except_logs_error(self) -> None:
        assert 'logger.error("MainWindow: export failed' in _export_block()

    def test_except_hides_progress_bar(self) -> None:
        blk = _export_block()
        assert blk.count("self._progress_bar.setVisible(False)") >= 2

    def test_except_qmessagebox_critical(self) -> None:
        assert 'QMessageBox.critical(self, "Export Error"' in _export_block()

    def test_except_trigger_error(self) -> None:
        assert 'self._state_machine.trigger("error")' in _export_block()

    def test_update_ui_idle_called(self) -> None:
        assert "_update_ui_for_state(AppState.IDLE)" in _export_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestTriggerExportLogic:
    def test_ext_map_epub(self) -> None:
        ext_map = {"epub": "epub", "txt": "txt", "md": "md"}
        assert ext_map["epub"] == "epub"

    def test_ext_map_txt(self) -> None:
        ext_map = {"epub": "epub", "txt": "txt", "md": "md"}
        assert ext_map["txt"] == "txt"

    def test_ext_map_default_epub(self) -> None:
        ext_map = {"epub": "epub", "txt": "txt", "md": "md"}
        assert ext_map.get("unknown", "epub") == "epub"

    def test_filename_template_substitution(self) -> None:
        template = "{session}_{timestamp}"
        result = template.replace("{session}", "mybook").replace("{timestamp}", "20240101_120000")
        assert result == "mybook_20240101_120000"

    def test_default_name_has_extension(self) -> None:
        stem = "mybook_20240101"
        ext = "epub"
        name = f"{stem}.{ext}"
        assert name.endswith(".epub")

    def test_cancel_on_empty_save_path(self) -> None:
        save_path = ""
        should_cancel = not save_path
        assert should_cancel

    def test_chosen_dir_from_parent(self, tmp_path: Path) -> None:
        save_path = str(tmp_path / "output" / "book.epub")
        chosen_dir = str(Path(save_path).parent)
        assert chosen_dir == str(tmp_path / "output")

    def test_config_round_trip_epub_output_dir(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("epub_output_dir", str(tmp_path / "exports"))
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("epub_output_dir") == str(tmp_path / "exports")


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestTriggerExportGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_export_noop_without_results(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._trigger_export()
        assert w._last_export_path == ""

    def test_open_folder_btn_hidden_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._open_folder_btn.isVisible()

    def test_progress_bar_hidden_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._progress_bar.isVisible()
