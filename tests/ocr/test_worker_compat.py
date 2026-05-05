"""
Tests for OCRWorker long-lived subprocess path.

All subprocess interactions are mocked at the Popen boundary.
No real PaddleOCR process is started (slow tests tagged @pytest.mark.slow).
"""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ocr.worker import _build_clean_env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_RESULTS = [
    {"text": "测试文本", "confidence": 0.95, "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 20}, "image_id": "001"},
    {"text": "第二行", "confidence": 0.88, "bbox": {"x1": 0, "y1": 25, "x2": 80, "y2": 45}, "image_id": "001"},
]


def _make_mock_proc(responses: list[str]) -> MagicMock:
    """Build a mock Popen process that yields *responses* line-by-line on stdout."""
    proc = MagicMock()
    proc.poll.return_value = None

    lines = iter(responses)
    proc.stdout.readline.side_effect = lambda: next(lines, "")
    proc.stderr.__iter__ = MagicMock(return_value=iter([]))
    proc.stdin.write = MagicMock()
    proc.stdin.flush = MagicMock()
    proc.stdin.close = MagicMock()
    proc.wait = MagicMock(return_value=0)
    proc.terminate = MagicMock()
    return proc


# ---------------------------------------------------------------------------
# Unit tests — long-lived path (mocked Popen)
# ---------------------------------------------------------------------------

class TestLongLivedBatch:
    """Test _run_longlived_batch via the OCRWorker instance."""

    def _make_worker(self, image_paths: list[Path], config: dict | None = None):
        from ocr.worker import OCRWorker
        cfg = {"ocr_long_lived_worker": True, "ocr_worker_warmup": False}
        if config:
            cfg.update(config)
        worker = OCRWorker.__new__(OCRWorker)
        worker._config = cfg
        worker._image_paths = image_paths
        return worker

    def test_happy_path_two_images(self, tmp_path: Path) -> None:
        img1 = tmp_path / "0001.png"
        img2 = tmp_path / "0002.png"
        img1.touch()
        img2.touch()

        ready = json.dumps({"ready": True})
        resp1 = json.dumps({"ok": True, "results": _SAMPLE_RESULTS})
        resp2 = json.dumps({"ok": True, "results": [_SAMPLE_RESULTS[1]]})

        mock_proc = _make_mock_proc([ready, resp1, resp2])

        with patch("subprocess.Popen", return_value=mock_proc):
            worker = self._make_worker([img1, img2])
            results = worker._run_longlived_batch(perf_enabled=False)

        assert len(results) == 2
        assert results[0] == _SAMPLE_RESULTS
        assert results[1] == [_SAMPLE_RESULTS[1]]

    def test_worker_error_response_yields_empty_list(self, tmp_path: Path) -> None:
        img = tmp_path / "0001.png"
        img.touch()

        ready = json.dumps({"ready": True})
        resp = json.dumps({"ok": False, "error": "cv2 read failed"})
        mock_proc = _make_mock_proc([ready, resp])

        with patch("subprocess.Popen", return_value=mock_proc):
            worker = self._make_worker([img])
            results = worker._run_longlived_batch(perf_enabled=False)

        assert results == [[]]

    def test_child_crash_raises_runtime_error(self, tmp_path: Path) -> None:
        img = tmp_path / "0001.png"
        img.touch()

        ready = json.dumps({"ready": True})
        mock_proc = _make_mock_proc([ready, ""])  # empty = EOF after crash
        mock_proc.poll.return_value = 1

        with patch("subprocess.Popen", return_value=mock_proc):
            worker = self._make_worker([img])
            with pytest.raises(RuntimeError, match="EOF"):
                worker._run_longlived_batch(perf_enabled=False)

    def test_not_ready_signal_raises(self, tmp_path: Path) -> None:
        img = tmp_path / "0001.png"
        img.touch()

        mock_proc = _make_mock_proc([json.dumps({"ready": False})])

        with patch("subprocess.Popen", return_value=mock_proc):
            worker = self._make_worker([img])
            with pytest.raises(RuntimeError, match="did not signal ready"):
                worker._run_longlived_batch(perf_enabled=False)

    def test_shutdown_sent_on_success(self, tmp_path: Path) -> None:
        img = tmp_path / "0001.png"
        img.touch()

        ready = json.dumps({"ready": True})
        resp = json.dumps({"ok": True, "results": []})
        mock_proc = _make_mock_proc([ready, resp])

        with patch("subprocess.Popen", return_value=mock_proc):
            worker = self._make_worker([img])
            worker._run_longlived_batch(perf_enabled=False)

        written_calls = [str(c) for c in mock_proc.stdin.write.call_args_list]
        assert any("shutdown" in c for c in written_calls)

    def test_crash_triggers_terminate(self, tmp_path: Path) -> None:
        img = tmp_path / "0001.png"
        img.touch()

        mock_proc = _make_mock_proc(["not-json-at-all"])

        with patch("subprocess.Popen", return_value=mock_proc):
            worker = self._make_worker([img])
            with pytest.raises(RuntimeError):
                worker._run_longlived_batch(perf_enabled=False)

        mock_proc.terminate.assert_called()


class TestBuildCleanEnv:
    def test_returns_dict(self) -> None:
        env = _build_clean_env()
        assert isinstance(env, dict)

    def test_path_is_set(self) -> None:
        env = _build_clean_env()
        assert "PATH" in env

    def test_no_random_env_vars_leaked(self) -> None:
        env = _build_clean_env()
        assert "SOME_RANDOM_APP_SECRET" not in env


class TestOCRWorkerRunDispatch:
    """Verify that OCRWorker.run() picks the right path based on config."""

    def _make_signals_mock(self):
        m = MagicMock()
        m.progress = MagicMock()
        m.progress.emit = MagicMock()
        m.results_ready = MagicMock()
        m.results_ready.emit = MagicMock()
        m.error_occurred = MagicMock()
        m.error_occurred.emit = MagicMock()
        return m

    def test_longlived_disabled_calls_single_subprocess(self, tmp_path: Path) -> None:
        from ocr.worker import OCRWorker
        img = tmp_path / "0001.png"
        img.touch()

        worker = OCRWorker.__new__(OCRWorker)
        worker._config = {"ocr_long_lived_worker": False, "ocr_pipeline_mode": "LOCAL_FAST"}
        worker._image_paths = [img]
        worker.signals = self._make_signals_mock()

        with patch.object(OCRWorker, "_run_single_subprocess", return_value=[]) as mock_single:
            with patch("ocr.worker.Pipeline") as mock_pipeline:
                mock_pipeline.return_value.process.return_value = []
                worker.run()
            mock_single.assert_called_once_with(img)

    def test_longlived_enabled_calls_longlived_batch(self, tmp_path: Path) -> None:
        from ocr.worker import OCRWorker
        img = tmp_path / "0001.png"
        img.touch()

        worker = OCRWorker.__new__(OCRWorker)
        worker._config = {"ocr_long_lived_worker": True, "ocr_pipeline_mode": "LOCAL_FAST"}
        worker._image_paths = [img]
        worker.signals = self._make_signals_mock()

        with patch.object(OCRWorker, "_run_longlived_batch", return_value=[[]]) as mock_ll:
            with patch("ocr.worker.Pipeline") as mock_pipeline:
                mock_pipeline.return_value.process.return_value = []
                worker.run()
            mock_ll.assert_called_once()
