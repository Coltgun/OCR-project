"""
Tests for HybridCorrectionStage.

All delegate stage calls are mocked via patch.object on _apply_stage so no
real BERT or LLM subprocess is needed.  Tests cover: registry, tier routing,
merge order, threshold defaults, invalid threshold fallback, empty tier
handling, and _apply_stage error/missing-stage fallbacks.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import call, patch

import pytest

from core.types import BoundingBox, OCRResult
from ocr.stages.base import PostProcessStage
from ocr.stages.hybrid_correction import HybridCorrectionStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(
    text: str,
    confidence: float,
    image_id: str = "1/0001",
) -> OCRResult:
    return OCRResult(
        text=text,
        confidence=confidence,
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        image_id=image_id,
    )


def passthrough(results: list[OCRResult], config: dict) -> list[OCRResult]:
    """Identity correction — returns originals unchanged."""
    return results


def suffix_correct(suffix: str):
    """Return a correction function that appends *suffix* to each text."""
    def _correct(results: list[OCRResult], config: dict) -> list[OCRResult]:
        return [replace(r, text=r.text + suffix) for r in results]
    return _correct


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_hybrid_correction(self) -> None:
        assert PostProcessStage.get("hybrid_correction") is HybridCorrectionStage

    def test_stage_id(self) -> None:
        assert HybridCorrectionStage().stage_id == "hybrid_correction"


# ---------------------------------------------------------------------------
# Tier routing
# ---------------------------------------------------------------------------

class TestTierRouting:
    _cfg: dict = {"hybrid_high_threshold": 0.90, "hybrid_low_threshold": 0.70}

    def _patch_apply(self, mid_fn=passthrough, low_fn=passthrough):
        from ocr.stages.bert_correction import BertCorrectionStage
        from ocr.stages.llm_correction import LlmCorrectionStage
        def side_effect(stage, results, config):
            if isinstance(stage, BertCorrectionStage):
                return mid_fn(results, config)
            if isinstance(stage, LlmCorrectionStage):
                return low_fn(results, config)
            return results
        return patch.object(HybridCorrectionStage, "_apply_stage", side_effect=side_effect)

    def test_high_confidence_not_corrected(self) -> None:
        stage = HybridCorrectionStage()
        r = make_result("高置信度", confidence=0.95)
        with self._patch_apply(
            mid_fn=suffix_correct("_BERT"),
            low_fn=suffix_correct("_LLM"),
        ):
            out = stage.process([r], self._cfg)
        assert out[0].text == "高置信度"

    def test_mid_confidence_goes_to_bert(self) -> None:
        stage = HybridCorrectionStage()
        r = make_result("中置信度", confidence=0.80)
        with self._patch_apply(mid_fn=suffix_correct("_BERT")):
            out = stage.process([r], self._cfg)
        assert out[0].text == "中置信度_BERT"

    def test_low_confidence_goes_to_llm(self) -> None:
        stage = HybridCorrectionStage()
        r = make_result("低置信度", confidence=0.50)
        with self._patch_apply(low_fn=suffix_correct("_LLM")):
            out = stage.process([r], self._cfg)
        assert out[0].text == "低置信度_LLM"

    def test_exact_high_threshold_is_high_tier(self) -> None:
        """conf == high_threshold → high tier (pass through)."""
        stage = HybridCorrectionStage()
        r = make_result("边界", confidence=0.90)
        with self._patch_apply(mid_fn=suffix_correct("_BERT")):
            out = stage.process([r], self._cfg)
        assert out[0].text == "边界"

    def test_exact_low_threshold_is_mid_tier(self) -> None:
        """conf == low_threshold → mid tier (BERT)."""
        stage = HybridCorrectionStage()
        r = make_result("边界", confidence=0.70)
        with self._patch_apply(mid_fn=suffix_correct("_BERT")):
            out = stage.process([r], self._cfg)
        assert out[0].text == "边界_BERT"


# ---------------------------------------------------------------------------
# Reading order preserved
# ---------------------------------------------------------------------------

class TestReadingOrder:
    _cfg: dict = {"hybrid_high_threshold": 0.90, "hybrid_low_threshold": 0.70}

    def test_mixed_tiers_merged_in_original_order(self) -> None:
        stage = HybridCorrectionStage()
        results = [
            make_result("A", confidence=0.95),   # high → unchanged
            make_result("B", confidence=0.80),   # mid  → _BERT
            make_result("C", confidence=0.50),   # low  → _LLM
            make_result("D", confidence=0.92),   # high → unchanged
            make_result("E", confidence=0.75),   # mid  → _BERT
        ]

        from ocr.stages.bert_correction import BertCorrectionStage
        from ocr.stages.llm_correction import LlmCorrectionStage
        def apply_side(s, res, config):
            if isinstance(s, BertCorrectionStage):
                return [replace(r, text=r.text + "_BERT") for r in res]
            if isinstance(s, LlmCorrectionStage):
                return [replace(r, text=r.text + "_LLM") for r in res]
            return res

        with patch.object(HybridCorrectionStage, "_apply_stage", side_effect=apply_side):
            out = stage.process(results, self._cfg)

        assert [r.text for r in out] == [
            "A", "B_BERT", "C_LLM", "D", "E_BERT"
        ]

    def test_all_same_tier_order_unchanged(self) -> None:
        stage = HybridCorrectionStage()
        results = [make_result(f"文字{i}", confidence=0.95) for i in range(5)]

        def apply_side(s, res, config):
            return res

        with patch.object(HybridCorrectionStage, "_apply_stage", side_effect=apply_side):
            out = stage.process(results, self._cfg)
        assert [r.text for r in out] == [f"文字{i}" for i in range(5)]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_returns_empty(self) -> None:
        stage = HybridCorrectionStage()
        assert stage.process([], {}) == []

    def test_single_high_result(self) -> None:
        stage = HybridCorrectionStage()
        r = make_result("文字", confidence=0.99)
        with patch.object(HybridCorrectionStage, "_apply_stage", return_value=[r]):
            out = stage.process([r], {})
        assert out[0].text == "文字"

    def test_invalid_thresholds_use_defaults(self) -> None:
        """low >= high is invalid — should fall back to defaults."""
        stage = HybridCorrectionStage()
        results = [make_result("文字", confidence=0.80)]
        cfg = {"hybrid_high_threshold": 0.50, "hybrid_low_threshold": 0.80}

        def apply_side(s, res, config):
            return [replace(r, text=r.text + "_BERT") for r in res]

        with patch.object(HybridCorrectionStage, "_apply_stage", side_effect=apply_side):
            out = stage.process(results, cfg)
        # With defaults (low=0.70, high=0.90), conf=0.80 → mid → BERT
        assert out[0].text == "文字_BERT"

    def test_default_thresholds_applied_when_absent(self) -> None:
        from ocr.stages.bert_correction import BertCorrectionStage
        stage = HybridCorrectionStage()
        r_high = make_result("高", confidence=0.95)
        r_mid = make_result("中", confidence=0.80)
        r_low = make_result("低", confidence=0.60)

        def apply_side(s, res, config):
            if isinstance(s, BertCorrectionStage):
                return [replace(r, text=r.text + "_B") for r in res]
            return [replace(r, text=r.text + "_L") for r in res]

        with patch.object(HybridCorrectionStage, "_apply_stage", side_effect=apply_side):
            out = stage.process([r_high, r_mid, r_low], {})
        assert out[0].text == "高"
        assert out[1].text == "中_B"
        assert out[2].text == "低_L"


# ---------------------------------------------------------------------------
# _apply_stage — error handling
# ---------------------------------------------------------------------------

class TestApplyStage:
    def test_stage_exception_returns_originals(self) -> None:
        from ocr.stages.bert_correction import BertCorrectionStage
        results = [make_result("文字", confidence=0.5)]
        broken = BertCorrectionStage()
        broken.process = lambda r, c: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore
        out = HybridCorrectionStage._apply_stage(broken, results, {})
        assert out == results

    def test_empty_results_returns_empty(self) -> None:
        from ocr.stages.bert_correction import BertCorrectionStage
        out = HybridCorrectionStage._apply_stage(BertCorrectionStage(), [], {})
        assert out == []


# ---------------------------------------------------------------------------
# Instance reuse
# ---------------------------------------------------------------------------

class TestInstanceReuse:
    def test_child_stages_instantiated_once(self) -> None:
        from ocr.stages.bert_correction import BertCorrectionStage
        from ocr.stages.llm_correction import LlmCorrectionStage
        stage = HybridCorrectionStage()
        assert isinstance(stage._bert_stage, BertCorrectionStage)
        assert isinstance(stage._llm_stage, LlmCorrectionStage)

    def test_same_instances_used_across_calls(self) -> None:
        """Calling process() twice must use the same child instances."""
        stage = HybridCorrectionStage()
        bert_id = id(stage._bert_stage)
        llm_id = id(stage._llm_stage)
        with patch.object(HybridCorrectionStage, "_apply_stage", side_effect=lambda s, r, c: r):
            stage.process([make_result("a", 0.5)], {})
            stage.process([make_result("b", 0.5)], {})
        assert id(stage._bert_stage) == bert_id
        assert id(stage._llm_stage) == llm_id


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_hybrid_correction_present_in_hybrid_tiered(self) -> None:
        from ocr.pipeline import Pipeline
        p = Pipeline("HYBRID_TIERED", {})
        assert "hybrid_correction" in p.stage_ids
