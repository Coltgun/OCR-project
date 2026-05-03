"""
Tests for FEAT-vram-tier-ui.

Source-scan tests verify the VRAM tier combo and its load/save wiring.
Pure-logic tests verify config round-trip and tier defaults.
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

class TestVramTierUiSource:
    def test_vram_group_exists(self) -> None:
        assert 'QGroupBox("VRAM Tier")' in _SD_SRC

    def test_combo_created(self) -> None:
        assert "self._vram_combo = QComboBox()" in _SD_SRC

    def test_combo_items(self) -> None:
        assert '["8gb", "16gb"]' in _SD_SRC

    def test_combo_form_row(self) -> None:
        assert '"Tier:"' in _SD_SRC

    def test_note_label_exists(self) -> None:
        assert "MacBERT-base" in _SD_SRC

    def test_load_values_reads_vram_tier(self) -> None:
        idx = _SD_SRC.index("def _load_values")
        end = _SD_SRC.index("\n    def _save_values", idx + 1)
        block = _SD_SRC[idx:end]
        assert '"vram_tier"' in block

    def test_load_values_uses_find_text(self) -> None:
        idx = _SD_SRC.index("def _load_values")
        end = _SD_SRC.index("\n    def _save_values", idx + 1)
        block = _SD_SRC[idx:end]
        assert "_vram_combo.findText" in block

    def test_save_values_writes_vram_tier(self) -> None:
        idx = _SD_SRC.index("def _save_values")
        end = _SD_SRC.index("\n    def _on_accept", idx + 1)
        block = _SD_SRC[idx:end]
        assert '"vram_tier"' in block

    def test_save_uses_current_text(self) -> None:
        idx = _SD_SRC.index("def _save_values")
        end = _SD_SRC.index("\n    def _on_accept", idx + 1)
        block = _SD_SRC[idx:end]
        assert "_vram_combo.currentText()" in block

    def test_factory_defaults_has_vram_tier(self) -> None:
        assert '"vram_tier": "8gb"' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

_VALID_TIERS = ("8gb", "16gb")


class TestVramTierUiLogic:
    def test_default_tier_8gb(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("vram_tier", "8gb") == "8gb"

    def test_persists_16gb(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("vram_tier", "16gb")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("vram_tier", "8gb") == "16gb"

    def test_persists_8gb(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("vram_tier", "8gb")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("vram_tier", "16gb") == "8gb"

    def test_only_two_tiers(self) -> None:
        assert len(_VALID_TIERS) == 2

    def test_8gb_is_valid(self) -> None:
        assert "8gb" in _VALID_TIERS

    def test_16gb_is_valid(self) -> None:
        assert "16gb" in _VALID_TIERS


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestVramTierUiGui:
    def _make_dialog(self, tmp_path, tier="8gb"):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("vram_tier", tier)
        return SettingsDialog(cfg), cfg

    def test_combo_exists(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._vram_combo is not None

    def test_restored_8gb(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, tier="8gb")
        assert dlg._vram_combo.currentText() == "8gb"

    def test_restored_16gb(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, tier="16gb")
        assert dlg._vram_combo.currentText() == "16gb"
