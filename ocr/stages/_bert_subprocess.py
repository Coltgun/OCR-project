"""
ocr/stages/_bert_subprocess.py — long-lived BERT correction child process.

Protocol (handled by TorchSubprocessService):
    First stdin line:  {"model": "...", "max_length": 128, "batch_size": 32}
    Ready signal:      {"ready": true}
    Per request:       {"request": {"texts": [...], "max_length": N, "batch_size": N}}
    Response:          {"ok": true, "result": ["corrected", ...]}
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


def _correct_batch(corrector, texts: list[str], max_length: int, batch_size: int) -> list[str]:
    corrected: list[str] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        results = corrector.correct_batch(batch, max_length=max_length)
        for idx, item in enumerate(results):
            corrected.append(
                item.get("target", item.get("corrected_text", batch[idx]))
            )
    return corrected


def main() -> None:
    _setup_dlls()

    init_line = sys.stdin.readline()
    try:
        init: dict = json.loads(init_line)
    except (json.JSONDecodeError, ValueError):
        init = {}

    model_name: str = init.get("model", "shibing624/macbert4csc-base-chinese")
    default_max_length: int = int(init.get("max_length", 128))
    default_batch_size: int = int(init.get("batch_size", 32))

    from pycorrector import MacBertCorrector  # noqa: PLC0415
    corrector = MacBertCorrector(model_name_or_path=model_name)

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
        max_length: int = int(req.get("max_length", default_max_length))
        batch_size: int = int(req.get("batch_size", default_batch_size))

        try:
            result = _correct_batch(corrector, texts, max_length, batch_size)
            sys.stdout.write(json.dumps({"ok": True, "result": result}) + "\n")
        except Exception as exc:
            sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
