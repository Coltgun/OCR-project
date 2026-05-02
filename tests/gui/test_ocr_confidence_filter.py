"""
Tests for FEAT-ocr-confidence-filter.

Source-scan tests verify SettingsDialog Pipeline tab widget + MainWindow filtering.
Pure-logic tests verify filter semantics.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.types import OCRResult
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

class TestConfidenceFilterSettingsSource:
    def test_spinbox_created(self) -> None:
        assert "self._ocr_min_confidence = self._make_double_spin(0.0, 1.0, 0.05, 2)" in _SD_SRC

    def test_spinbox_row_label(self) -> None:
        assert '"Min confidence (discard <):"' in _SD_SRC

    def test_confidence_group_box(self) -> None:
        assert '"OCR Confidence Filter"' in _SD_SRC

    def test_loaded_from_config(self) -> None:
        assert 'cfg.get("ocr_min_confidence", 0.0)' in _SD_SRC

    def test_saved_to_config(self) -> None:
        assert 'cfg.set("ocr_min_confidence", self._ocr_min_confidence.value())' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. MainWindow source-scan
# ---------------------------------------------------------------------------

class TestConfidenceFilterMainWindowSource:
    def test_filter_applied_in_on_ocr_results(self) -> None:
        assert 'min_conf = float(self._cfg.get("ocr_min_confidence", 0.0))' in _MW_SRC

    def test_filter_only_applied_when_positive(self) -> None:
        assert "if min_conf > 0.0:" in _MW_SRC

    def test_filter_uses_confidence_attribute(self) -> None:
        assert "r.confidence >= min_conf" in _MW_SRC

    def test_filtered_results_stored(self) -> None:
        idx = _MW_SRC.index("def _on_ocr_results")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._ocr_results = results" in block


# ---------------------------------------------------------------------------
# 3. Pure-logic tests (no Qt)
# ---------------------------------------------------------------------------

def _r(conf: float) -> OCRResult:
    return OCRResult(text="x", confidence=conf, bbox=(0, 0, 10, 10), image_id="i")


def _apply_filter(results: list[OCRResult], min_conf: float) -> list[OCRResult]:
    """Mirrors the logic in _on_ocr_results."""
    if min_conf > 0.0:
        results = [r for r in results if r.confidence >= min_conf]
    return results


class TestConfidenceFilterLogic:
    def test_zero_threshold_keeps_all(self) -> None:
        results = [_r(0.1), _r(0.5), _r(0.9)]
        assert len(_apply_filter(results, 0.0)) == 3

    def test_threshold_filters_low_confidence(self) -> None:
        results = [_r(0.3), _r(0.7), _r(0.9)]
        filtered = _apply_filter(results, 0.5)
        assert len(filtered) == 2
        assert all(r.confidence >= 0.5 for r in filtered)

    def test_exact_boundary_included(self) -> None:
        results = [_r(0.5)]
        assert len(_apply_filter(results, 0.5)) == 1

    def test_below_boundary_excluded(self) -> None:
        results = [_r(0.49)]
        assert len(_apply_filter(results, 0.5)) == 0

    def test_full_threshold_keeps_only_perfect(self) -> None:
        results = [_r(0.99), _r(1.0), _r(0.5)]
        filtered = _apply_filter(results, 1.0)
        assert len(filtered) == 1
        assert filtered[0].confidence == 1.0

    def test_empty_list_stays_empty(self) -> None:
        assert _apply_filter([], 0.5) == []

    def test_config_default_is_zero(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert float(cfg.get("ocr_min_confidence", 0.0)) == 0.0

    def test_config_persists_threshold(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_min_confidence", 0.6)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert float(cfg2.get("ocr_min_confidence", 0.0)) == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestConfidenceFilterGui:
    def _make_dialog(self, tmp_path, conf=0.0):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_min_confidence", conf)
        return SettingsDialog(cfg), cfg

    def test_spinbox_loads_default(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, 0.0)
        assert dlg._ocr_min_confidence.value() == pytest.approx(0.0)

    def test_spinbox_loads_custom_value(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, 0.6)
        assert dlg._ocr_min_confidence.value() == pytest.approx(0.6)

    def test_spinbox_range_min(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._ocr_min_confidence.minimum() == pytest.approx(0.0)

    def test_spinbox_range_max(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._ocr_min_confidence.maximum() == pytest.approx(1.0)

    def test_save_writes_threshold(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._ocr_min_confidence.setValue(0.75)
        dlg._save_values()
        assert float(cfg.get("ocr_min_confidence", 0.0)) == pytest.approx(0.75)
