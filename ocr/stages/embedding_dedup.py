"""
EmbeddingDeduplicationStage — semantic near-duplicate removal using BGE-M3 embeddings.

Registration key: "embedding_dedup"

Architecture constraint (CRITICAL):
    sentence_transformers pulls in PyTorch.  Paddle (cu126) and torch (cu121)
    bundle incompatible cuDNN DLL builds — they MUST NOT be imported in the same
    process (WinError 127).  All torch/BGE-M3 work therefore runs in a clean
    subprocess, exactly as OCRWorker does for paddle.

Algorithm:
    1. Serialise OCRResult texts to JSON and pass to a subprocess.
    2. Subprocess loads BGE-M3, encodes all texts, computes pairwise cosine
       similarity, and returns a list of duplicate-group assignments.
    3. Main process resolves groups (highest-confidence winner per group,
       reading order preserved) without ever importing torch.

Config keys consumed:
    embedding_model       (str)   HuggingFace model id  [default: BAAI/bge-m3]
    embedding_threshold   (float) Cosine similarity threshold  [default: 0.92]
    embedding_batch_size  (int)   Encoding batch size          [default: 32]

Why a second dedup stage after minhash_dedup:
    MinHash detects near-identical strings (surface-level).  BGE-M3 detects
    semantically equivalent sentences that differ in wording — e.g. OCR
    variants like "他走了。" and "地走了。" (一/二 character misread).
    Using both in sequence catches different classes of duplicate.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys

from core.types import OCRResult
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "BAAI/bge-m3"
_DEFAULT_THRESHOLD = 0.92
_DEFAULT_BATCH_SIZE = 32


class EmbeddingDeduplicationStage(PostProcessStage, register_as="embedding_dedup"):
    """Remove semantically duplicate OCRResult entries using BGE-M3 cosine similarity.

    Runs the embedding model in a subprocess to enforce torch/paddle isolation.
    Group resolution keeps the highest-confidence result, preserving reading order.
    """

    @property
    def stage_id(self) -> str:
        """Stage identifier."""
        return "embedding_dedup"

    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Remove semantic duplicates from *results*.

        Args:
            results: Input OCR results (typically already minhash-deduped).
            config:  Full application config dict.

        Returns:
            De-duplicated list in original reading order.
        """
        if len(results) < 2:
            return results

        model: str = str(config.get("embedding_model", _DEFAULT_MODEL))
        threshold: float = float(config.get("embedding_threshold", _DEFAULT_THRESHOLD))
        batch_size: int = int(config.get("embedding_batch_size", _DEFAULT_BATCH_SIZE))

        texts = [r.text for r in results]

        try:
            group_assignments = self._run_subprocess(texts, model, threshold, batch_size)
        except Exception as exc:
            logger.error(
                "EmbeddingDeduplicationStage: subprocess failed (%s) — "
                "returning results unchanged.",
                exc,
            )
            return results

        kept = self._resolve_groups(results, group_assignments)
        removed = len(results) - len(kept)
        if removed:
            logger.info(
                "EmbeddingDeduplicationStage: removed %d semantic duplicate(s) "
                "(threshold=%.2f, %d results remain).",
                removed, threshold, len(kept),
            )
        return kept

    # ------------------------------------------------------------------
    # Subprocess dispatch
    # ------------------------------------------------------------------

    @staticmethod
    def _run_subprocess(
        texts: list[str],
        model: str,
        threshold: float,
        batch_size: int,
    ) -> list[int]:
        """Run BGE-M3 dedup in a clean subprocess.

        Returns a list of length len(texts) where each element is the
        canonical index for that text (i.e. texts[i] is a duplicate of
        texts[group_assignments[i]]; if not a duplicate, group_assignments[i] == i).

        Raises:
            RuntimeError: If the subprocess fails or returns invalid JSON.
        """
        payload = json.dumps({
            "texts": texts,
            "model": model,
            "threshold": threshold,
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
            raise RuntimeError(f"Embedding subprocess failed: {last}")

        output = result.stdout.strip()
        if not output:
            raise RuntimeError("Embedding subprocess returned empty output.")

        try:
            assignments = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Embedding subprocess returned invalid JSON: {exc}"
            ) from exc

        if not isinstance(assignments, list) or len(assignments) != len(texts):
            raise RuntimeError(
                f"Embedding subprocess returned unexpected shape: {assignments!r}"
            )

        return assignments

    # ------------------------------------------------------------------
    # Group resolution (no torch — pure Python)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_groups(
        results: list[OCRResult],
        group_assignments: list[int],
    ) -> list[OCRResult]:
        """Keep the highest-confidence result per duplicate group.

        Args:
            results:          Input OCR results.
            group_assignments: group_assignments[i] == canonical index for result i.

        Returns:
            De-duplicated list in original reading order.
        """
        groups: dict[int, list[tuple[int, OCRResult]]] = {}
        for idx, result in enumerate(results):
            canonical = group_assignments[idx]
            groups.setdefault(canonical, []).append((idx, result))

        best: dict[int, tuple[int, OCRResult]] = {}
        for canonical, members in groups.items():
            winner_idx, winner = max(
                members, key=lambda t: (t[1].confidence, -t[0])
            )
            best[canonical] = (winner_idx, winner)

        ordered = sorted(best.values(), key=lambda t: t[0])
        return [result for _, result in ordered]


# ---------------------------------------------------------------------------
# Subprocess script builder
# ---------------------------------------------------------------------------

def _build_subprocess_script(payload_json: str) -> str:
    """Build the Python script that runs inside the isolated subprocess.

    The subprocess:
      1. Registers NVIDIA DLL dirs (same pattern as OCRWorker).
      2. Imports sentence_transformers (torch-dependent).
      3. Encodes all texts with BGE-M3.
      4. Computes pairwise cosine similarity.
      5. Builds group_assignments list.
      6. Prints JSON to stdout.

    Uses upper-triangle cosine similarity to avoid O(n²) memory for large
    batches; for typical OCR sessions (< 500 lines) this is negligible.
    """
    # Escape for embedding in a triple-quoted string inside the script
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
threshold = float(payload["threshold"])
batch_size = int(payload["batch_size"])

from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer(model_name)
embeddings = model.encode(
    texts,
    batch_size=batch_size,
    normalize_embeddings=True,
    show_progress_bar=False,
)

n = len(texts)
# group_assignments[i] = canonical index (lowest index in duplicate group)
group_assignments = list(range(n))

# Upper-triangle pairwise cosine similarity (embeddings are L2-normalised)
for i in range(n):
    for j in range(i + 1, n):
        sim = float(np.dot(embeddings[i], embeddings[j]))
        if sim >= threshold:
            # Canonicalise j to the root of i's group
            root_i = group_assignments[i]
            if group_assignments[j] == j:
                group_assignments[j] = root_i

print(json.dumps(group_assignments))
'''
