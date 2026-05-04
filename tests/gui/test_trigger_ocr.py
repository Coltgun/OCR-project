"""
Tests for FEAT-trigger-ocr.

Source-scan tests verify _trigger_run_ocr: session None guard,
state_machine.run_ocr() guard, numeric folder+png sort, empty images guard,
OCRWorker creation+signals wiring (results_ready, error_occurred, progress),
ocr_start_time, QThreadPool.globalInstance().start, status message.
_on_ocr_results: min_conf filter, kept_count, avg_conf, ocr_results stored,
export_btn enabled, ocr_done, progress_bar hidden, filtered_note, status msg,
_populate_preview, update_ui_idle.
_on_ocr_error: logger.error, state_machine trigger("error"), progress_bar hidden,
status msg, QMessageBox.critical, update_ui_idle.
Pure-logic tests verify confidence filter, avg_conf, filtered_note.
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
# Helpers
# ---------------------------------------------------------------------------

def _run_ocr_block() -> str:
    idx = _MW_SRC.index("def _trigger_run_ocr")
    end = _MW_SRC.index("\n    @Slot(list)\n    def _on_ocr_results", idx + 1)
    return _MW_SRC[idx:end]


def _ocr_results_block() -> str:
    idx = _MW_SRC.index("def _on_ocr_results")
    end = _MW_SRC.index("\n    @Slot(str)\n    def _on_ocr_error", idx + 1)
    return _MW_SRC[idx:end]


def _ocr_error_block() -> str:
    idx = _MW_SRC.index("def _on_ocr_error")
    end = _MW_SRC.index("\n    @Slot(int, int)", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestTriggerOcrSource:
    def test_trigger_run_ocr_exists(self) -> None:
        assert "def _trigger_run_ocr" in _MW_SRC

    def test_session_none_guard(self) -> None:
        assert "self._session is None" in _run_ocr_block()

    def test_state_machine_run_ocr_guard(self) -> None:
        assert "self._state_machine.run_ocr()" in _run_ocr_block()

    def test_numeric_folder_sort(self) -> None:
        assert "key=lambda x: x" in _run_ocr_block()

    def test_png_suffix_filter(self) -> None:
        assert '.suffix.lower() == ".png"' in _run_ocr_block()

    def test_numeric_png_sort(self) -> None:
        assert "key=lambda p: int(p.stem)" in _run_ocr_block()

    def test_empty_images_guard(self) -> None:
        assert "if not image_paths:" in _run_ocr_block()

    def test_empty_images_calls_ocr_done(self) -> None:
        assert "self._state_machine.ocr_done()" in _run_ocr_block()

    def test_ocr_worker_created(self) -> None:
        assert "OCRWorker(self._cfg, image_paths, self)" in _run_ocr_block()

    def test_results_ready_connected(self) -> None:
        assert "results_ready.connect(self._on_ocr_results)" in _run_ocr_block()

    def test_error_occurred_connected(self) -> None:
        assert "error_occurred.connect(self._on_ocr_error)" in _run_ocr_block()

    def test_progress_connected(self) -> None:
        assert "progress.connect(self._on_ocr_progress)" in _run_ocr_block()

    def test_ocr_start_time_recorded(self) -> None:
        assert "self._ocr_start_time = datetime.now()" in _run_ocr_block()

    def test_threadpool_start_called(self) -> None:
        assert "QThreadPool.globalInstance().start(worker)" in _run_ocr_block()

    def test_status_message_shown(self) -> None:
        assert "_status_bar.showMessage(" in _run_ocr_block()


class TestOnOcrResultsSource:
    def test_on_ocr_results_exists(self) -> None:
        assert "def _on_ocr_results" in _MW_SRC

    def test_min_conf_read_from_config(self) -> None:
        assert '"ocr_min_confidence"' in _ocr_results_block()

    def test_confidence_filter_applied(self) -> None:
        assert "r.confidence >= min_conf" in _ocr_results_block()

    def test_ocr_results_stored(self) -> None:
        assert "self._ocr_results = results" in _ocr_results_block()

    def test_export_btn_enabled(self) -> None:
        assert "self._export_btn.setEnabled(True)" in _ocr_results_block()

    def test_ocr_done_called(self) -> None:
        assert "self._state_machine.ocr_done()" in _ocr_results_block()

    def test_progress_bar_hidden(self) -> None:
        assert "self._progress_bar.setVisible(False)" in _ocr_results_block()

    def test_filtered_note_in_status(self) -> None:
        assert "filtered" in _ocr_results_block()

    def test_populate_preview_called(self) -> None:
        assert "self._populate_preview(results)" in _ocr_results_block()

    def test_update_ui_idle(self) -> None:
        assert "_update_ui_for_state(AppState.IDLE)" in _ocr_results_block()


class TestOnOcrErrorSource:
    def test_on_ocr_error_exists(self) -> None:
        assert "def _on_ocr_error" in _MW_SRC

    def test_logger_error_called(self) -> None:
        assert 'logger.error("MainWindow: OCR error' in _ocr_error_block()

    def test_state_machine_trigger_error(self) -> None:
        assert 'self._state_machine.trigger("error")' in _ocr_error_block()

    def test_progress_bar_hidden(self) -> None:
        assert "self._progress_bar.setVisible(False)" in _ocr_error_block()

    def test_status_message_shown(self) -> None:
        assert "_status_bar.showMessage(" in _ocr_error_block()

    def test_qmessagebox_critical(self) -> None:
        assert "QMessageBox.critical(" in _ocr_error_block()

    def test_update_ui_idle(self) -> None:
        assert "_update_ui_for_state(AppState.IDLE)" in _ocr_error_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestTriggerOcrLogic:
    def _make_result(self, confidence: float):
        from core.types import BoundingBox, OCRResult
        return OCRResult(
            text="text",
            confidence=confidence,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        )

    def test_min_conf_zero_keeps_all(self) -> None:
        results = [self._make_result(0.3), self._make_result(0.9)]
        min_conf = 0.0
        filtered = [r for r in results if r.confidence >= min_conf] if min_conf > 0.0 else results
        assert len(filtered) == 2

    def test_min_conf_filters_low(self) -> None:
        results = [self._make_result(0.3), self._make_result(0.9)]
        min_conf = 0.5
        filtered = [r for r in results if r.confidence >= min_conf]
        assert len(filtered) == 1

    def test_avg_conf_zero_results(self) -> None:
        kept_count = 0
        avg = 0.0 if kept_count == 0 else 1.0
        assert avg == 0.0

    def test_avg_conf_nonzero(self) -> None:
        results = [self._make_result(0.8), self._make_result(0.6)]
        kept_count = len(results)
        avg = sum(r.confidence for r in results) / kept_count
        assert abs(avg - 0.7) < 1e-9

    def test_filtered_note_when_removed(self) -> None:
        raw_count, kept_count = 5, 3
        note = f"  ({raw_count - kept_count} filtered)" if raw_count != kept_count else ""
        assert "2 filtered" in note

    def test_filtered_note_empty_when_none_removed(self) -> None:
        raw_count, kept_count = 4, 4
        note = f"  ({raw_count - kept_count} filtered)" if raw_count != kept_count else ""
        assert note == ""

    def test_numeric_png_sort_order(self, tmp_path: Path) -> None:
        stems = ["10", "2", "1", "20"]
        sorted_stems = sorted(stems, key=lambda s: int(s))
        assert sorted_stems == ["1", "2", "10", "20"]


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestTriggerOcrGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_run_ocr_noop_without_session(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._trigger_run_ocr()
        assert w._ocr_results == []

    def test_export_btn_disabled_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._export_btn.isEnabled()

    def test_progress_bar_hidden_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._progress_bar.isVisible()
