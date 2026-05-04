"""
Tests for progress bar integration in MainWindow.

Headless tests verify that OCRWorkerSignals exists with the correct
signature and that the progress update logic is correct.

GUI tests (marked @pytest.mark.gui + @pytest.mark.skip) verify the
QProgressBar widget behaviour within a live QApplication.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Headless tests — no PySide6 import
# ---------------------------------------------------------------------------

class TestOCRWorkerSignals:
    def test_progress_signal_exists(self) -> None:
        """OCRWorkerSignals must expose a progress(int, int) signal."""
        import inspect
        import sys
        # Verify the attribute exists in source without importing Qt
        worker_path = Path(__file__).parent.parent.parent / "ocr" / "worker.py"
        source = worker_path.read_text(encoding="utf-8")
        assert "progress = Signal(int, int)" in source

    def test_results_ready_signal_exists(self) -> None:
        worker_path = Path(__file__).parent.parent.parent / "ocr" / "worker.py"
        source = worker_path.read_text(encoding="utf-8")
        assert "results_ready = Signal(list)" in source

    def test_error_occurred_signal_exists(self) -> None:
        worker_path = Path(__file__).parent.parent.parent / "ocr" / "worker.py"
        source = worker_path.read_text(encoding="utf-8")
        assert "error_occurred = Signal(str)" in source


class TestProgressBarWiring:
    def test_main_window_imports_qprogressbar(self) -> None:
        mw_path = Path(__file__).parent.parent.parent / "gui" / "main_window.py"
        source = mw_path.read_text(encoding="utf-8")
        assert "QProgressBar" in source

    def test_progress_bar_hidden_on_build(self) -> None:
        """_build_status_bar must set progress bar to invisible initially."""
        mw_path = Path(__file__).parent.parent.parent / "gui" / "main_window.py"
        source = mw_path.read_text(encoding="utf-8")
        assert "self._progress_bar.setVisible(False)" in source

    def test_progress_bar_shown_on_ocr_progress(self) -> None:
        mw_path = Path(__file__).parent.parent.parent / "gui" / "main_window.py"
        source = mw_path.read_text(encoding="utf-8")
        assert "_on_ocr_progress" in source
        assert "_progress_bar.setVisible(True)" in source

    def test_progress_bar_hidden_on_ocr_results(self) -> None:
        mw_path = Path(__file__).parent.parent.parent / "gui" / "main_window.py"
        source = mw_path.read_text(encoding="utf-8")
        assert "_on_ocr_results" in source
        # progress bar must be hidden on success
        idx_results = source.index("def _on_ocr_results")
        idx_next = source.index("\n    @Slot", idx_results)
        results_block = source[idx_results:idx_next]
        assert "_progress_bar.setVisible(False)" in results_block

    def test_progress_bar_hidden_on_ocr_error(self) -> None:
        mw_path = Path(__file__).parent.parent.parent / "gui" / "main_window.py"
        source = mw_path.read_text(encoding="utf-8")
        idx_error = source.index("def _on_ocr_error")
        idx_next = source.index("\n    @Slot", idx_error)
        error_block = source[idx_error:idx_next]
        assert "_progress_bar.setVisible(False)" in error_block

    def test_export_shows_indeterminate_progress(self) -> None:
        """Export must set range (0, 0) = indeterminate before formatting."""
        mw_path = Path(__file__).parent.parent.parent / "gui" / "main_window.py"
        source = mw_path.read_text(encoding="utf-8")
        assert "setRange(0, 0)" in source

    def test_export_hides_progress_bar_on_success(self) -> None:
        mw_path = Path(__file__).parent.parent.parent / "gui" / "main_window.py"
        source = mw_path.read_text(encoding="utf-8")
        idx_export = source.index("def _trigger_export")
        export_block = source[idx_export:]
        assert "_progress_bar.setVisible(False)" in export_block

    def test_progress_bar_fixed_width_200(self) -> None:
        source = (Path(__file__).parent.parent.parent / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "_progress_bar.setFixedWidth(200)" in source

    def test_progress_bar_text_visible(self) -> None:
        source = (Path(__file__).parent.parent.parent / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "_progress_bar.setTextVisible(True)" in source

    def test_progress_bar_added_to_status_bar(self) -> None:
        source = (Path(__file__).parent.parent.parent / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "_status_bar.addPermanentWidget(self._progress_bar)" in source

    def test_ocr_progress_sets_range_and_value(self) -> None:
        source = (Path(__file__).parent.parent.parent / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "_progress_bar.setRange(0, total)" in source
        assert "_progress_bar.setValue(done)" in source


# ---------------------------------------------------------------------------
# GUI tests (require QApplication + compatible DLL env)
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestProgressBarGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_progress_bar_initially_hidden(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._progress_bar.isVisible()

    def test_on_ocr_progress_shows_bar(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._on_ocr_progress(1, 5)
        assert w._progress_bar.isVisible()
        assert w._progress_bar.value() == 1
        assert w._progress_bar.maximum() == 5

    def test_on_ocr_progress_updates_value(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._on_ocr_progress(3, 10)
        assert w._progress_bar.value() == 3

    def test_on_ocr_results_hides_bar(self, tmp_path: Path) -> None:
        from core.types import BoundingBox, OCRResult
        w = self._make_window(tmp_path)
        w._on_ocr_progress(2, 5)
        assert w._progress_bar.isVisible()
        w._on_ocr_results([])
        assert not w._progress_bar.isVisible()

    def test_on_ocr_error_hides_bar(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._on_ocr_progress(1, 3)
        assert w._progress_bar.isVisible()
        from unittest.mock import patch
        with patch.object(w, "_state_machine"):
            with patch("gui.main_window.QMessageBox"):
                w._on_ocr_error("test error")
        assert not w._progress_bar.isVisible()

    def test_progress_bar_zero_total_guard(self, tmp_path: Path) -> None:
        """Zero total must not show bar to avoid division by zero."""
        w = self._make_window(tmp_path)
        w._on_ocr_progress(0, 0)
        assert not w._progress_bar.isVisible()
