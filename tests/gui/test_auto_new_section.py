"""
Tests for FEAT-auto-new-section.

Source-scan tests verify SettingsDialog + MainWindow wiring.
Pure-logic tests verify threshold semantics.
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

class TestAutoNewSectionSettingsSource:
    def test_spinbox_created(self) -> None:
        assert "self._auto_section_threshold = QSpinBox()" in _SD_SRC

    def test_range_0_to_99(self) -> None:
        assert "self._auto_section_threshold.setRange(0, 99)" in _SD_SRC

    def test_default_zero(self) -> None:
        assert "self._auto_section_threshold.setValue(0)" in _SD_SRC

    def test_special_value_text_disabled(self) -> None:
        assert 'self._auto_section_threshold.setSpecialValueText("Disabled")' in _SD_SRC

    def test_suffix_captures(self) -> None:
        assert 'self._auto_section_threshold.setSuffix(" captures")' in _SD_SRC

    def test_row_label(self) -> None:
        assert '"New section after:"' in _SD_SRC

    def test_group_box(self) -> None:
        assert '"Auto Section"' in _SD_SRC

    def test_loaded_from_config(self) -> None:
        assert 'cfg.get("auto_new_section_threshold", 0)' in _SD_SRC

    def test_saved_to_config(self) -> None:
        assert 'cfg.set("auto_new_section_threshold", self._auto_section_threshold.value())' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. MainWindow source-scan
# ---------------------------------------------------------------------------

class TestAutoNewSectionMainWindowSource:
    def test_threshold_read_in_trigger_capture(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert 'self._cfg.get("auto_new_section_threshold", 0)' in block

    def test_guard_threshold_positive(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "threshold > 0" in block

    def test_checks_image_count_vs_threshold(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "image_count(self._session.current_folder) >= threshold" in block

    def test_calls_trigger_new_section(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._trigger_new_section()" in block


# ---------------------------------------------------------------------------
# 3. Pure-logic tests
# ---------------------------------------------------------------------------

def _should_auto_advance(threshold: int, current_count: int) -> bool:
    """Mirrors the auto-advance condition in _trigger_capture."""
    return threshold > 0 and current_count >= threshold


class TestAutoNewSectionLogic:
    def test_disabled_when_zero(self) -> None:
        assert not _should_auto_advance(0, 10)

    def test_triggers_at_exact_threshold(self) -> None:
        assert _should_auto_advance(5, 5)

    def test_triggers_above_threshold(self) -> None:
        assert _should_auto_advance(5, 6)

    def test_does_not_trigger_below_threshold(self) -> None:
        assert not _should_auto_advance(5, 4)

    def test_disabled_with_zero_count(self) -> None:
        assert not _should_auto_advance(0, 0)

    def test_threshold_one_triggers_after_first_capture(self) -> None:
        assert _should_auto_advance(1, 1)

    def test_config_default_is_zero(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg.get("auto_new_section_threshold", 0)) == 0

    def test_config_persists_threshold(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("auto_new_section_threshold", 10)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg2.get("auto_new_section_threshold", 0)) == 10


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestAutoNewSectionGui:
    def _make_dialog(self, tmp_path, threshold=0):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("auto_new_section_threshold", threshold)
        return SettingsDialog(cfg), cfg

    def test_spinbox_loads_default(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._auto_section_threshold.value() == 0

    def test_spinbox_loads_custom(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, 5)
        assert dlg._auto_section_threshold.value() == 5

    def test_save_writes_threshold(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._auto_section_threshold.setValue(8)
        dlg._save_values()
        assert int(cfg.get("auto_new_section_threshold", 0)) == 8

    def test_range_max(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._auto_section_threshold.maximum() == 99
