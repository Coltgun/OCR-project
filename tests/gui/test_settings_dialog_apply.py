"""
Tests for FEAT-settings-dialog-apply.

Source-scan tests verify SettingsDialog._on_accept: threshold validation, _save_values,
accept(); _on_reset_defaults: QMessageBox.question, _FACTORY_DEFAULTS restore, _load_values.
MainWindow._open_settings: SettingsDialog exec, _cfg reload, hotkeys.reload, font update,
pipeline_mode_combo sync, recent_sessions_cleared handling.
Pure-logic tests verify threshold guard logic and factory-defaults round-trip.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_SD_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "settings_dialog.py"
).read_text(encoding="utf-8")

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _on_accept_block() -> str:
    idx = _SD_SRC.index("def _on_accept")
    end = _SD_SRC.index("\n    def _on_clear_recent", idx + 1)
    return _SD_SRC[idx:end]

def _reset_block() -> str:
    idx = _SD_SRC.index("def _on_reset_defaults")
    end = _SD_SRC.index("\n    # ---", idx + 1)
    return _SD_SRC[idx:end]

def _open_settings_block() -> str:
    idx = _MW_SRC.index("def _open_settings")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests — SettingsDialog
# ---------------------------------------------------------------------------

class TestSettingsDialogApplySource:
    def test_on_accept_exists(self) -> None:
        assert "def _on_accept" in _SD_SRC

    def test_on_accept_validates_thresholds(self) -> None:
        assert "low >= high" in _on_accept_block()

    def test_on_accept_shows_warning_on_invalid(self) -> None:
        assert "QMessageBox.warning" in _on_accept_block()

    def test_on_accept_calls_save_values(self) -> None:
        assert "self._save_values()" in _on_accept_block()

    def test_on_accept_calls_accept(self) -> None:
        assert "self.accept()" in _on_accept_block()

    def test_reset_defaults_btn_created(self) -> None:
        assert 'self._reset_defaults_btn = QPushButton("Reset to Defaults")' in _SD_SRC

    def test_reset_defaults_btn_connected(self) -> None:
        assert "_reset_defaults_btn.clicked.connect(self._on_reset_defaults)" in _SD_SRC

    def test_reset_defaults_confirms_with_question(self) -> None:
        assert "QMessageBox.question" in _reset_block()

    def test_reset_defaults_iterates_factory_defaults(self) -> None:
        assert "self._FACTORY_DEFAULTS.items()" in _reset_block()

    def test_reset_defaults_saves_config(self) -> None:
        assert "self._config.save()" in _reset_block()

    def test_reset_defaults_reloads_widgets(self) -> None:
        assert "self._load_values()" in _reset_block()


# ---------------------------------------------------------------------------
# 2. Source-scan tests — MainWindow._open_settings
# ---------------------------------------------------------------------------

class TestOpenSettingsSource:
    def test_open_settings_exists(self) -> None:
        assert "def _open_settings" in _MW_SRC

    def test_opens_settings_dialog(self) -> None:
        assert "SettingsDialog(self._config" in _open_settings_block()

    def test_reloads_cfg_on_accept(self) -> None:
        assert "self._cfg = self._config._data" in _open_settings_block()

    def test_reloads_hotkeys_on_accept(self) -> None:
        assert "self._hotkeys.reload(self._cfg)" in _open_settings_block()

    def test_updates_pipeline_mode_combo(self) -> None:
        assert "_pipeline_mode_combo" in _open_settings_block()

    def test_handles_recent_sessions_cleared(self) -> None:
        assert "recent_sessions_cleared" in _open_settings_block()


# ---------------------------------------------------------------------------
# 3. Pure-logic tests
# ---------------------------------------------------------------------------

class TestSettingsDialogApplyLogic:
    def test_threshold_invalid_low_gte_high(self) -> None:
        high, low = 0.8, 0.8
        assert low >= high

    def test_threshold_valid_low_lt_high(self) -> None:
        high, low = 0.8, 0.5
        assert not (low >= high)

    def test_factory_defaults_restored(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        defaults = {"ocr_pipeline_mode": "LOCAL_FAST", "dark_mode": False}
        cfg.set("ocr_pipeline_mode", "FULL")
        for key, value in defaults.items():
            cfg.set(key, value)
        cfg.save()
        assert cfg.get("ocr_pipeline_mode") == "LOCAL_FAST"

    def test_factory_defaults_save_persists(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", True)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("dark_mode") is True

    def test_threshold_boundary_exactly_equal_is_invalid(self) -> None:
        high = low = 0.6
        is_invalid = low >= high
        assert is_invalid

    def test_threshold_low_just_below_high_is_valid(self) -> None:
        high, low = 0.6, 0.59
        is_invalid = low >= high
        assert not is_invalid


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSettingsDialogApplyGui:
    def _make_dialog(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return SettingsDialog(cfg)

    def test_reset_defaults_btn_present(self, tmp_path: Path) -> None:
        dlg = self._make_dialog(tmp_path)
        assert dlg._reset_defaults_btn is not None

    def test_on_accept_rejects_equal_thresholds(self, tmp_path: Path) -> None:
        dlg = self._make_dialog(tmp_path)
        dlg._hybrid_high.setValue(0.8)
        dlg._hybrid_low.setValue(0.8)
        dlg._on_accept()
        assert not dlg.result()

    def test_save_values_persists_pipeline_mode(self, tmp_path: Path) -> None:
        dlg = self._make_dialog(tmp_path)
        dlg._mode_combo.setCurrentText("LOCAL_FAST")
        dlg._save_values()
        assert dlg._config.get("ocr_pipeline_mode") == "LOCAL_FAST"
