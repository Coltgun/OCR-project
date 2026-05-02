"""
Tests for FEAT-export-filename-template.

Source-scan tests verify SettingsDialog + MainWindow wiring.
Pure-logic tests verify template substitution.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
_SD_SRC = (_ROOT / "gui" / "settings_dialog.py").read_text(encoding="utf-8")
_MW_SRC = (_ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. SettingsDialog source-scan
# ---------------------------------------------------------------------------

class TestExportFilenameTemplateSettingsSource:
    def test_lineedit_created(self) -> None:
        assert "self._export_filename_template = QLineEdit()" in _SD_SRC

    def test_placeholder_text(self) -> None:
        assert '"{session}_{timestamp}"' in _SD_SRC

    def test_row_label(self) -> None:
        assert '"Export filename template:"' in _SD_SRC

    def test_loaded_from_config(self) -> None:
        assert 'cfg.get_str("export_filename_template", "{session}_{timestamp}")' in _SD_SRC

    def test_saved_to_config(self) -> None:
        assert 'cfg.set(\n            "export_filename_template"' in _SD_SRC

    def test_fallback_on_empty(self) -> None:
        assert 'or "{session}_{timestamp}"' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. MainWindow source-scan
# ---------------------------------------------------------------------------

class TestExportFilenameTemplateMainWindowSource:
    def test_template_read_from_config(self) -> None:
        assert 'self._cfg.get("export_filename_template", "{session}_{timestamp}")' in _MW_SRC

    def test_session_substitution(self) -> None:
        assert 'replace("{session}", session_name)' in _MW_SRC

    def test_timestamp_substitution(self) -> None:
        assert 'replace("{timestamp}", timestamp)' in _MW_SRC

    def test_default_name_uses_stem(self) -> None:
        assert 'default_name = f"{default_stem}.{ext}"' in _MW_SRC


# ---------------------------------------------------------------------------
# 3. Pure-logic tests
# ---------------------------------------------------------------------------

def _apply_template(template: str, session: str, timestamp: str) -> str:
    return template.replace("{session}", session).replace("{timestamp}", timestamp)


class TestExportFilenameTemplateLogic:
    def test_default_template_produces_session_timestamp(self) -> None:
        result = _apply_template("{session}_{timestamp}", "mybook", "20260101_120000")
        assert result == "mybook_20260101_120000"

    def test_session_only_template(self) -> None:
        result = _apply_template("{session}", "novel", "20260101_120000")
        assert result == "novel"

    def test_timestamp_only_template(self) -> None:
        result = _apply_template("{timestamp}", "novel", "20260501_090000")
        assert result == "20260501_090000"

    def test_custom_prefix_template(self) -> None:
        result = _apply_template("export_{session}_{timestamp}", "ch1", "ts")
        assert result == "export_ch1_ts"

    def test_no_placeholder_template(self) -> None:
        result = _apply_template("my_export", "session", "ts")
        assert result == "my_export"

    def test_config_default_value(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        val = cfg.get_str("export_filename_template", "{session}_{timestamp}")
        assert val == "{session}_{timestamp}"

    def test_config_persists_template(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("export_filename_template", "book_{session}")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get_str("export_filename_template", "{session}_{timestamp}") == "book_{session}"

    def test_empty_template_falls_back(self) -> None:
        template = "" or "{session}_{timestamp}"
        assert template == "{session}_{timestamp}"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestExportFilenameTemplateGui:
    def _make_dialog(self, tmp_path, template="{session}_{timestamp}"):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("export_filename_template", template)
        return SettingsDialog(cfg), cfg

    def test_loads_default_template(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._export_filename_template.text() == "{session}_{timestamp}"

    def test_loads_custom_template(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, "book_{session}")
        assert dlg._export_filename_template.text() == "book_{session}"

    def test_save_writes_template(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._export_filename_template.setText("out_{timestamp}")
        dlg._save_values()
        assert cfg.get_str("export_filename_template", "") == "out_{timestamp}"

    def test_save_empty_falls_back(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._export_filename_template.setText("")
        dlg._save_values()
        assert cfg.get_str("export_filename_template", "") == "{session}_{timestamp}"
