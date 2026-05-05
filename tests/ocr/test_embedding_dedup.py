"""
Tests for EmbeddingDeduplicationStage.

All subprocess calls are mocked — no torch/BGE-M3 import required.
The stage logic (group resolution, reading order, confidence winner) is
tested directly.  The subprocess script builder is tested for structural
correctness only.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.types import BoundingBox, OCRResult
from ocr.stages.base import PostProcessStage
from ocr.stages.embedding_dedup import EmbeddingDeduplicationStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(
    text: str,
    confidence: float = 0.9,
    image_id: str = "1/0001",
) -> OCRResult:
    return OCRResult(
        text=text,
        confidence=confidence,
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        image_id=image_id,
    )


def identity_assignments(n: int) -> list[int]:
    """No duplicates — each result is its own canonical."""
    return list(range(n))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_embedding_dedup(self) -> None:
        assert PostProcessStage.get("embedding_dedup") is EmbeddingDeduplicationStage

    def test_stage_id(self) -> None:
        assert EmbeddingDeduplicationStage().stage_id == "embedding_dedup"


# ---------------------------------------------------------------------------
# _resolve_groups — pure Python, no subprocess
# ---------------------------------------------------------------------------

class TestResolveGroups:
    def test_no_duplicates_all_kept(self) -> None:
        results = [make_result(f"文字{i}") for i in range(4)]
        out = EmbeddingDeduplicationStage._resolve_groups(
            results, identity_assignments(4)
        )
        assert [r.text for r in out] == [r.text for r in results]

    def test_duplicate_pair_keeps_higher_confidence(self) -> None:
        low = make_result("重复文字", confidence=0.6)
        high = make_result("重复文字", confidence=0.95)
        # assignments: both in group 0 (canonical = 0)
        out = EmbeddingDeduplicationStage._resolve_groups(
            [low, high], [0, 0]
        )
        assert len(out) == 1
        assert out[0].confidence == 0.95

    def test_equal_confidence_first_occurrence_kept(self) -> None:
        first = make_result("同等置信度", confidence=0.9)
        second = make_result("同等置信度", confidence=0.9)
        out = EmbeddingDeduplicationStage._resolve_groups(
            [first, second], [0, 0]
        )
        assert len(out) == 1
        assert out[0] is first

    def test_three_results_one_group(self) -> None:
        r0 = make_result("A", confidence=0.7)
        r1 = make_result("A", confidence=0.95)
        r2 = make_result("A", confidence=0.8)
        # all in group 0
        out = EmbeddingDeduplicationStage._resolve_groups(
            [r0, r1, r2], [0, 0, 0]
        )
        assert len(out) == 1
        assert out[0].confidence == 0.95

    def test_two_independent_groups(self) -> None:
        r0 = make_result("A组第一", confidence=0.9)
        r1 = make_result("A组第二", confidence=0.8)
        r2 = make_result("B组第一", confidence=0.95)
        r3 = make_result("B组第二", confidence=0.7)
        # [0,0,2,2]: r0+r1 in group 0, r2+r3 in group 2
        out = EmbeddingDeduplicationStage._resolve_groups(
            [r0, r1, r2, r3], [0, 0, 2, 2]
        )
        assert len(out) == 2
        confidences = {r.confidence for r in out}
        assert confidences == {0.9, 0.95}

    def test_reading_order_preserved(self) -> None:
        """Winners must appear in the order of their original index."""
        r0 = make_result("第一", confidence=0.9)
        r1 = make_result("第二", confidence=0.9)  # dup of r0 but lower index wins
        r2 = make_result("第三", confidence=0.9)
        r3 = make_result("第四", confidence=0.95)  # dup of r2
        # r0+r1 group 0, r2+r3 group 2
        out = EmbeddingDeduplicationStage._resolve_groups(
            [r0, r1, r2, r3], [0, 0, 2, 2]
        )
        assert len(out) == 2
        # r0 (idx 0) before r3 (idx 3, winner of group 2)
        assert out[0].text == "第一"
        assert out[1].confidence == 0.95


# ---------------------------------------------------------------------------
# process() — subprocess mocked
# ---------------------------------------------------------------------------

class TestProcess:
    _cfg: dict = {}

    def _patch_subprocess(self, assignments: list[int]):
        """Return a context manager that patches _run_subprocess."""
        return patch.object(
            EmbeddingDeduplicationStage,
            "_run_subprocess",
            return_value=assignments,
        )

    def test_empty_returns_empty(self) -> None:
        stage = EmbeddingDeduplicationStage()
        assert stage.process([], self._cfg) == []

    def test_single_result_returned_unchanged(self) -> None:
        stage = EmbeddingDeduplicationStage()
        r = make_result("单条文字")
        assert stage.process([r], self._cfg) == [r]

    def test_no_duplicates_all_kept(self) -> None:
        stage = EmbeddingDeduplicationStage()
        results = [make_result(f"独特文字{i}") for i in range(3)]
        with self._patch_subprocess(identity_assignments(3)):
            out = stage.process(results, self._cfg)
        assert len(out) == 3

    def test_duplicates_removed(self) -> None:
        stage = EmbeddingDeduplicationStage()
        results = [make_result("重复"), make_result("重复"), make_result("独特")]
        # r0+r1 are duplicates (both canonical=0), r2 is independent
        with self._patch_subprocess([0, 0, 2]):
            out = stage.process(results, self._cfg)
        assert len(out) == 2

    def test_subprocess_failure_returns_results_unchanged(self) -> None:
        stage = EmbeddingDeduplicationStage()
        results = [make_result("文字一"), make_result("文字二")]
        with patch.object(
            EmbeddingDeduplicationStage,
            "_run_subprocess",
            side_effect=RuntimeError("subprocess failed"),
        ):
            out = stage.process(results, self._cfg)
        assert out == results

    def test_config_keys_forwarded_to_subprocess(self) -> None:
        stage = EmbeddingDeduplicationStage()
        results = [make_result("文字一"), make_result("文字二")]
        cfg = {
            "embedding_model": "BAAI/bge-m3",
            "embedding_threshold": 0.95,
            "embedding_batch_size": 16,
        }
        with patch.object(
            EmbeddingDeduplicationStage,
            "_run_subprocess",
            return_value=[0, 1],
        ) as mock_sub:
            stage.process(results, cfg)
        mock_sub.assert_called_once_with(
            ["文字一", "文字二"], "BAAI/bge-m3", 0.95, 16
        )


# ---------------------------------------------------------------------------
# _run_subprocess — mocked at subprocess.run level
# ---------------------------------------------------------------------------

class TestRunSubprocess:
    def _make_completed(self, stdout: str, returncode: int = 0) -> MagicMock:
        m = MagicMock()
        m.returncode = returncode
        m.stdout = stdout
        m.stderr = ""
        return m

    def test_valid_json_returned(self) -> None:
        assignments = [0, 0, 2]
        with patch("subprocess.run", return_value=self._make_completed(json.dumps(assignments))):
            result = EmbeddingDeduplicationStage._run_subprocess(
                ["a", "b", "c"], "BAAI/bge-m3", 0.92, 32
            )
        assert result == assignments

    def test_subprocess_nonzero_raises_runtime_error(self) -> None:
        with patch("subprocess.run", return_value=self._make_completed("", returncode=1)):
            with pytest.raises(RuntimeError, match="subprocess failed"):
                EmbeddingDeduplicationStage._run_subprocess(
                    ["a"], "BAAI/bge-m3", 0.92, 32
                )

    def test_empty_output_raises_runtime_error(self) -> None:
        with patch("subprocess.run", return_value=self._make_completed("")):
            with pytest.raises(RuntimeError, match="empty output"):
                EmbeddingDeduplicationStage._run_subprocess(
                    ["a"], "BAAI/bge-m3", 0.92, 32
                )

    def test_invalid_json_raises_runtime_error(self) -> None:
        with patch("subprocess.run", return_value=self._make_completed("not-json")):
            with pytest.raises(RuntimeError, match="invalid JSON"):
                EmbeddingDeduplicationStage._run_subprocess(
                    ["a"], "BAAI/bge-m3", 0.92, 32
                )

    def test_wrong_length_raises_runtime_error(self) -> None:
        with patch("subprocess.run", return_value=self._make_completed("[0]")):
            with pytest.raises(RuntimeError, match="unexpected shape"):
                EmbeddingDeduplicationStage._run_subprocess(
                    ["a", "b", "c"], "BAAI/bge-m3", 0.92, 32
                )


# ---------------------------------------------------------------------------
# _build_subprocess_script — structural checks
# ---------------------------------------------------------------------------

class TestBuildSubprocessScript:
    def test_script_contains_sentence_transformers_import(self) -> None:
        from ocr.stages.embedding_dedup import _build_subprocess_script
        script = _build_subprocess_script('{"texts":[],"model":"m","threshold":0.9,"batch_size":32}')
        assert "sentence_transformers" in script

    def test_script_registers_nvidia_dirs(self) -> None:
        from ocr.stages.embedding_dedup import _build_subprocess_script
        script = _build_subprocess_script('{"texts":[],"model":"m","threshold":0.9,"batch_size":32}')
        assert "add_dll_directory" in script

    def test_script_prints_json(self) -> None:
        from ocr.stages.embedding_dedup import _build_subprocess_script
        script = _build_subprocess_script('{"texts":[],"model":"m","threshold":0.9,"batch_size":32}')
        assert "print(json.dumps" in script


# ---------------------------------------------------------------------------
# Persistent subprocess path
# ---------------------------------------------------------------------------

class TestPersistentPath:
    _cfg: dict = {"embedding_persistent_subprocess": True}

    def test_persistent_path_deduplicates(self) -> None:
        results = [make_result("文字A"), make_result("文字B")]
        # group_assignments: both map to 0 → only first kept
        with patch(
            "ocr.stages.embedding_dedup.TorchSubprocessService.call",
            return_value=[0, 0],
        ):
            stage = EmbeddingDeduplicationStage()
            out = stage.process(results, self._cfg)
        assert len(out) == 1

    def test_persistent_path_no_dedup(self) -> None:
        results = [make_result("文字A"), make_result("文字B")]
        with patch(
            "ocr.stages.embedding_dedup.TorchSubprocessService.call",
            return_value=[0, 1],
        ):
            stage = EmbeddingDeduplicationStage()
            out = stage.process(results, self._cfg)
        assert len(out) == 2

    def test_service_reused_on_second_call(self) -> None:
        results = [make_result("文字A"), make_result("文字B")]
        with patch(
            "ocr.stages.embedding_dedup.TorchSubprocessService.call",
            return_value=[0, 1],
        ) as mock_call:
            stage = EmbeddingDeduplicationStage()
            stage.process(results, self._cfg)
            svc1 = stage._service
            stage.process(results, self._cfg)
            svc2 = stage._service
        assert svc1 is svc2
        assert mock_call.call_count == 2

    def test_unload_shuts_down_service(self) -> None:
        results = [make_result("文字A"), make_result("文字B")]
        with patch(
            "ocr.stages.embedding_dedup.TorchSubprocessService.call",
            return_value=[0, 1],
        ):
            stage = EmbeddingDeduplicationStage()
            stage.process(results, self._cfg)

        mock_svc = MagicMock()
        stage._service = mock_svc
        stage.unload()
        mock_svc.shutdown.assert_called_once()
        assert stage._service is None

    def test_persistent_failure_returns_unchanged(self) -> None:
        results = [make_result("文字A"), make_result("文字B")]
        with patch(
            "ocr.stages.embedding_dedup.TorchSubprocessService.call",
            side_effect=RuntimeError("child OOM"),
        ):
            stage = EmbeddingDeduplicationStage()
            out = stage.process(results, self._cfg)
        assert len(out) == 2

    def test_group_assignments_parity_with_old_loop(self) -> None:
        """Verify matmul in subprocess gives identical group_assignments to the old loop.

        Uses _resolve_groups directly (no subprocess) to validate the algorithm.
        """
        import numpy as np

        n = 10
        texts = [f"text{i}" for i in range(n)]
        results = [make_result(t, confidence=float(i) / n) for i, t in enumerate(texts)]

        # Build synthetic embeddings: first 3 are very similar, rest are distinct
        rng = np.random.default_rng(42)
        embeddings = rng.standard_normal((n, 64)).astype(np.float32)
        # Force first 3 to be near-identical
        embeddings[1] = embeddings[0] + rng.standard_normal(64).astype(np.float32) * 0.001
        embeddings[2] = embeddings[0] + rng.standard_normal(64).astype(np.float32) * 0.001
        # L2-normalise
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms

        threshold = 0.95

        # Old O(n²) loop
        assignments_loop = list(range(n))
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(np.dot(embeddings[i], embeddings[j]))
                if sim >= threshold:
                    root_i = assignments_loop[i]
                    if assignments_loop[j] == j:
                        assignments_loop[j] = root_i

        # Matmul version (same as _embedding_subprocess.py)
        sims = embeddings @ embeddings.T
        assignments_matmul = list(range(n))
        for i in range(n):
            for j in range(i + 1, n):
                if float(sims[i, j]) >= threshold:
                    root_i = assignments_matmul[i]
                    if assignments_matmul[j] == j:
                        assignments_matmul[j] = root_i

        assert assignments_loop == assignments_matmul

        # Both should produce the same kept set
        kept_loop = EmbeddingDeduplicationStage._resolve_groups(results, assignments_loop)
        kept_matmul = EmbeddingDeduplicationStage._resolve_groups(results, assignments_matmul)
        assert [r.text for r in kept_loop] == [r.text for r in kept_matmul]
