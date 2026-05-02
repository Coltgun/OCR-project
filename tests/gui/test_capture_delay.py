"""
Tests for FEAT-capture-delay.

Source-scan tests verify SettingsDialog widget + MainWindow wiring.
Pure-logic tests verify ms↔s conversion and delay condition.
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

class TestCaptureDelaySettingsSource:
    def test_group_box(self) -> None:
        assert '"Capture Delay"' in _SD_SRC

    def test_spinbox_created(self) -> None:
        assert "self._capture_delay = self._make_double_spin(0.0, 5.0, 0.1, 1)" in _SD_SRC

    def test_special_value_text(self) -> None:
        assert 'self._capture_delay.setSpecialValueText("None")' in _SD_SRC

    def test_suffix(self) -> None:
        assert 'self._capture_delay.setSuffix(" s")' in _SD_SRC

    def test_row_label(self) -> None:
        assert '"Delay before grab:"' in _SD_SRC

    def test_loaded_from_config(self) -> None:
        assert 'cfg.get("capture_delay_ms", 0)' in _SD_SRC

    def test_loaded_converts_ms_to_s(self) -> None:
        assert "/ 1000.0" in _SD_SRC

    def test_saved_converts_s_to_ms(self) -> None:
        assert 'int(self._capture_delay.value() * 1000)' in _SD_SRC

    def test_saved_to_config(self) -> None:
        assert 'cfg.set("capture_delay_ms",' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. MainWindow source-scan
# ---------------------------------------------------------------------------

class TestCaptureDelayMainWindowSource:
    def test_time_imported(self) -> None:
        assert "import time" in _MW_SRC

    def test_delay_read_in_trigger_capture(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert 'self._cfg.get("capture_delay_ms", 0)' in block

    def test_delay_divides_by_1000(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "/ 1000.0" in block

    def test_sleep_called_when_positive(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "time.sleep(delay_s)" in block

    def test_guarded_by_positive_check(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "delay_s > 0" in block


# ---------------------------------------------------------------------------
# 3. Pure-logic tests
# ---------------------------------------------------------------------------

def _ms_to_s(ms: float) -> float:
    return ms / 1000.0


def _s_to_ms(s: float) -> int:
    return int(s * 1000)


def _should_sleep(delay_s: float) -> bool:
    return delay_s > 0


class TestCaptureDelayLogic:
    def test_zero_ms_gives_zero_s(self) -> None:
        assert _ms_to_s(0) == 0.0

    def test_500ms_gives_0_5s(self) -> None:
        assert _ms_to_s(500) == 0.5

    def test_5000ms_gives_5s(self) -> None:
        assert _ms_to_s(5000) == 5.0

    def test_0_5s_gives_500ms(self) -> None:
        assert _s_to_ms(0.5) == 500

    def test_no_sleep_when_zero(self) -> None:
        assert not _should_sleep(0.0)

    def test_sleep_when_positive(self) -> None:
        assert _should_sleep(0.1)

    def test_config_default_zero(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert float(cfg.get("capture_delay_ms", 0)) == 0.0

    def test_config_persists_500(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("capture_delay_ms", 500)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg2.get("capture_delay_ms", 0)) == 500


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestCaptureDelayGui:
    def _make_dialog(self, tmp_path, delay_ms=0):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("capture_delay_ms", delay_ms)
        return SettingsDialog(cfg), cfg

    def test_default_zero(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._capture_delay.value() == 0.0

    def test_loads_500ms_as_0_5s(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, 500)
        assert dlg._capture_delay.value() == 0.5

    def test_save_writes_ms(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._capture_delay.setValue(1.0)
        dlg._save_values()
        assert int(cfg.get("capture_delay_ms", 0)) == 1000
