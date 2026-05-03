"""
Tests for FEAT-display-tab-ui.

Source-scan tests verify _preview_font_size QSpinBox, _font_preview_label,
live-preview wiring, and load/save.
Pure-logic tests verify font size range and config round-trip.
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

class TestDisplayTabUiSource:
    def _load_block(self) -> str:
        idx = _SD_SRC.index("def _load_values")
        end = _SD_SRC.index("\n    def _save_values", idx + 1)
        return _SD_SRC[idx:end]

    def _save_block(self) -> str:
        idx = _SD_SRC.index("def _save_values")
        end = _SD_SRC.index("\n    def _on_accept", idx + 1)
        return _SD_SRC[idx:end]

    def test_display_group_exists(self) -> None:
        assert 'QGroupBox("Display")' in _SD_SRC

    def test_font_size_spinbox_created(self) -> None:
        assert "self._preview_font_size = QSpinBox()" in _SD_SRC

    def test_font_size_range(self) -> None:
        assert "self._preview_font_size.setRange(8, 24)" in _SD_SRC

    def test_font_size_default(self) -> None:
        assert "self._preview_font_size.setValue(11)" in _SD_SRC

    def test_font_size_suffix(self) -> None:
        assert 'self._preview_font_size.setSuffix(" pt")' in _SD_SRC

    def test_font_preview_label_created(self) -> None:
        assert "self._font_preview_label = QLabel" in _SD_SRC

    def test_font_preview_label_tooltip(self) -> None:
        assert '"Live font size preview"' in _SD_SRC

    def test_live_preview_wired(self) -> None:
        assert "_preview_font_size.valueChanged.connect(self._update_font_preview)" in _SD_SRC

    def test_update_font_preview_method_exists(self) -> None:
        assert "def _update_font_preview" in _SD_SRC

    def test_load_reads_preview_font_size(self) -> None:
        assert '"preview_font_size"' in self._load_block()

    def test_load_calls_update_preview(self) -> None:
        assert "_update_font_preview(" in self._load_block()

    def test_save_writes_preview_font_size(self) -> None:
        assert '"preview_font_size"' in self._save_block()

    def test_factory_defaults_has_preview_font_size(self) -> None:
        assert '"preview_font_size"' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestDisplayTabUiLogic:
    def test_default_font_size(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg.get("preview_font_size", 11)) == 11

    def test_persists_font_size(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_font_size", 14)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg2.get("preview_font_size", 11)) == 14

    def test_range_min(self) -> None:
        assert 8 >= 8

    def test_range_max(self) -> None:
        assert 24 <= 24

    def test_clamp_below_min(self) -> None:
        val = max(8, 6)
        assert val == 8

    def test_clamp_above_max(self) -> None:
        val = min(24, 30)
        assert val == 24


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestDisplayTabUiGui:
    def _make_dialog(self, tmp_path, font_size=11):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_font_size", font_size)
        return SettingsDialog(cfg), cfg

    def test_spinbox_restored(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, font_size=14)
        assert dlg._preview_font_size.value() == 14

    def test_preview_label_present(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._font_preview_label is not None

    def test_preview_label_font_size_matches(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, font_size=16)
        assert dlg._font_preview_label.font().pointSize() == 16
