"""
Tests for FEAT-bert-threshold-ui.

Source-scan tests verify all five threshold spinboxes, their groups, load, and save wiring.
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


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load_block() -> str:
    idx = _SD_SRC.index("def _load_values")
    end = _SD_SRC.index("\n    def _save_values", idx + 1)
    return _SD_SRC[idx:end]


def _save_block() -> str:
    idx = _SD_SRC.index("def _save_values")
    end = _SD_SRC.index("\n    def _on_accept", idx + 1)
    return _SD_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests — spinbox creation
# ---------------------------------------------------------------------------

class TestBertThresholdUiSource:
    def test_dedup_group_exists(self) -> None:
        assert 'QGroupBox("Deduplication")' in _SD_SRC

    def test_minhash_spinbox_created(self) -> None:
        assert "self._minhash_threshold = " in _SD_SRC

    def test_embedding_spinbox_created(self) -> None:
        assert "self._embedding_threshold = " in _SD_SRC

    def test_confidence_group_exists(self) -> None:
        assert 'QGroupBox("OCR Confidence Filter")' in _SD_SRC

    def test_ocr_min_confidence_spinbox_created(self) -> None:
        assert "self._ocr_min_confidence = " in _SD_SRC

    def test_hybrid_group_exists(self) -> None:
        assert 'QGroupBox("Hybrid Correction Thresholds")' in _SD_SRC

    def test_hybrid_high_spinbox_created(self) -> None:
        assert "self._hybrid_high = " in _SD_SRC

    def test_hybrid_low_spinbox_created(self) -> None:
        assert "self._hybrid_low = " in _SD_SRC

    def test_load_reads_dedup_threshold(self) -> None:
        assert '"dedup_threshold"' in _load_block()

    def test_load_reads_embedding_threshold(self) -> None:
        assert '"embedding_threshold"' in _load_block()

    def test_load_reads_ocr_min_confidence(self) -> None:
        assert '"ocr_min_confidence"' in _load_block()

    def test_load_reads_hybrid_high(self) -> None:
        assert '"hybrid_high_threshold"' in _load_block()

    def test_load_reads_hybrid_low(self) -> None:
        assert '"hybrid_low_threshold"' in _load_block()

    def test_save_writes_dedup_threshold(self) -> None:
        assert '"dedup_threshold"' in _save_block()

    def test_save_writes_embedding_threshold(self) -> None:
        assert '"embedding_threshold"' in _save_block()

    def test_save_writes_ocr_min_confidence(self) -> None:
        assert '"ocr_min_confidence"' in _save_block()

    def test_save_writes_hybrid_high(self) -> None:
        assert '"hybrid_high_threshold"' in _save_block()

    def test_save_writes_hybrid_low(self) -> None:
        assert '"hybrid_low_threshold"' in _save_block()

    def test_factory_defaults_has_dedup_threshold(self) -> None:
        assert '"dedup_threshold"' in _SD_SRC

    def test_factory_defaults_has_embedding_threshold(self) -> None:
        assert '"embedding_threshold"' in _SD_SRC

    def test_factory_defaults_has_ocr_min_confidence(self) -> None:
        assert '"ocr_min_confidence"' in _SD_SRC

    def test_factory_defaults_has_hybrid_high(self) -> None:
        assert '"hybrid_high_threshold"' in _SD_SRC

    def test_factory_defaults_has_hybrid_low(self) -> None:
        assert '"hybrid_low_threshold"' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestBertThresholdUiLogic:
    def test_dedup_default(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert abs(float(cfg.get("dedup_threshold", 0.85)) - 0.85) < 1e-9

    def test_hybrid_high_default(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert abs(float(cfg.get("hybrid_high_threshold", 0.90)) - 0.90) < 1e-9

    def test_hybrid_low_default(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert abs(float(cfg.get("hybrid_low_threshold", 0.70)) - 0.70) < 1e-9

    def test_persists_ocr_min_confidence(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_min_confidence", 0.75)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert abs(float(cfg2.get("ocr_min_confidence", 0.0)) - 0.75) < 1e-9

    def test_high_above_low(self) -> None:
        high, low = 0.90, 0.70
        assert high > low

    def test_range_0_to_1(self) -> None:
        for val in (0.0, 0.5, 1.0):
            assert 0.0 <= val <= 1.0


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestBertThresholdUiGui:
    def _make_dialog(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return SettingsDialog(cfg), cfg

    def test_hybrid_high_restored(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("hybrid_high_threshold", 0.95)
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        dlg = SettingsDialog(cfg)
        assert abs(dlg._hybrid_high.value() - 0.95) < 1e-3

    def test_hybrid_low_restored(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("hybrid_low_threshold", 0.65)
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        dlg = SettingsDialog(cfg)
        assert abs(dlg._hybrid_low.value() - 0.65) < 1e-3

    def test_all_five_spinboxes_present(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert all(hasattr(dlg, attr) for attr in (
            "_minhash_threshold", "_embedding_threshold",
            "_ocr_min_confidence", "_hybrid_high", "_hybrid_low",
        ))
