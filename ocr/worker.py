"""
OCRWorker — runs PaddleOCR in a subprocess to enforce process isolation.

On Windows, paddle (cu126) and torch (cu121) bundle incompatible cuDNN DLL
builds and cannot coexist in the same process. This worker runs the OCR
engine in a fresh subprocess, returning results to the caller via a queue.

Typical use (from the main Qt process):
    worker = OCRWorker(config, image_paths)
    worker.results_ready.connect(my_slot)
    worker.error_occurred.connect(my_error_slot)
    QThreadPool.globalInstance().start(worker)

The subprocess runs ocr/worker_subprocess.py which imports paddle, runs
PaddleOCREngine, and writes OCRResult objects to stdout as JSON.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image as PILImage
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from core.types import BoundingBox, OCRResult
from ocr.pipeline import Pipeline, PIPELINE_MODES, _DEFAULT_MODE

logger = logging.getLogger(__name__)


class OCRWorkerSignals(QObject):
    """Signals for OCRWorker (QRunnable cannot have signals directly)."""

    results_ready = Signal(list)
    error_occurred = Signal(str)
    progress = Signal(int, int)


class OCRWorker(QRunnable):
    """QRunnable that runs PaddleOCR in a subprocess and emits results.

    Args:
        config:      Full application config dict.
        image_paths: Ordered list of image paths to process.
        parent:      Optional parent for the signals QObject.
    """

    def __init__(
        self,
        config: dict,
        image_paths: list[Path],
        parent: QObject | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._image_paths = image_paths
        self.signals = OCRWorkerSignals(parent)
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Execute OCR in a subprocess for each image path."""
        all_results: list[list[dict]] = []
        total = len(self._image_paths)
        perf_enabled = bool(self._config.get("perf_timing", False))
        use_longlived = bool(self._config.get("ocr_long_lived_worker", False))

        if use_longlived and total > 0:
            try:
                all_results = self._run_longlived_batch(perf_enabled)
                for idx in range(total):
                    self.signals.progress.emit(idx + 1, total)
            except Exception as exc:
                logger.error("OCRWorker: long-lived batch failed: %s — falling back to per-image mode.", exc)
                all_results = []
                use_longlived = False

        if not use_longlived:
            for idx, path in enumerate(self._image_paths):
                try:
                    _t0 = time.perf_counter()
                    if perf_enabled:
                        logger.info("[PERF] ocr_subprocess start image=%s", path.name)
                    page_results = self._run_single_subprocess(path)
                    if perf_enabled:
                        _ms = (time.perf_counter() - _t0) * 1000.0
                        logger.info(
                            "[PERF] ocr_subprocess end image=%s ms=%.1f results=%d",
                            path.name, _ms, len(page_results),
                        )
                    all_results.append(page_results)
                    self.signals.progress.emit(idx + 1, total)
                except Exception as exc:
                    logger.error("OCRWorker: error on '%s': %s", path, exc)
                    self.signals.error_occurred.emit(str(exc))
                    return

        ocr_results = [
            OCRResult(
                text=r["text"],
                confidence=r["confidence"],
                bbox=BoundingBox(**r["bbox"]) if r.get("bbox") else None,
                image_id=r.get("image_id", ""),
            )
            for page in all_results
            for r in page
        ]

        mode = str(self._config.get("ocr_pipeline_mode", _DEFAULT_MODE))
        if mode not in PIPELINE_MODES:
            logger.warning(
                "OCRWorker: unknown pipeline mode '%s', falling back to '%s'.",
                mode, _DEFAULT_MODE,
            )
            mode = _DEFAULT_MODE

        try:
            pipeline = Pipeline(mode, self._config)
            ocr_results = pipeline.process(ocr_results)
        except Exception as exc:
            logger.error("OCRWorker: pipeline failed: %s — emitting raw results.", exc)

        self.signals.results_ready.emit(ocr_results)

    def _run_longlived_batch(self, perf_enabled: bool) -> list[list[dict]]:
        """Start worker_subprocess.py once, send all images, collect responses.

        Returns a list-of-lists parallel to self._image_paths.
        Raises RuntimeError on child crash or protocol error.
        """
        subprocess_script = Path(__file__).with_name("worker_subprocess.py")
        clean_env = _build_clean_env()
        config_json = json.dumps(self._config)

        proc = subprocess.Popen(
            [sys.executable, str(subprocess_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=clean_env,
            bufsize=1,
        )

        stderr_lines: list[str] = []

        def _drain_stderr() -> None:
            for line in proc.stderr:  # type: ignore[union-attr]
                stderr_lines.append(line.rstrip())

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        try:
            # Send config as first line
            proc.stdin.write(config_json + "\n")  # type: ignore[union-attr]
            proc.stdin.flush()  # type: ignore[union-attr]

            # Wait for ready signal
            ready_line = proc.stdout.readline()  # type: ignore[union-attr]
            try:
                ready = json.loads(ready_line)
                if not ready.get("ready"):
                    raise RuntimeError(f"Worker did not signal ready: {ready_line!r}")
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Worker ready-line not JSON: {ready_line!r}") from exc

            all_results: list[list[dict]] = []
            idle_timeout = float(self._config.get("ocr_worker_idle_timeout_s", 60))

            for path in self._image_paths:
                req = json.dumps({"image_path": str(path)})
                if perf_enabled:
                    logger.info("[PERF] ocr_longlived start image=%s", path.name)
                _t0 = time.perf_counter()

                proc.stdin.write(req + "\n")  # type: ignore[union-attr]
                proc.stdin.flush()  # type: ignore[union-attr]

                # Blocking readline — safe because the stderr drain thread
                # prevents the child's stderr pipe from filling and blocking.
                # If the child crashes, readline returns "" (EOF).
                resp_line = proc.stdout.readline()  # type: ignore[union-attr]
                if not resp_line:
                    raise RuntimeError(
                        f"OCR worker EOF (process likely crashed) on image {path.name}. "
                        f"Exit code: {proc.poll()}"
                    )

                if perf_enabled:
                    _ms = (time.perf_counter() - _t0) * 1000.0

                try:
                    resp = json.loads(resp_line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Worker response not JSON for {path.name}: {resp_line!r}") from exc

                if not resp.get("ok"):
                    err = resp.get("error", "unknown")
                    logger.warning("OCRWorker: worker reported error for '%s': %s", path.name, err)
                    all_results.append([])
                else:
                    page = resp.get("results", [])
                    if perf_enabled:
                        logger.info(
                            "[PERF] ocr_longlived end image=%s ms=%.1f results=%d",
                            path.name, _ms, len(page),
                        )
                    all_results.append(page)

            # Graceful shutdown
            try:
                proc.stdin.write(json.dumps({"shutdown": True}) + "\n")  # type: ignore[union-attr]
                proc.stdin.flush()  # type: ignore[union-attr]
                proc.stdin.close()  # type: ignore[union-attr]
            except OSError:
                pass
            proc.wait(timeout=10)
            return all_results

        except Exception:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except OSError:
                pass
            if stderr_lines:
                logger.error("OCR worker stderr: %s", "\n".join(stderr_lines[-20:]))
            raise
        finally:
            stderr_thread.join(timeout=2.0)

    def _run_single_subprocess(self, image_path: Path) -> list[dict]:
        """Run OCR on one image in a clean subprocess, return list of result dicts.

        A minimal environment (no PATH inherited from parent) is passed so that
        torch/paddle cuDNN DLL conflicts from the parent process never affect the
        child.  The subprocess bootstrap script rebuilds the correct PATH itself.
        """
        config_json = json.dumps(self._config)
        script = _build_subprocess_script(str(image_path), config_json)
        clean_env = _build_clean_env()

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
            env=clean_env,
        )

        if result.returncode != 0:
            stderr_tail = (result.stderr or "").strip().splitlines()
            last = stderr_tail[-1] if stderr_tail else "unknown error"
            raise RuntimeError(
                f"OCR subprocess failed for '{image_path}': {last}"
            )

        output = result.stdout.strip()
        if not output:
            return []

        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"OCR subprocess returned invalid JSON for '{image_path}': {exc}"
            ) from exc


def _build_clean_env() -> dict[str, str]:
    """Return a minimal env dict for subprocess isolation."""
    env = {
        k: v for k, v in os.environ.items()
        if k.upper() in (
            "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
            "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
            "PYTHONPATH", "PYTHONHOME",
            "CONDA_PREFIX", "CONDA_DEFAULT_ENV",
        )
    }
    env["PATH"] = os.path.join(os.environ.get("SYSTEMROOT", "C:\\Windows"), "System32")
    return env


def _build_subprocess_script(image_path: str, config_json: str) -> str:
    """Build the Python script string for the OCR subprocess.

    The script registers nvidia DLL dirs, imports paddle/paddleocr in a clean
    process, runs recognition, and writes JSON results to stdout.
    """
    # Escape backslashes in Windows paths for embedding in a string literal
    safe_path = image_path.replace("\\", "\\\\")
    safe_config = config_json.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")

    return f"""
import os
import site
import json
import sys

# 1. Add conda env Library\\bin (mkl, zlib, openssl, etc.) — required by paddle's
#    cuDNN siblings when the subprocess runs without conda activate.
_lib_bin = os.path.join(sys.prefix, 'Library', 'bin')
if os.path.isdir(_lib_bin):
    os.add_dll_directory(_lib_bin)
    os.environ['PATH'] = _lib_bin + os.pathsep + os.environ.get('PATH', '')

# 2. Add pip-installed NVIDIA CUDA DLL dirs (cublas, cudnn, etc.)
nvidia_subdirs = ['cublas','cuda_runtime','cudnn','cufft','curand','cusolver','cusparse','nvjitlink']
extra = []
for sp in site.getsitepackages():
    for d in nvidia_subdirs:
        p = os.path.join(sp, 'nvidia', d, 'bin')
        if os.path.isdir(p):
            os.add_dll_directory(p)
            extra.append(p)
if extra:
    os.environ['PATH'] = os.pathsep.join(extra) + os.pathsep + os.environ.get('PATH', '')

import numpy as np
from paddleocr import PaddleOCR

config = json.loads('{safe_config}')
use_gpu = bool(config.get('paddleocr_use_gpu', True))
lang = str(config.get('paddleocr_lang', 'ch'))
orientation = bool(config.get('paddleocr_orientation', True))
device = 'gpu' if use_gpu else 'cpu'

engine = PaddleOCR(use_textline_orientation=orientation, lang=lang, device=device)

import cv2
image = cv2.imread(r'{safe_path}')
if image is None:
    print('[]')
    sys.exit(0)

raw = engine.predict(image)
results = []
image_id = os.path.splitext(os.path.basename(r'{safe_path}'))[0]
for page in (raw or []):
    if page is None:
        continue
    try:
        texts  = page['rec_texts']
        scores = page['rec_scores']
        boxes  = page['rec_boxes']   # [[x1,y1,x2,y2], ...]
        for text, conf, box in zip(texts, scores, boxes):
            if text is None or str(text).strip() == '':
                continue
            x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            results.append({{
                'text': str(text),
                'confidence': float(conf),
                'bbox': {{'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}},
                'image_id': image_id,
            }})
    except Exception as e:
        sys.stderr.write(f'result parse error: {{e}}\\n')

print(json.dumps(results))
"""
