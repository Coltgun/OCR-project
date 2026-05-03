"""
Tests for FEAT-ocr-progress.

Source-scan tests verify _progress_bar QProgressBar (fixed width, hidden, permanent),
_on_ocr_progress: timing, pct calculation, setRange/setValue/setVisible, status msg;
_on_ocr_error: progress_bar.setVisible(False), status, QMessageBox.critical;
_on_ocr_results: progress_bar.setVisible(False); _ocr_start_time init.
Pure-logic tests verify pct formula and timing semantics.
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

def _on_progress_block() -> str:
    idx = _MW_SRC.index("def _on_ocr_progress")
    end = _MW_SRC.index("\n    @Slot()\n    def _trigger_export", idx + 1)
    return _MW_SRC[idx:end]

def _on_ocr_error_block() -> str:
    idx = _MW_SRC.index("def _on_ocr_error")
    end = _MW_SRC.index("\n    def _on_ocr_progress", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestOcrProgressSource:
    def test_progress_bar_created(self) -> None:
        assert "self._progress_bar = QProgressBar()" in _MW_SRC

    def test_progress_bar_fixed_width(self) -> None:
        assert "_progress_bar.setFixedWidth(200)" in _MW_SRC

    def test_progress_bar_hidden_on_init(self) -> None:
        assert "_progress_bar.setVisible(False)" in _MW_SRC

    def test_progress_bar_added_to_status_bar(self) -> None:
        assert "_status_bar.addPermanentWidget(self._progress_bar)" in _MW_SRC

    def test_ocr_start_time_initialised(self) -> None:
        assert "_ocr_start_time: datetime = datetime.now()" in _MW_SRC

    def test_on_ocr_progress_exists(self) -> None:
        assert "def _on_ocr_progress" in _MW_SRC

    def test_on_ocr_progress_computes_elapsed(self) -> None:
        assert "_ocr_start_time).total_seconds()" in _on_progress_block()

    def test_on_ocr_progress_computes_pct(self) -> None:
        assert "done / total * 100" in _on_progress_block()

    def test_on_ocr_progress_guards_total_zero(self) -> None:
        assert "if total > 0" in _on_progress_block()

    def test_on_ocr_progress_sets_range(self) -> None:
        assert "_progress_bar.setRange(0, total)" in _on_progress_block()

    def test_on_ocr_progress_sets_value(self) -> None:
        assert "_progress_bar.setValue(done)" in _on_progress_block()

    def test_on_ocr_progress_shows_bar(self) -> None:
        assert "_progress_bar.setVisible(True)" in _on_progress_block()

    def test_on_ocr_error_hides_bar(self) -> None:
        assert "_progress_bar.setVisible(False)" in _on_ocr_error_block()

    def test_on_ocr_results_hides_bar(self) -> None:
        idx = _MW_SRC.index("def _on_ocr_results")
        end = _MW_SRC.index("\n    def _on_ocr_error", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_progress_bar.setVisible(False)" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestOcrProgressLogic:
    def test_pct_halfway(self) -> None:
        done, total = 5, 10
        pct = int(done / total * 100) if total > 0 else 0
        assert pct == 50

    def test_pct_complete(self) -> None:
        done, total = 10, 10
        pct = int(done / total * 100) if total > 0 else 0
        assert pct == 100

    def test_pct_zero_when_total_zero(self) -> None:
        done, total = 0, 0
        pct = int(done / total * 100) if total > 0 else 0
        assert pct == 0

    def test_pct_first_image(self) -> None:
        done, total = 1, 10
        pct = int(done / total * 100) if total > 0 else 0
        assert pct == 10

    def test_bar_hidden_when_total_zero(self) -> None:
        total = 0
        should_show = total > 0
        assert not should_show

    def test_bar_shown_when_total_positive(self) -> None:
        total = 5
        should_show = total > 0
        assert should_show


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestOcrProgressGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_progress_bar_hidden_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._progress_bar.isVisible()

    def test_on_ocr_progress_shows_bar(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._on_ocr_progress(3, 10)
        assert w._progress_bar.isVisible()

    def test_on_ocr_progress_zero_total_hides_bar(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._on_ocr_progress(0, 0)
        assert not w._progress_bar.isVisible()
