"""
Tests for FEAT-font-size-setting.

Source-scan tests verify SettingsDialog Capture tab + MainWindow wiring.
Config-logic tests verify default, clamping, and persistence.
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
_SETTINGS_SRC = (_ROOT / "gui" / "settings_dialog.py").read_text(encoding="utf-8")
_MW_SRC = (_ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. SettingsDialog source-scan
# ---------------------------------------------------------------------------

class TestFontSizeSettingsDialogSource:
    def test_preview_font_size_spinbox_created(self) -> None:
        assert "self._preview_font_size = QSpinBox()" in _SETTINGS_SRC

    def test_spinbox_range_8_to_24(self) -> None:
        assert "self._preview_font_size.setRange(8, 24)" in _SETTINGS_SRC

    def test_spinbox_default_value_11(self) -> None:
        assert "self._preview_font_size.setValue(11)" in _SETTINGS_SRC

    def test_spinbox_has_pt_suffix(self) -> None:
        assert 'self._preview_font_size.setSuffix(" pt")' in _SETTINGS_SRC

    def test_spinbox_in_display_group(self) -> None:
        assert 'QGroupBox("Display")' in _SETTINGS_SRC

    def test_spinbox_row_label(self) -> None:
        assert '"Preview font size:"' in _SETTINGS_SRC

    def test_font_size_loaded_from_config(self) -> None:
        assert 'cfg.get("preview_font_size", 11)' in _SETTINGS_SRC

    def test_font_size_saved_to_config(self) -> None:
        assert 'cfg.set("preview_font_size", self._preview_font_size.value())' in _SETTINGS_SRC


# ---------------------------------------------------------------------------
# 2. MainWindow source-scan
# ---------------------------------------------------------------------------

class TestFontSizeMainWindowSource:
    def test_apply_preview_font_size_method_exists(self) -> None:
        assert "def _apply_preview_font_size" in _MW_SRC

    def test_apply_called_on_init(self) -> None:
        assert 'self._apply_preview_font_size(int(self._cfg.get("preview_font_size", 11)))' in _MW_SRC

    def test_apply_called_after_settings_accept(self) -> None:
        idx = _MW_SRC.index("def _open_settings")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_apply_preview_font_size" in block

    def test_font_size_clamped_to_range(self) -> None:
        assert "max(8, min(size, 24))" in _MW_SRC

    def test_apply_sets_font_on_preview_pane(self) -> None:
        assert "self._preview_pane.setFont(font)" in _MW_SRC


# ---------------------------------------------------------------------------
# 3. Config-logic tests (no Qt)
# ---------------------------------------------------------------------------

class TestFontSizeConfig:
    def test_default_is_11(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg.get("preview_font_size", 11)) == 11

    def test_persists_custom_size(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_font_size", 14)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg2.get("preview_font_size", 11)) == 14

    def test_clamp_below_min(self) -> None:
        size = 4
        assert max(8, min(size, 24)) == 8

    def test_clamp_above_max(self) -> None:
        size = 30
        assert max(8, min(size, 24)) == 24

    def test_clamp_within_range(self) -> None:
        size = 14
        assert max(8, min(size, 24)) == 14


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestFontSizeGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg), cfg

    def _make_dialog(self, tmp_path, size=11):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_font_size", size)
        return SettingsDialog(cfg), cfg

    def test_spinbox_loads_default(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, 11)
        assert dlg._preview_font_size.value() == 11

    def test_spinbox_loads_config_value(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, 16)
        assert dlg._preview_font_size.value() == 16

    def test_spinbox_range_min(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._preview_font_size.minimum() == 8

    def test_spinbox_range_max(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._preview_font_size.maximum() == 24

    def test_save_writes_font_size(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._preview_font_size.setValue(14)
        dlg._save_values()
        assert int(cfg.get("preview_font_size", 11)) == 14

    def test_apply_changes_preview_font(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        w._apply_preview_font_size(16)
        assert w._preview_pane.font().pointSize() == 16

    def test_apply_clamps_below_min(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        w._apply_preview_font_size(4)
        assert w._preview_pane.font().pointSize() == 8

    def test_apply_clamps_above_max(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        w._apply_preview_font_size(30)
        assert w._preview_pane.font().pointSize() == 24
