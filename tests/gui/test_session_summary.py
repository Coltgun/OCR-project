"""
Tests for FEAT-session-summary.

Source-scan tests verify the enriched status bar message logic.
Pure-logic tests verify summary computation.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.types import OCRResult
from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestSessionSummarySource:
    def test_raw_count_captured(self) -> None:
        assert "raw_count = len(results)" in _MW_SRC

    def test_kept_count_captured(self) -> None:
        assert "kept_count = len(results)" in _MW_SRC

    def test_avg_conf_computed(self) -> None:
        assert "avg_conf" in _MW_SRC

    def test_avg_conf_guarded_empty(self) -> None:
        assert "if kept_count > 0" in _MW_SRC

    def test_avg_conf_zero_on_empty(self) -> None:
        assert "else 0.0" in _MW_SRC

    def test_filtered_note_present(self) -> None:
        assert "filtered_note" in _MW_SRC

    def test_filtered_note_only_when_different(self) -> None:
        assert "if raw_count != kept_count" in _MW_SRC

    def test_status_bar_shows_kept_count(self) -> None:
        assert "kept_count} block(s) kept" in _MW_SRC

    def test_status_bar_shows_avg_confidence(self) -> None:
        assert "avg confidence: {avg_conf:.2f}" in _MW_SRC

    def test_status_bar_shows_filtered_note(self) -> None:
        assert "{filtered_note}" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests (no Qt)
# ---------------------------------------------------------------------------

def _r(conf: float) -> OCRResult:
    return OCRResult(text="x", confidence=conf, bbox=(0, 0, 10, 10), image_id="i")


def _summary(raw: list[OCRResult], min_conf: float) -> dict:
    """Mirrors the logic in _on_ocr_results."""
    raw_count = len(raw)
    if min_conf > 0.0:
        kept = [r for r in raw if r.confidence >= min_conf]
    else:
        kept = list(raw)
    kept_count = len(kept)
    avg_conf = sum(r.confidence for r in kept) / kept_count if kept_count > 0 else 0.0
    filtered_note = f"  ({raw_count - kept_count} filtered)" if raw_count != kept_count else ""
    msg = f"OCR complete: {kept_count} block(s) kept{filtered_note}  |  avg confidence: {avg_conf:.2f}"
    return {"raw": raw_count, "kept": kept_count, "avg": avg_conf, "msg": msg}


class TestSessionSummaryLogic:
    def test_no_filter_kept_equals_raw(self) -> None:
        s = _summary([_r(0.5), _r(0.8)], 0.0)
        assert s["kept"] == 2
        assert s["raw"] == 2

    def test_filter_reduces_kept(self) -> None:
        s = _summary([_r(0.3), _r(0.7), _r(0.9)], 0.5)
        assert s["kept"] == 2

    def test_avg_confidence_correct(self) -> None:
        s = _summary([_r(0.6), _r(0.8)], 0.0)
        assert abs(s["avg"] - 0.7) < 1e-9

    def test_avg_zero_on_empty(self) -> None:
        s = _summary([], 0.5)
        assert s["avg"] == 0.0

    def test_no_filtered_note_when_no_filter(self) -> None:
        s = _summary([_r(0.5)], 0.0)
        assert "filtered" not in s["msg"]

    def test_filtered_note_appears_when_some_dropped(self) -> None:
        s = _summary([_r(0.3), _r(0.8)], 0.5)
        assert "1 filtered" in s["msg"]

    def test_msg_contains_avg_confidence(self) -> None:
        s = _summary([_r(0.75)], 0.0)
        assert "avg confidence: 0.75" in s["msg"]

    def test_msg_contains_kept_count(self) -> None:
        s = _summary([_r(0.5), _r(0.9)], 0.0)
        assert "2 block(s) kept" in s["msg"]

    def test_all_filtered_shows_zero_kept(self) -> None:
        s = _summary([_r(0.1), _r(0.2)], 0.9)
        assert s["kept"] == 0
        assert "0 block(s) kept" in s["msg"]

    def test_avg_formatted_two_decimals(self) -> None:
        s = _summary([_r(1.0 / 3)], 0.0)
        assert "avg confidence: 0.33" in s["msg"]


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSessionSummaryGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_status_bar_shows_kept_count(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        results = [_r(0.9), _r(0.8)]
        w._on_ocr_results(results)
        assert "2 block(s) kept" in w._status_bar.currentMessage()

    def test_status_bar_shows_avg_confidence(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._on_ocr_results([_r(1.0)])
        assert "avg confidence: 1.00" in w._status_bar.currentMessage()

    def test_status_bar_shows_filtered_note(self, tmp_path: Path) -> None:
        from utils.config_manager import ConfigManager
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_min_confidence", 0.5)
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow(cfg)
        w._on_ocr_results([_r(0.3), _r(0.9)])
        assert "filtered" in w._status_bar.currentMessage()
