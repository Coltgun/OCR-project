"""Tests for the Pipeline orchestrator."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from core.types import OCRResult
from ocr.pipeline import Pipeline, PIPELINE_MODES
from ocr.stages.base import PostProcessStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(text: str, confidence: float = 0.9) -> OCRResult:
    return OCRResult(text=text, confidence=confidence)


# ---------------------------------------------------------------------------
# PIPELINE_MODES structure
# ---------------------------------------------------------------------------

class TestPipelineModes:
    def test_all_expected_modes_present(self) -> None:
        expected = {
            "LOCAL_FAST", "LOCAL_STANDARD", "LOCAL_LLM",
            "HYBRID_TIERED", "API_STANDARD", "API_FULL",
        }
        assert expected <= set(PIPELINE_MODES.keys())

    def test_local_fast_starts_with_cleanup(self) -> None:
        assert PIPELINE_MODES["LOCAL_FAST"][0] == "cleanup"

    def test_local_fast_second_stage_is_rule_corrections(self) -> None:
        assert PIPELINE_MODES["LOCAL_FAST"][1] == "rule_corrections"

    def test_all_modes_are_lists(self) -> None:
        for mode, stages in PIPELINE_MODES.items():
            assert isinstance(stages, list), f"Mode '{mode}' stages must be a list"

    def test_no_mode_has_empty_stage_list(self) -> None:
        for mode, stages in PIPELINE_MODES.items():
            assert len(stages) > 0, f"Mode '{mode}' has no stages"


# ---------------------------------------------------------------------------
# Pipeline construction
# ---------------------------------------------------------------------------

class TestPipelineConstruction:
    def test_local_fast_builds_with_registered_stages(self) -> None:
        p = Pipeline("LOCAL_FAST", {})
        assert "cleanup" in p.stage_ids
        assert "rule_corrections" in p.stage_ids

    def test_unknown_mode_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown pipeline mode"):
            Pipeline("NONEXISTENT_MODE", {})

    def test_minhash_dedup_present_in_local_fast(self) -> None:
        p = Pipeline("LOCAL_FAST", {})
        assert "minhash_dedup" in p.stage_ids

    def test_bert_correction_present_in_local_standard(self) -> None:
        p = Pipeline("LOCAL_STANDARD", {})
        assert "bert_correction" in p.stage_ids

    def test_llm_correction_present_in_local_llm(self) -> None:
        p = Pipeline("LOCAL_LLM", {})
        assert "llm_correction" in p.stage_ids

    def test_openrouter_correction_present_in_api_standard(self) -> None:
        p = Pipeline("API_STANDARD", {})
        assert "openrouter_correction" in p.stage_ids

    def test_hybrid_correction_present_in_hybrid_tiered(self) -> None:
        p = Pipeline("HYBRID_TIERED", {})
        assert "hybrid_correction" in p.stage_ids

    def test_openrouter_dedup_present_in_api_full(self) -> None:
        p = Pipeline("API_FULL", {})
        assert "openrouter_dedup" in p.stage_ids

    def test_unregistered_stage_skipped_gracefully(self) -> None:
        """_build_stages skips unknown keys without raising."""
        import ocr.pipeline as pipeline_mod
        patched = {**PIPELINE_MODES, "TEST_SKIP": ["cleanup", "not_yet_implemented_stage"]}
        with patch.object(pipeline_mod, "PIPELINE_MODES", patched):
            p = Pipeline("TEST_SKIP", {})
        assert "not_yet_implemented_stage" not in p.stage_ids
        assert "cleanup" in p.stage_ids

    def test_available_modes_returns_all(self) -> None:
        modes = Pipeline.available_modes()
        assert "LOCAL_FAST" in modes
        assert len(modes) == len(PIPELINE_MODES)

    def test_mode_property(self) -> None:
        p = Pipeline("LOCAL_FAST", {})
        assert p.mode == "LOCAL_FAST"


# ---------------------------------------------------------------------------
# Pipeline.process()
# ---------------------------------------------------------------------------

class TestPipelineProcess:
    def test_process_returns_list_of_ocr_results(self) -> None:
        p = Pipeline("LOCAL_FAST", {})
        results = [make_result("你好世界", 0.9)]
        out = p.process(results)
        assert isinstance(out, list)
        assert all(isinstance(r, OCRResult) for r in out)

    def test_cleanup_stage_runs(self) -> None:
        p = Pipeline("LOCAL_FAST", {"cleanup_confidence_threshold": 0.5})
        results = [
            make_result("你 好 世 界", 0.9),
            make_result("低置信度", 0.1),
        ]
        out = p.process(results)
        assert len(out) == 1
        assert out[0].text == "你好世界"

    def test_rule_corrections_stage_runs(self) -> None:
        p = Pipeline("LOCAL_FAST", {})
        results = [make_result("自已为是", 0.9)]
        out = p.process(results)
        assert out[0].text == "自己为是"

    def test_empty_input_returns_empty(self) -> None:
        p = Pipeline("LOCAL_FAST", {})
        assert p.process([]) == []

    def test_stage_exception_does_not_crash_pipeline(self) -> None:
        """A crashing stage is logged and skipped; later stages still run."""

        class BrokenStage(PostProcessStage, register_as="_test_broken_stage"):
            @property
            def stage_id(self) -> str:
                return "_test_broken_stage"

            def process(self, results, config):
                raise RuntimeError("intentional test failure")

        original_fast = PIPELINE_MODES["LOCAL_FAST"].copy()
        PIPELINE_MODES["LOCAL_FAST"] = ["_test_broken_stage", "cleanup", "rule_corrections"]
        try:
            p = Pipeline("LOCAL_FAST", {})
            results = [make_result("你好", 0.9)]
            out = p.process(results)
            assert isinstance(out, list)
        finally:
            PIPELINE_MODES["LOCAL_FAST"] = original_fast
            PostProcessStage._registry.pop("_test_broken_stage", None)

    def test_fullwidth_and_rule_correction_chain(self) -> None:
        """Cleanup (fullwidth) then rule_corrections both apply."""
        p = Pipeline("LOCAL_FAST", {})
        results = [make_result("自已为是１２３", 0.9)]
        out = p.process(results)
        assert "己" in out[0].text
        assert "123" in out[0].text


# ---------------------------------------------------------------------------
# Pipeline with all registered modes (smoke test)
# ---------------------------------------------------------------------------

class TestPipelineSmokeAllModes:
    @pytest.mark.parametrize("mode", list(PIPELINE_MODES.keys()))
    def test_pipeline_constructs_for_all_modes(self, mode: str) -> None:
        """All modes must construct without error (unregistered stages are skipped)."""
        p = Pipeline(mode, {})
        assert p.mode == mode

    @pytest.mark.parametrize("mode", list(PIPELINE_MODES.keys()))
    def test_pipeline_processes_for_all_modes(self, mode: str) -> None:
        """All modes must process without error."""
        p = Pipeline(mode, {})
        results = [make_result("你好世界", 0.9)]
        out = p.process(results)
        assert isinstance(out, list)
