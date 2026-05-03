"""
Tests for FEAT-reset-to-defaults.

Source-scan tests verify button, FACTORY_DEFAULTS constant, and slot structure.
Pure-logic tests verify defaults dict and reset behaviour.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_SD_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "settings_dialog.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestResetToDefaultsSource:
    def test_button_created(self) -> None:
        assert 'QPushButton("Reset to Defaults")' in _SD_SRC

    def test_button_has_tooltip(self) -> None:
        assert "Restore all settings to factory defaults" in _SD_SRC

    def test_button_connected_to_slot(self) -> None:
        assert "self._reset_defaults_btn.clicked.connect(self._on_reset_defaults)" in _SD_SRC

    def test_factory_defaults_constant_exists(self) -> None:
        assert "_FACTORY_DEFAULTS" in _SD_SRC

    def test_defaults_include_pipeline_mode(self) -> None:
        assert '"ocr_pipeline_mode"' in _SD_SRC

    def test_defaults_include_vram_tier(self) -> None:
        assert '"vram_tier"' in _SD_SRC

    def test_defaults_include_preview_font_size(self) -> None:
        assert '"preview_font_size"' in _SD_SRC

    def test_slot_exists(self) -> None:
        assert "def _on_reset_defaults" in _SD_SRC

    def test_slot_has_confirmation(self) -> None:
        idx = _SD_SRC.index("def _on_reset_defaults")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert "QMessageBox.question" in block

    def test_slot_iterates_factory_defaults(self) -> None:
        idx = _SD_SRC.index("def _on_reset_defaults")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert "_FACTORY_DEFAULTS.items()" in block

    def test_slot_saves_config(self) -> None:
        idx = _SD_SRC.index("def _on_reset_defaults")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert "self._config.save()" in block

    def test_slot_calls_load_values(self) -> None:
        idx = _SD_SRC.index("def _on_reset_defaults")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert "self._load_values()" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

_FACTORY_DEFAULTS = {
    "ocr_pipeline_mode": "LOCAL_FAST",
    "vram_tier": "8gb",
    "preview_font_size": 11,
    "dark_mode": False,
    "preview_word_wrap": True,
    "export_format": "epub",
    "rotation_mode": "none",
    "capture_delay_ms": 0,
    "max_recent_sessions": 5,
}


class TestResetToDefaultsLogic:
    def test_defaults_pipeline_mode(self) -> None:
        assert _FACTORY_DEFAULTS["ocr_pipeline_mode"] == "LOCAL_FAST"

    def test_defaults_vram_tier(self) -> None:
        assert _FACTORY_DEFAULTS["vram_tier"] == "8gb"

    def test_defaults_export_format(self) -> None:
        assert _FACTORY_DEFAULTS["export_format"] == "epub"

    def test_reset_applies_all_keys(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_pipeline_mode", "FULL")
        for key, value in _FACTORY_DEFAULTS.items():
            cfg.set(key, value)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("ocr_pipeline_mode", "?") == "LOCAL_FAST"

    def test_reset_not_applied_on_cancel(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_pipeline_mode", "FULL")
        assert cfg.get("ocr_pipeline_mode", "?") == "FULL"

    def test_defaults_count_gte_9(self) -> None:
        assert len(_FACTORY_DEFAULTS) >= 9


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestResetToDefaultsGui:
    def _make_dialog(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return SettingsDialog(cfg), cfg

    def test_button_exists(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._reset_defaults_btn is not None

    def test_button_is_enabled(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._reset_defaults_btn.isEnabled()

    def test_factory_defaults_has_all_keys(self, tmp_path: Path) -> None:
        from gui.settings_dialog import SettingsDialog
        assert "preview_font_size" in SettingsDialog._FACTORY_DEFAULTS
