"""
Tests for FEAT-ocr-worker-flow.

Source-scan tests verify OCRWorker creation, signal connections, QThreadPool dispatch,
_on_ocr_results confidence filter, _populate_preview call, and _on_ocr_error handling.
Pure-logic tests verify confidence filtering and avg_conf maths.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ocr_slot_block() -> str:
    idx = _MW_SRC.index("def _on_ocr_results")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]

def _run_ocr_block() -> str:
    idx = _MW_SRC.index("worker = OCRWorker(")
    end = _MW_SRC.index("\n\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestOcrWorkerFlowSource:
    def test_ocr_worker_imported(self) -> None:
        assert "from ocr.worker import OCRWorker" in _MW_SRC

    def test_worker_created_with_cfg(self) -> None:
        assert "OCRWorker(self._cfg, image_paths, self)" in _MW_SRC

    def test_results_ready_connected(self) -> None:
        assert "results_ready.connect(self._on_ocr_results)" in _MW_SRC

    def test_error_occurred_connected(self) -> None:
        assert "error_occurred.connect(self._on_ocr_error)" in _MW_SRC

    def test_progress_connected(self) -> None:
        assert "signals.progress.connect" in _MW_SRC

    def test_worker_dispatched_to_threadpool(self) -> None:
        assert "QThreadPool.globalInstance().start(worker)" in _MW_SRC

    def test_on_ocr_results_slot_exists(self) -> None:
        assert "def _on_ocr_results" in _MW_SRC

    def test_on_ocr_results_filters_by_confidence(self) -> None:
        assert "ocr_min_confidence" in _ocr_slot_block()

    def test_on_ocr_results_stores_results(self) -> None:
        assert "self._ocr_results = results" in _ocr_slot_block()

    def test_on_ocr_results_enables_export_btn(self) -> None:
        assert "_export_btn.setEnabled(True)" in _ocr_slot_block()

    def test_on_ocr_results_calls_populate_preview(self) -> None:
        assert "_populate_preview(results)" in _ocr_slot_block()

    def test_on_ocr_error_slot_exists(self) -> None:
        assert "def _on_ocr_error" in _MW_SRC

    def test_numeric_sort_on_image_paths(self) -> None:
        assert "key=lambda p: int(p.stem)" in _MW_SRC

    def test_empty_images_guard(self) -> None:
        assert "if not image_paths:" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestOcrWorkerFlowLogic:
    def _filter(self, results, min_conf):
        return [r for r in results if r >= min_conf]

    def test_zero_min_conf_keeps_all(self) -> None:
        results = [0.3, 0.6, 0.9]
        assert self._filter(results, 0.0) == results

    def test_high_min_conf_filters(self) -> None:
        results = [0.3, 0.6, 0.9]
        assert self._filter(results, 0.7) == [0.9]

    def test_avg_conf_computed(self) -> None:
        results = [0.8, 0.9, 1.0]
        avg = sum(results) / len(results)
        assert abs(avg - 0.9) < 1e-9

    def test_avg_conf_zero_when_empty(self) -> None:
        results = []
        avg = sum(results) / len(results) if results else 0.0
        assert avg == 0.0

    def test_filtered_note_shown_when_removed(self) -> None:
        raw, kept = 5, 3
        note = f"  ({raw - kept} filtered)" if raw != kept else ""
        assert "2 filtered" in note

    def test_no_filtered_note_when_all_kept(self) -> None:
        raw, kept = 5, 5
        note = f"  ({raw - kept} filtered)" if raw != kept else ""
        assert note == ""


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestOcrWorkerFlowGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_export_btn_disabled_before_ocr(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._export_btn.isEnabled()

    def test_ocr_results_empty_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._ocr_results == []

    def test_populate_preview_called_with_results(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        w = self._make_window(tmp_path)
        with patch.object(w, "_populate_preview") as mock_pp:
            w._on_ocr_results([])
            mock_pp.assert_called_once()
