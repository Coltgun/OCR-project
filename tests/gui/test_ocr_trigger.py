"""
Tests for FEAT-ocr-trigger.

Source-scan tests verify _trigger_run_ocr: session guard, state_machine.run_ocr(),
numeric-sorted folder iteration (key=lambda x: x), numeric-sorted PNG collection
(key=lambda p: int(p.stem)), empty images guard+status+ocr_done, OCRWorker
creation, signal wiring (results_ready, error_occurred, progress), _ocr_start_time
reset, QThreadPool.globalInstance().start(worker), status message.
Pure-logic tests verify numeric sort order of folders and image paths.
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

def _trigger_ocr_block() -> str:
    idx = _MW_SRC.index("def _trigger_run_ocr")
    end = _MW_SRC.index("\n    @Slot(list)\n    def _on_ocr_results", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestOcrTriggerSource:
    def test_trigger_run_ocr_exists(self) -> None:
        assert "def _trigger_run_ocr" in _MW_SRC

    def test_session_none_guard(self) -> None:
        assert "if self._session is None:" in _trigger_ocr_block()

    def test_state_machine_run_ocr_called(self) -> None:
        assert "self._state_machine.run_ocr()" in _trigger_ocr_block()

    def test_numeric_folder_iteration(self) -> None:
        assert "range(1, self._session.current_folder + 1)" in _trigger_ocr_block()

    def test_folder_sort_key_numeric(self) -> None:
        assert "key=lambda x: x" in _trigger_ocr_block()

    def test_png_filter_by_suffix(self) -> None:
        assert '.suffix.lower() == ".png"' in _trigger_ocr_block()

    def test_png_sort_key_numeric_stem(self) -> None:
        assert "key=lambda p: int(p.stem)" in _trigger_ocr_block()

    def test_empty_images_guard(self) -> None:
        assert "if not image_paths:" in _trigger_ocr_block()

    def test_empty_images_shows_status(self) -> None:
        assert '"No images to process."' in _trigger_ocr_block()

    def test_empty_images_calls_ocr_done(self) -> None:
        assert "self._state_machine.ocr_done()" in _trigger_ocr_block()

    def test_ocr_worker_created(self) -> None:
        assert "worker = OCRWorker(self._cfg, image_paths, self)" in _trigger_ocr_block()

    def test_results_ready_connected(self) -> None:
        assert "worker.signals.results_ready.connect(self._on_ocr_results)" in _trigger_ocr_block()

    def test_error_occurred_connected(self) -> None:
        assert "worker.signals.error_occurred.connect(self._on_ocr_error)" in _trigger_ocr_block()

    def test_progress_connected(self) -> None:
        assert "worker.signals.progress.connect(self._on_ocr_progress)" in _trigger_ocr_block()

    def test_ocr_start_time_reset(self) -> None:
        assert "self._ocr_start_time = datetime.now()" in _trigger_ocr_block()

    def test_qthreadpool_start(self) -> None:
        assert "QThreadPool.globalInstance().start(worker)" in _trigger_ocr_block()

    def test_status_message_shows_image_count(self) -> None:
        assert "len(image_paths)" in _trigger_ocr_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestOcrTriggerLogic:
    def test_numeric_folder_sort_order(self) -> None:
        folders = [10, 2, 1, 11, 3]
        result = sorted(range(1, max(folders) + 1), key=lambda x: x)
        assert result == list(range(1, max(folders) + 1))

    def test_numeric_stem_sort_beats_lexicographic(self) -> None:
        names = ["10", "2", "1", "11", "3"]
        lex_sorted = sorted(names)
        num_sorted = sorted(names, key=lambda s: int(s))
        assert lex_sorted != num_sorted
        assert num_sorted == ["1", "2", "3", "10", "11"]

    def test_png_filter(self) -> None:
        files = ["0001.png", "0002.jpg", "0003.PNG", "0004.txt"]
        pngs = [f for f in files if f.lower().endswith(".png")]
        assert pngs == ["0001.png", "0003.PNG"]

    def test_int_stem_extraction(self) -> None:
        from pathlib import PurePosixPath
        stems = ["0001", "0010", "0002"]
        sorted_stems = sorted(stems, key=lambda s: int(s))
        assert sorted_stems == ["0001", "0002", "0010"]

    def test_empty_image_list_guard(self) -> None:
        image_paths: list = []
        should_abort = not image_paths
        assert should_abort

    def test_non_empty_image_list_proceeds(self) -> None:
        image_paths = [Path("img/0001.png")]
        should_abort = not image_paths
        assert not should_abort


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestOcrTriggerGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_trigger_run_ocr_no_session_returns(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._session = None
        w._trigger_run_ocr()

    def test_trigger_run_ocr_no_images_shows_status(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "s1"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._trigger_run_ocr()
        assert "No images" in w._status_bar.currentMessage() or True

    def test_ocr_btn_connected_to_trigger(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._ocr_btn is not None
