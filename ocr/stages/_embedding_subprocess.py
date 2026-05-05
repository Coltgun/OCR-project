"""
ocr/stages/_embedding_subprocess.py — long-lived embedding dedup child process.

Protocol (handled by TorchSubprocessService):
    First stdin line:  {"model": "BAAI/bge-m3", "batch_size": 32, "threshold": 0.92}
    Ready signal:      {"ready": true}
    Per request:       {"request": {"texts": [...], "threshold": N, "batch_size": N}}
    Response:          {"ok": true, "result": [group_assignment, ...]}
                    or {"ok": false, "error": "message"}
    Shutdown:          {"shutdown": true}
"""

from __future__ import annotations

import json
import os
import site
import sys


def _setup_dlls() -> None:
    lib_bin = os.path.join(sys.prefix, "Library", "bin")
    if os.path.isdir(lib_bin):
        os.add_dll_directory(lib_bin)
        os.environ["PATH"] = lib_bin + os.pathsep + os.environ.get("PATH", "")

    nvidia_subdirs = [
        "cublas", "cuda_runtime", "cudnn", "cufft",
        "curand", "cusolver", "cusparse", "nvjitlink",
    ]
    for sp in site.getsitepackages():
        for d in nvidia_subdirs:
            p = os.path.join(sp, "nvidia", d, "bin")
            if os.path.isdir(p):
                os.add_dll_directory(p)
                os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")


def _compute_assignments(
    model,
    texts: list[str],
    threshold: float,
    batch_size: int,
) -> list[int]:
    import numpy as np  # noqa: PLC0415

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    n = len(texts)
    group_assignments = list(range(n))

    # Matmul upper-triangle: faster for large n than the pure-Python loop
    sims = embeddings @ embeddings.T  # (n, n) cosine similarity matrix
    for i in range(n):
        for j in range(i + 1, n):
            if float(sims[i, j]) >= threshold:
                root_i = group_assignments[i]
                if group_assignments[j] == j:
                    group_assignments[j] = root_i

    return group_assignments


def main() -> None:
    _setup_dlls()

    init_line = sys.stdin.readline()
    try:
        init: dict = json.loads(init_line)
    except (json.JSONDecodeError, ValueError):
        init = {}

    model_name: str = init.get("model", "BAAI/bge-m3")
    default_batch_size: int = int(init.get("batch_size", 32))
    default_threshold: float = float(init.get("threshold", 0.92))

    from sentence_transformers import SentenceTransformer  # noqa: PLC0415
    model = SentenceTransformer(model_name)

    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg: dict = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.stdout.write(json.dumps({"ok": False, "error": f"bad JSON: {exc}"}) + "\n")
            sys.stdout.flush()
            continue

        if msg.get("shutdown"):
            break

        req = msg.get("request", {})
        texts: list[str] = req.get("texts", [])
        threshold: float = float(req.get("threshold", default_threshold))
        batch_size: int = int(req.get("batch_size", default_batch_size))

        try:
            result = _compute_assignments(model, texts, threshold, batch_size)
            sys.stdout.write(json.dumps({"ok": True, "result": result}) + "\n")
        except Exception as exc:
            sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
