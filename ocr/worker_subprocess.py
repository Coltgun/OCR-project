"""
ocr/worker_subprocess.py — long-lived OCR child process.

Protocol (line-delimited JSON over stdin/stdout):
    Request:  {"image_path": "/abs/path/to/img.png"}
           or {"shutdown": true}
    Response: {"ok": true,  "results": [...]}
           or {"ok": false, "error": "message"}

Run via subprocess.Popen; never imported directly into the GUI process.
"""

from __future__ import annotations

import json
import os
import site
import sys


def _setup_dlls() -> None:
    """Register CUDA/MKL DLL directories before any paddle import."""
    lib_bin = os.path.join(sys.prefix, "Library", "bin")
    if os.path.isdir(lib_bin):
        os.add_dll_directory(lib_bin)
        os.environ["PATH"] = lib_bin + os.pathsep + os.environ.get("PATH", "")

    nvidia_subdirs = [
        "cublas", "cuda_runtime", "cudnn", "cufft",
        "curand", "cusolver", "cusparse", "nvjitlink",
    ]
    extra: list[str] = []
    for sp in site.getsitepackages():
        for d in nvidia_subdirs:
            p = os.path.join(sp, "nvidia", d, "bin")
            if os.path.isdir(p):
                os.add_dll_directory(p)
                extra.append(p)
    if extra:
        os.environ["PATH"] = os.pathsep.join(extra) + os.pathsep + os.environ.get("PATH", "")


def _load_engine(config: dict):  # type: ignore[return]
    """Import PaddleOCR and instantiate the engine from config."""
    from paddleocr import PaddleOCR  # noqa: PLC0415

    use_gpu = bool(config.get("paddleocr_use_gpu", True))
    lang = str(config.get("paddleocr_lang", "ch"))
    orientation = bool(config.get("paddleocr_orientation", True))
    device = "gpu" if use_gpu else "cpu"
    return PaddleOCR(use_textline_orientation=orientation, lang=lang, device=device)


def _process_image(engine, image_path: str) -> list[dict]:
    """Run OCR on one image file and return a list of result dicts."""
    import cv2  # noqa: PLC0415

    image = cv2.imread(image_path)
    if image is None:
        return []

    image_id = os.path.splitext(os.path.basename(image_path))[0]
    raw = engine.predict(image)
    results: list[dict] = []

    for page in (raw or []):
        if page is None:
            continue
        try:
            texts = page["rec_texts"]
            scores = page["rec_scores"]
            boxes = page["rec_boxes"]
            for text, conf, box in zip(texts, scores, boxes):
                if text is None or str(text).strip() == "":
                    continue
                x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                results.append(
                    {
                        "text": str(text),
                        "confidence": float(conf),
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                        "image_id": image_id,
                    }
                )
        except Exception as exc:
            sys.stderr.write(f"result parse error: {exc}\n")
            sys.stderr.flush()

    return results


def _warmup(engine) -> None:
    """Run a dummy predict to bake cuDNN algorithm selection."""
    import numpy as np  # noqa: PLC0415

    dummy = np.zeros((32, 32, 3), dtype=np.uint8)
    try:
        engine.predict(dummy)
    except Exception:
        pass  # warmup failure is non-fatal


def main() -> None:
    _setup_dlls()

    # Read config from the first stdin line before entering the request loop
    config_line = sys.stdin.readline()
    try:
        config: dict = json.loads(config_line)
    except (json.JSONDecodeError, ValueError):
        config = {}

    engine = _load_engine(config)

    if config.get("ocr_worker_warmup", True):
        _warmup(engine)

    # Signal ready
    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req: dict = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.stdout.write(json.dumps({"ok": False, "error": f"bad JSON: {exc}"}) + "\n")
            sys.stdout.flush()
            continue

        if req.get("shutdown"):
            break

        image_path: str = req.get("image_path", "")
        if not image_path:
            sys.stdout.write(json.dumps({"ok": False, "error": "missing image_path"}) + "\n")
            sys.stdout.flush()
            continue

        try:
            results = _process_image(engine, image_path)
            sys.stdout.write(json.dumps({"ok": True, "results": results}) + "\n")
        except Exception as exc:
            sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
