"""
HybridCorrectionStage — confidence-routed OCR correction.

Registration key: "hybrid_correction"

Routes each OCRResult to the cheapest corrector that can handle its confidence
level, then merges results back in the original reading order.

Routing logic:
    confidence >= hybrid_high_threshold   → pass through unchanged (already reliable)
    hybrid_low_threshold <= conf < high   → BertCorrectionStage  (fast, local, torch)
    confidence < hybrid_low_threshold     → LlmCorrectionStage   (slower, higher quality)

This avoids running a heavy LLM on every result while still applying
deep correction where OCR quality is poor.

Config keys consumed:
    hybrid_high_threshold  (float) Min confidence to skip correction  [default: 0.90]
    hybrid_low_threshold   (float) Max confidence for LLM tier        [default: 0.70]
    + all keys consumed by BertCorrectionStage and LlmCorrectionStage

Thresholds must satisfy: 0 <= low < high <= 1.
If either stage is unavailable (not registered / subprocess fails), the
results for that tier fall back to their original texts.
"""

from __future__ import annotations

import logging

from core.types import OCRResult
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

_DEFAULT_HIGH = 0.90
_DEFAULT_LOW = 0.70


class HybridCorrectionStage(PostProcessStage, register_as="hybrid_correction"):
    """Route OCR results to appropriate correction stage by confidence tier.

    - High confidence  (>= high_threshold): unchanged.
    - Mid confidence   (low <= conf < high): BertCorrectionStage.
    - Low confidence   (< low_threshold):    LlmCorrectionStage.

    Results are merged back into their original reading order.
    """

    @property
    def stage_id(self) -> str:
        """Stage identifier."""
        return "hybrid_correction"

    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Apply confidence-routed correction to *results*.

        Args:
            results: Input OCR results.
            config:  Full application config dict.

        Returns:
            Corrected results in the original reading order.
        """
        if not results:
            return results

        high: float = float(config.get("hybrid_high_threshold", _DEFAULT_HIGH))
        low: float = float(config.get("hybrid_low_threshold", _DEFAULT_LOW))

        if not (0.0 <= low < high <= 1.0):
            logger.warning(
                "HybridCorrectionStage: invalid thresholds (low=%.2f, high=%.2f) "
                "— using defaults (%.2f, %.2f).",
                low, high, _DEFAULT_LOW, _DEFAULT_HIGH,
            )
            low, high = _DEFAULT_LOW, _DEFAULT_HIGH

        # Partition into three tiers, preserving original index for merge
        high_tier: list[tuple[int, OCRResult]] = []
        mid_tier: list[tuple[int, OCRResult]] = []
        low_tier: list[tuple[int, OCRResult]] = []

        for idx, result in enumerate(results):
            if result.confidence >= high:
                high_tier.append((idx, result))
            elif result.confidence >= low:
                mid_tier.append((idx, result))
            else:
                low_tier.append((idx, result))

        logger.debug(
            "HybridCorrectionStage: high=%d, mid=%d, low=%d results.",
            len(high_tier), len(mid_tier), len(low_tier),
        )

        # Correct mid tier with BERT
        mid_corrected = self._apply_stage("bert_correction", [r for _, r in mid_tier], config)
        # Correct low tier with LLM
        low_corrected = self._apply_stage("llm_correction", [r for _, r in low_tier], config)

        # Merge all three tiers back into original order
        merged: dict[int, OCRResult] = {}
        for (idx, _), result in zip(high_tier, [r for _, r in high_tier]):
            merged[idx] = result
        for (idx, _), result in zip(mid_tier, mid_corrected):
            merged[idx] = result
        for (idx, _), result in zip(low_tier, low_corrected):
            merged[idx] = result

        return [merged[i] for i in range(len(results))]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_stage(stage_key: str, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Apply a registered stage by key; return originals if unavailable.

        Args:
            stage_key: Registry key of the stage to apply.
            results:   Results to process.
            config:    Full application config dict.

        Returns:
            Processed results, or originals on any error.
        """
        if not results:
            return results

        try:
            cls = PostProcessStage.get(stage_key)
            stage = cls()
            return stage.process(results, config)
        except KeyError:
            logger.warning(
                "HybridCorrectionStage: stage '%s' not registered — "
                "keeping tier unchanged.",
                stage_key,
            )
            return results
        except Exception as exc:
            logger.error(
                "HybridCorrectionStage: stage '%s' raised %s: %s — "
                "keeping tier unchanged.",
                stage_key, type(exc).__name__, exc,
            )
            return results
