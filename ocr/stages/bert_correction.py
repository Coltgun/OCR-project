"""
BertCorrectionStage — Chinese Spell Correction using MacBERT via pycorrector.

Registration key: "bert_correction"

Architecture constraint (CRITICAL):
    pycorrector.MacBertCorrector imports PyTorch.  Paddle (cu126) and torch
    (cu121) bundle incompatible cuDNN DLL builds — MUST NOT share a process.
    All correction work runs in a clean subprocess, returning results to the
    caller via JSON, exactly as OCRWorker and EmbeddingDeduplicationStage do.

Algorithm:
    1. Serialise OCRResult texts + config to JSON and pass to subprocess.
    2. Subprocess loads MacBertCorrector, corrects each text, and writes
       corrected texts as a JSON list to stdout.
    3. Main process replaces each result's text with the corrected version,
       preserving confidence, bbox, and image_id unchanged.

Design decision — confidence unchanged:
    MacBERT correction is structural (character substitution).  The original
    PaddleOCR confidence score reflects visual recognition quality, not
    linguistic correctness.  Keeping it unchanged avoids misleading downstream
    dedup stages that sort by confidence.

Config keys consumed:
    bert_model        (str)   pycorrector model path or name
                              [default: shibing624/macbert4csc-base-chinese]
    bert_max_length   (int)   max token length per sequence  [default: 128]
    bert_batch_size   (int)   correction batch size          [default: 32]
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys

from core.types import OCRResult
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "shibing624/macbert4csc-base-chinese"
_DEFAULT_MAX_LENGTH = 128
_DEFAULT_BATCH_SIZE = 32


class BertCorrectionStage(PostProcessStage, register_as="bert_correction"):
    """Apply MacBERT Chinese Spell Correction to OCR results.

    Runs MacBertCorrector in a subprocess to enforce torch/paddle isolation.
    Texts are corrected in place; confidence, bbox, and image_id are preserved.
    On subprocess failure the original results are returned unchanged.
    """

    @property
    def stage_id(self) -> str:
        """Stage identifier."""
        return "bert_correction"

    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Correct spelling errors in each OCRResult's text.

        Args:
            results: Input OCR results.
            config:  Full application config dict.

        Returns:
            Results with corrected text fields; all other fields unchanged.
        """
        if not results:
            return results

        model: str = str(config.get("bert_model", _DEFAULT_MODEL))
        max_length: int = int(config.get("bert_max_length", _DEFAULT_MAX_LENGTH))
        batch_size: int = int(config.get("bert_batch_size", _DEFAULT_BATCH_SIZE))

        texts = [r.text for r in results]

        try:
            corrected = self._run_subprocess(texts, model, max_length, batch_size)
        except Exception as exc:
            logger.error(
                "BertCorrectionStage: subprocess failed (%s) — "
                "returning results unchanged.",
                exc,
            )
            return results

        if len(corrected) != len(results):
            logger.error(
                "BertCorrectionStage: subprocess returned %d texts for %d inputs — "
                "returning results unchanged.",
                len(corrected), len(results),
            )
            return results

        output: list[OCRResult] = []
        for result, new_text in zip(results, corrected):
            if new_text != result.text:
                logger.debug(
                    "BertCorrectionStage: corrected '%s' → '%s'",
                    result.text, new_text,
                )
            from dataclasses import replace
            output.append(replace(result, text=new_text))
        return output

    # ------------------------------------------------------------------
    # Subprocess dispatch
    # ------------------------------------------------------------------

    @staticmethod
    def _run_subprocess(
        texts: list[str],
        model: str,
        max_length: int,
        batch_size: int,
    ) -> list[str]:
        """Run MacBERT correction in a clean subprocess.

        Returns a list of corrected strings, same length and order as *texts*.

        Raises:
            RuntimeError: If the subprocess fails or returns invalid output.
        """
        payload = json.dumps({
            "texts": texts,
            "model": model,
            "max_length": max_length,
            "batch_size": batch_size,
        })
        script = _build_subprocess_script(payload)

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            stderr_tail = (result.stderr or "").strip().splitlines()
            last = stderr_tail[-1] if stderr_tail else "unknown error"
            raise RuntimeError(f"BertCorrection subprocess failed: {last}")

        output = result.stdout.strip()
        if not output:
            raise RuntimeError("BertCorrection subprocess returned empty output.")

        try:
            corrected = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"BertCorrection subprocess returned invalid JSON: {exc}"
            ) from exc

        if not isinstance(corrected, list):
            raise RuntimeError(
                f"BertCorrection subprocess returned unexpected type: {type(corrected)}"
            )

        return [str(t) for t in corrected]


# ---------------------------------------------------------------------------
# Subprocess script builder
# ---------------------------------------------------------------------------

def _build_subprocess_script(payload_json: str) -> str:
    """Build the Python script that runs inside the isolated subprocess.

    The subprocess:
      1. Registers NVIDIA DLL dirs (same pattern as OCRWorker).
      2. Imports pycorrector (torch-dependent).
      3. Loads MacBertCorrector and corrects all texts in batches.
      4. Prints corrected texts as a JSON list to stdout.
    """
    safe_payload = payload_json.replace("\\", "\\\\").replace('"', '\\"')

    return f'''
import os
import site
import json
import sys

# Register NVIDIA CUDA DLL directories (torch cuDNN requires them on Windows)
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

payload = json.loads("{safe_payload}")
texts = payload["texts"]
model_name = payload["model"]
max_length = int(payload["max_length"])
batch_size = int(payload["batch_size"])

from pycorrector import MacBertCorrector

corrector = MacBertCorrector(model_name_or_path=model_name)

corrected = []
for i in range(0, len(texts), batch_size):
    batch = texts[i : i + batch_size]
    results = corrector.correct_batch(batch, max_length=max_length)
    for item in results:
        corrected.append(item.get("target", item.get("corrected_text", batch[len(corrected) - i])))

print(json.dumps(corrected))
'''
