"""
bench_ocr.py — wall-clock benchmark for OCR pipeline modes.

Usage (from repo root, conda env active):
    python scripts/bench_ocr.py --pipeline LOCAL_FAST --images tests/fixtures/ocr_images --runs 3
    python scripts/bench_ocr.py --pipeline LOCAL_LLM  --images tests/fixtures/ocr_images --runs 3
    python scripts/bench_ocr.py --pipeline API_STANDARD --images tests/fixtures/ocr_images --runs 3

The script writes a human-readable summary to stdout and appends one JSON line
per run to BASELINE.txt in the repo root (for later comparison).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import statistics
import sys
import time
from pathlib import Path

# --- ensure repo root is on sys.path ---
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from utils.logging_config import setup_logging

# Set up logging so [PERF] lines are visible
setup_logging(log_level=logging.INFO, console=True)

import logging
logger = logging.getLogger("bench_ocr")


def _load_config(pipeline: str) -> dict:
    """Load config.json (or config.example.json) and patch for benchmarking."""
    config_path = _REPO_ROOT / "config.json"
    if not config_path.exists():
        config_path = _REPO_ROOT / "config.example.json"
    with config_path.open(encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg["ocr_pipeline_mode"] = pipeline
    cfg["perf_timing"] = True
    return cfg


def _collect_images(images_dir: Path) -> list[Path]:
    """Return image paths from *images_dir*, sorted numerically by stem."""
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    paths = [p for p in images_dir.iterdir() if p.suffix.lower() in exts]
    paths = sorted(paths, key=lambda p: int(re.sub(r"\D", "0", p.stem) or "0"))
    return paths


def _run_once(image_paths: list[Path], config: dict) -> tuple[float, list]:
    """Run OCRWorker synchronously and return (wall_clock_s, ocr_results)."""
    from ocr.worker import OCRWorker
    from ocr.pipeline import Pipeline, PIPELINE_MODES, _DEFAULT_MODE
    from core.types import BoundingBox, OCRResult
    import json as _json

    worker_cls = OCRWorker  # noqa: F841 — verify import ok

    # Run the subprocess path directly (no Qt event loop needed for bench)
    from ocr.worker import _build_subprocess_script
    import subprocess

    all_results: list[list[dict]] = []
    t0 = time.perf_counter()

    clean_env = {
        k: v for k, v in os.environ.items()
        if k.upper() in (
            "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
            "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
            "PYTHONPATH", "PYTHONHOME",
            "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "PATH",
        )
    }

    config_json = _json.dumps(config)
    for path in image_paths:
        script = _build_subprocess_script(str(path), config_json)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=300,
            env=clean_env,
        )
        if result.returncode != 0:
            stderr_tail = (result.stderr or "").strip().splitlines()
            last = stderr_tail[-1] if stderr_tail else "unknown"
            logger.error("Subprocess failed for %s: %s", path.name, last)
            all_results.append([])
        else:
            try:
                all_results.append(_json.loads(result.stdout.strip() or "[]"))
            except _json.JSONDecodeError:
                all_results.append([])

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

    mode = config.get("ocr_pipeline_mode", _DEFAULT_MODE)
    if mode in PIPELINE_MODES:
        pipeline = Pipeline(mode, config)
        ocr_results = pipeline.process(ocr_results)

    elapsed = time.perf_counter() - t0
    return elapsed, ocr_results


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR pipeline benchmark")
    parser.add_argument("--pipeline", default="LOCAL_FAST", help="Pipeline mode name")
    parser.add_argument("--images", required=True, help="Directory of test images")
    parser.add_argument("--runs", type=int, default=3, help="Number of timed runs")
    parser.add_argument("--warmup", type=int, default=0, help="Warmup runs (not counted)")
    parser.add_argument(
        "--output", default=str(_REPO_ROOT / "BASELINE.txt"),
        help="File to append JSON result lines to",
    )
    args = parser.parse_args()

    images_dir = Path(args.images)
    if not images_dir.exists():
        print(f"ERROR: images directory not found: {images_dir}", file=sys.stderr)
        sys.exit(1)

    image_paths = _collect_images(images_dir)
    if not image_paths:
        print(f"ERROR: no images found in {images_dir}", file=sys.stderr)
        sys.exit(1)

    config = _load_config(args.pipeline)

    print(f"\n=== bench_ocr: pipeline={args.pipeline}  images={len(image_paths)}  "
          f"runs={args.runs}  warmup={args.warmup} ===\n")

    # Warmup runs
    for i in range(args.warmup):
        print(f"  [warmup {i+1}/{args.warmup}] ...", end=" ", flush=True)
        elapsed, _ = _run_once(image_paths, config)
        print(f"{elapsed:.2f}s")

    # Timed runs
    times: list[float] = []
    result_counts: list[int] = []
    for i in range(args.runs):
        print(f"  [run {i+1}/{args.runs}] ...", end=" ", flush=True)
        elapsed, results = _run_once(image_paths, config)
        times.append(elapsed)
        result_counts.append(len(results))
        print(f"{elapsed:.2f}s  ({len(results)} results)")

    med = statistics.median(times)
    mn = min(times)
    mx = max(times)
    print(f"\n  median={med:.2f}s  min={mn:.2f}s  max={mx:.2f}s  "
          f"avg_results={statistics.mean(result_counts):.1f}")

    record = {
        "pipeline": args.pipeline,
        "images": len(image_paths),
        "runs": times,
        "median_s": round(med, 3),
        "min_s": round(mn, 3),
        "max_s": round(mx, 3),
    }
    with open(args.output, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    print(f"\n  Result appended to: {args.output}\n")


if __name__ == "__main__":
    main()
