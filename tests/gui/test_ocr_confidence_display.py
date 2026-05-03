"""
Tests for FEAT-ocr-confidence-display.

Source-scan tests verify avg_conf computation and label format in _populate_preview.
Pure-logic tests verify avg confidence maths.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.types import OCRResult


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestConfidenceDisplaySource:
    def _populate_block(self) -> str:
        idx = _MW_SRC.index("def _populate_preview")
        end = _MW_SRC.index("\n    def _clear_preview", idx + 1)
        return _MW_SRC[idx:end]

    def test_avg_conf_computed(self) -> None:
        assert "avg_conf" in self._populate_block()

    def test_avg_conf_uses_sum(self) -> None:
        assert "sum(r.confidence for r in results)" in self._populate_block()

    def test_avg_conf_divides_by_n(self) -> None:
        assert "/ n" in self._populate_block()

    def test_label_includes_avg_conf(self) -> None:
        assert "Avg conf:" in self._populate_block()

    def test_label_formats_two_decimals(self) -> None:
        assert ":.2f" in self._populate_block()

    def test_search_label_also_shows_conf(self) -> None:
        idx = _MW_SRC.index("def _on_search_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "Avg conf:" in block

    def test_search_label_guards_empty(self) -> None:
        idx = _MW_SRC.index("def _on_search_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "if total > 0" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

def _avg_confidence(results: list[OCRResult]) -> float:
    if not results:
        return 0.0
    return sum(r.confidence for r in results) / len(results)


class TestConfidenceDisplayLogic:
    def test_single_result(self) -> None:
        r = OCRResult(text="hello", confidence=0.95)
        assert abs(_avg_confidence([r]) - 0.95) < 1e-9

    def test_two_results_avg(self) -> None:
        r1 = OCRResult(text="a", confidence=0.80)
        r2 = OCRResult(text="b", confidence=0.60)
        assert abs(_avg_confidence([r1, r2]) - 0.70) < 1e-9

    def test_empty_returns_zero(self) -> None:
        assert _avg_confidence([]) == 0.0

    def test_all_perfect_confidence(self) -> None:
        results = [OCRResult(text="x", confidence=1.0) for _ in range(5)]
        assert abs(_avg_confidence(results) - 1.0) < 1e-9

    def test_label_format(self) -> None:
        avg = 0.876543
        label = f"Avg conf: {avg:.2f}"
        assert label == "Avg conf: 0.88"

    def test_label_two_decimal_rounding(self) -> None:
        assert f"{0.994:.2f}" == "0.99"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestConfidenceDisplayGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_populate_sets_conf_label(self, tmp_path) -> None:
        w = self._make_window(tmp_path)
        results = [OCRResult(text="hi", confidence=0.80, image_id="0001")]
        w._populate_preview(results)
        assert "Avg conf:" in w._preview_label.text()

    def test_empty_results_no_conf(self, tmp_path) -> None:
        w = self._make_window(tmp_path)
        w._populate_preview([])
        assert "Avg conf:" not in w._preview_label.text()
