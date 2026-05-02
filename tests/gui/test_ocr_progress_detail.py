"""
Tests for FEAT-ocr-progress-detail.

Source-scan tests verify the enriched progress message and elapsed time.
Pure-logic tests verify message formatting.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestOcrProgressDetailSource:
    def test_start_time_initialised(self) -> None:
        assert "self._ocr_start_time: datetime = datetime.now()" in _MW_SRC

    def test_start_time_stamped_before_worker(self) -> None:
        idx = _MW_SRC.index("def _trigger_run_ocr")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._ocr_start_time = datetime.now()" in block

    def test_elapsed_computed_in_on_progress(self) -> None:
        idx = _MW_SRC.index("def _on_ocr_progress")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "datetime.now() - self._ocr_start_time" in block

    def test_elapsed_in_seconds(self) -> None:
        idx = _MW_SRC.index("def _on_ocr_progress")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "total_seconds()" in block

    def test_pct_computed(self) -> None:
        idx = _MW_SRC.index("def _on_ocr_progress")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "pct" in block

    def test_message_format_image_n_of_m(self) -> None:
        assert '"OCR: image {done} / {total}' in _MW_SRC

    def test_message_includes_pct(self) -> None:
        assert "({pct}%)" in _MW_SRC

    def test_message_includes_elapsed(self) -> None:
        assert "elapsed" in _MW_SRC

    def test_elapsed_one_decimal(self) -> None:
        assert "{elapsed:.1f}s elapsed" in _MW_SRC

    def test_pct_guarded_total_zero(self) -> None:
        idx = _MW_SRC.index("def _on_ocr_progress")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "if total > 0 else 0" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

def _progress_msg(done: int, total: int, elapsed: float) -> str:
    pct = int(done / total * 100) if total > 0 else 0
    return f"OCR: image {done} / {total}  ({pct}%)  \u2014  {elapsed:.1f}s elapsed"


class TestOcrProgressDetailLogic:
    def test_first_image_message(self) -> None:
        msg = _progress_msg(1, 10, 0.5)
        assert "OCR: image 1 / 10" in msg
        assert "10%" in msg
        assert "0.5s elapsed" in msg

    def test_last_image_message(self) -> None:
        msg = _progress_msg(10, 10, 3.2)
        assert "100%" in msg
        assert "10 / 10" in msg

    def test_zero_total_gives_zero_pct(self) -> None:
        msg = _progress_msg(0, 0, 0.0)
        assert "(0%)" in msg

    def test_elapsed_one_decimal(self) -> None:
        msg = _progress_msg(1, 5, 1.567)
        assert "1.6s elapsed" in msg

    def test_halfway_pct(self) -> None:
        msg = _progress_msg(5, 10, 2.0)
        assert "50%" in msg

    def test_pct_truncates_not_rounds(self) -> None:
        msg = _progress_msg(1, 3, 0.1)
        assert "33%" in msg


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestOcrProgressDetailGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_start_time_attribute_exists(self, tmp_path) -> None:
        from pathlib import Path
        w = self._make_window(tmp_path)
        assert hasattr(w, "_ocr_start_time")

    def test_progress_updates_status_bar(self, tmp_path) -> None:
        from pathlib import Path
        from datetime import datetime
        w = self._make_window(tmp_path)
        w._ocr_start_time = datetime.now()
        w._on_ocr_progress(3, 10)
        msg = w._status_bar.currentMessage()
        assert "3 / 10" in msg
        assert "30%" in msg

    def test_progress_bar_visible(self, tmp_path) -> None:
        from datetime import datetime
        w = self._make_window(tmp_path)
        w._ocr_start_time = datetime.now()
        w._on_ocr_progress(1, 5)
        assert w._progress_bar.isVisible()
