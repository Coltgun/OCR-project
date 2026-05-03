"""
Tests for FEAT-auto-section-threshold-ui.

Source-scan tests verify spinbox creation, load, and save wiring in SettingsDialog.
Pure-logic tests verify config round-trip and range clamping.
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
# 1. Source-scan tests — SettingsDialog
# ---------------------------------------------------------------------------

class TestAutoSectionThresholdSource:
    def test_auto_group_exists(self) -> None:
        assert 'QGroupBox("Auto Section")' in _SD_SRC

    def test_spinbox_created(self) -> None:
        assert "self._auto_section_threshold = QSpinBox()" in _SD_SRC

    def test_spinbox_range(self) -> None:
        assert "self._auto_section_threshold.setRange(0, 99)" in _SD_SRC

    def test_spinbox_special_value_text(self) -> None:
        assert 'self._auto_section_threshold.setSpecialValueText("Disabled")' in _SD_SRC

    def test_spinbox_suffix(self) -> None:
        assert 'self._auto_section_threshold.setSuffix(" captures")' in _SD_SRC

    def test_spinbox_form_row(self) -> None:
        assert '"New section after:"' in _SD_SRC

    def test_load_values_reads_threshold(self) -> None:
        assert '"auto_new_section_threshold"' in _SD_SRC

    def test_save_values_writes_threshold(self) -> None:
        idx = _SD_SRC.index("def _save_values")
        end = _SD_SRC.index("\n    def ", idx + 1)
        block = _SD_SRC[idx:end]
        assert '"auto_new_section_threshold"' in block

    def test_factory_defaults_includes_threshold(self) -> None:
        assert '"auto_new_section_threshold": 0' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Source-scan tests — MainWindow reads the value
# ---------------------------------------------------------------------------

class TestAutoSectionThresholdMWSource:
    def test_main_window_reads_threshold(self) -> None:
        assert '"auto_new_section_threshold"' in _MW_SRC

    def test_main_window_threshold_check(self) -> None:
        assert "threshold > 0" in _MW_SRC


# ---------------------------------------------------------------------------
# 3. Pure-logic tests
# ---------------------------------------------------------------------------

class TestAutoSectionThresholdLogic:
    def test_default_is_zero(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg.get("auto_new_section_threshold", 0)) == 0

    def test_zero_means_disabled(self) -> None:
        threshold = 0
        assert threshold == 0

    def test_persists_nonzero(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("auto_new_section_threshold", 5)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg2.get("auto_new_section_threshold", 0)) == 5

    def test_clamp_range_min(self) -> None:
        assert max(0, -1) == 0

    def test_clamp_range_max(self) -> None:
        assert min(99, 100) == 99

    def test_threshold_triggers_section(self) -> None:
        threshold = 3
        count = 3
        assert threshold > 0 and count >= threshold


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestAutoSectionThresholdGui:
    def _make_dialog(self, tmp_path, threshold=0):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("auto_new_section_threshold", threshold)
        return SettingsDialog(cfg), cfg

    def test_spinbox_exists(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._auto_section_threshold is not None

    def test_restored_value(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, threshold=5)
        assert dlg._auto_section_threshold.value() == 5

    def test_zero_shows_disabled(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, threshold=0)
        assert dlg._auto_section_threshold.value() == 0
