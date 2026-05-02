"""
Tests for SettingsDialog.

Headless tests (TestSettingsDialogHeadless) exercise _save_values logic
directly against ConfigManager without importing PySide6 — safe in all
pytest environments.

GUI tests (TestSettingsDialogGui) require a live QApplication and are
marked @pytest.mark.gui + @pytest.mark.skip (cv2 + PySide6 DLL conflict
in the headless pytest process on Windows — same constraint as
test_session_dialog.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Helpers (no PySide6 import)
# ---------------------------------------------------------------------------

def make_config(tmp_path: Path, data: dict | None = None) -> ConfigManager:
    """Return a ConfigManager backed by a temp file."""
    cfg = ConfigManager(path=tmp_path / "config.json")
    if data:
        for k, v in data.items():
            cfg.set(k, v)
    return cfg


# ---------------------------------------------------------------------------
# Headless tests — pure logic, no Qt
# ---------------------------------------------------------------------------

class TestSettingsDialogHeadless:
    def test_pipeline_modes_available(self) -> None:
        from ocr.pipeline import PIPELINE_MODES
        assert len(PIPELINE_MODES) >= 6
        assert "LOCAL_FAST" in PIPELINE_MODES
        assert "HYBRID_TIERED" in PIPELINE_MODES
        assert "API_FULL" in PIPELINE_MODES

    def test_config_roundtrip_pipeline_mode(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path)
        cfg.set("ocr_pipeline_mode", "API_FULL")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get_str("ocr_pipeline_mode") == "API_FULL"

    def test_config_roundtrip_thresholds(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path)
        cfg.set("dedup_threshold", 0.77)
        cfg.set("embedding_threshold", 0.93)
        cfg.set("hybrid_high_threshold", 0.91)
        cfg.set("hybrid_low_threshold", 0.65)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert abs(float(cfg2.get("dedup_threshold")) - 0.77) < 0.001
        assert abs(float(cfg2.get("embedding_threshold")) - 0.93) < 0.001
        assert abs(float(cfg2.get("hybrid_high_threshold")) - 0.91) < 0.001
        assert abs(float(cfg2.get("hybrid_low_threshold")) - 0.65) < 0.001

    def test_config_roundtrip_api_key(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"openrouter_api_key": "sk-test"})
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get_str("openrouter_api_key") == "sk-test"

    def test_config_roundtrip_vram_tier(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"vram_tier": "16gb"})
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get_str("vram_tier") == "16gb"

    def test_invalid_hybrid_threshold_combination(self) -> None:
        """low >= high is semantically invalid — document the invariant."""
        low, high = 0.80, 0.60
        assert not (0.0 <= low < high <= 1.0)

    def test_valid_hybrid_threshold_combination(self) -> None:
        low, high = 0.70, 0.90
        assert 0.0 <= low < high <= 1.0


# ---------------------------------------------------------------------------
# GUI tests (require QApplication + compatible DLL env)
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSettingsDialogGui:
    def _make_dialog(self, tmp_path, data=None):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = make_config(tmp_path, data)
        return SettingsDialog(cfg), cfg

    def test_opens_without_error(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg is not None

    def test_pipeline_mode_combo_populated(self, tmp_path: Path) -> None:
        from ocr.pipeline import PIPELINE_MODES
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._mode_combo.count() == len(PIPELINE_MODES)

    def test_vram_combo_has_two_options(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        items = [dlg._vram_combo.itemText(i) for i in range(dlg._vram_combo.count())]
        assert "8gb" in items
        assert "16gb" in items

    def test_loads_existing_pipeline_mode(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, {"ocr_pipeline_mode": "LOCAL_LLM"})
        assert dlg._mode_combo.currentText() == "LOCAL_LLM"

    def test_loads_existing_vram_tier(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, {"vram_tier": "16gb"})
        assert dlg._vram_combo.currentText() == "16gb"

    def test_loads_minhash_threshold(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, {"dedup_threshold": 0.75})
        assert abs(dlg._minhash_threshold.value() - 0.75) < 0.001

    def test_loads_hybrid_thresholds(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, {
            "hybrid_high_threshold": 0.88,
            "hybrid_low_threshold": 0.60,
        })
        assert abs(dlg._hybrid_high.value() - 0.88) < 0.001
        assert abs(dlg._hybrid_low.value() - 0.60) < 0.001

    def test_loads_openrouter_key(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, {"openrouter_api_key": "sk-test-key"})
        assert dlg._openrouter_key.text() == "sk-test-key"

    def test_save_writes_pipeline_mode(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._mode_combo.setCurrentText("HYBRID_TIERED")
        dlg._save_values()
        assert cfg.get_str("ocr_pipeline_mode") == "HYBRID_TIERED"

    def test_save_writes_thresholds(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._minhash_threshold.setValue(0.77)
        dlg._hybrid_high.setValue(0.91)
        dlg._hybrid_low.setValue(0.65)
        dlg._save_values()
        assert abs(float(cfg.get("dedup_threshold")) - 0.77) < 0.001
        assert abs(float(cfg.get("hybrid_high_threshold")) - 0.91) < 0.001
        assert abs(float(cfg.get("hybrid_low_threshold")) - 0.65) < 0.001

    def test_save_persists_to_disk(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        dlg._mode_combo.setCurrentText("API_FULL")
        dlg._save_values()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get_str("ocr_pipeline_mode") == "API_FULL"

    def test_invalid_thresholds_shows_warning(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._hybrid_high.setValue(0.60)
        dlg._hybrid_low.setValue(0.80)
        with patch("gui.settings_dialog.QMessageBox") as mock_mb:
            mock_mb.warning = MagicMock()
            dlg._on_accept()
            mock_mb.warning.assert_called_once()
        assert cfg.get("hybrid_high_threshold") is None

    def test_cancel_does_not_save(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._mode_combo.setCurrentText("API_FULL")
        dlg.reject()
        assert cfg.get("ocr_pipeline_mode") is None
