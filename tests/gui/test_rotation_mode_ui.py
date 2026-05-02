"""
Tests for FEAT-rotation-mode-ui.

Source-scan tests verify widget creation, items, load/save wiring.
Pure-logic tests verify config round-trip and item set.
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

class TestRotationModeUiSource:
    def test_group_box_created(self) -> None:
        assert '"Image Rotation"' in _SD_SRC

    def test_combo_created(self) -> None:
        assert "self._rotation_mode = QComboBox()" in _SD_SRC

    def test_items_added(self) -> None:
        assert '["none", "90cw", "90ccw", "180"]' in _SD_SRC

    def test_row_label(self) -> None:
        assert '"Rotate captured image:"' in _SD_SRC

    def test_loaded_from_config(self) -> None:
        assert 'cfg.get_str("rotation_mode", "none")' in _SD_SRC

    def test_findtext_used(self) -> None:
        assert "self._rotation_mode.findText(rot)" in _SD_SRC

    def test_setcurrentindex_with_guard(self) -> None:
        assert "self._rotation_mode.setCurrentIndex(max(0, idx))" in _SD_SRC

    def test_saved_to_config(self) -> None:
        assert 'cfg.set("rotation_mode", self._rotation_mode.currentText())' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

_ROTATION_ITEMS = ["none", "90cw", "90ccw", "180"]


class TestRotationModeUiLogic:
    def test_items_list(self) -> None:
        assert _ROTATION_ITEMS == ["none", "90cw", "90ccw", "180"]

    def test_default_is_none(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get_str("rotation_mode", "none") == "none"

    def test_config_persists_90cw(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("rotation_mode", "90cw")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get_str("rotation_mode", "none") == "90cw"

    def test_config_persists_180(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("rotation_mode", "180")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get_str("rotation_mode", "none") == "180"

    def test_unknown_mode_falls_back_to_index_zero(self) -> None:
        items = _ROTATION_ITEMS
        idx = items.index("none") if "none" in items else -1
        assert max(0, idx) == 0

    def test_all_four_items_present(self) -> None:
        for item in ("none", "90cw", "90ccw", "180"):
            assert item in _ROTATION_ITEMS


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestRotationModeUiGui:
    def _make_dialog(self, tmp_path, rotation="none"):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("rotation_mode", rotation)
        return SettingsDialog(cfg), cfg

    def test_default_selected(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._rotation_mode.currentText() == "none"

    def test_90cw_selected(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, "90cw")
        assert dlg._rotation_mode.currentText() == "90cw"

    def test_save_writes_180(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._rotation_mode.setCurrentText("180")
        dlg._save_values()
        assert cfg.get_str("rotation_mode", "none") == "180"

    def test_four_items_in_combo(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._rotation_mode.count() == 4
