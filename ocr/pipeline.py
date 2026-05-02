"""
OCR Pipeline Orchestrator.

Defines the available pipeline modes as ordered lists of stage registry keys,
and provides the Pipeline class that executes them.

Adding a new mode: add one entry to PIPELINE_MODES. No other code changes.
Adding a new stage: create the stage file + add its key to the relevant modes.

Pipeline modes:

    LOCAL_FAST      — PaddleOCR → cleanup → rule_corrections → [minhash_dedup]
    LOCAL_STANDARD  — + bert_correction (MacBERT, torch subprocess)
    LOCAL_LLM       — + llm_correction (Ollama)
    HYBRID_TIERED   — confidence-routed: high→done, mid→bert, low→llm
    API_STANDARD    — + openrouter_correction (OpenRouter API)
    API_FULL        — + openrouter_dedup
"""

from __future__ import annotations

import logging
from typing import Sequence

from core.types import OCRResult
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

PIPELINE_MODES: dict[str, list[str]] = {
    "LOCAL_FAST": [
        "cleanup",
        "rule_corrections",
        "minhash_dedup",
    ],
    "LOCAL_STANDARD": [
        "cleanup",
        "rule_corrections",
        "bert_correction",
        "minhash_dedup",
        "embedding_dedup",
    ],
    "LOCAL_LLM": [
        "cleanup",
        "rule_corrections",
        "llm_correction",
        "minhash_dedup",
        "embedding_dedup",
    ],
    "HYBRID_TIERED": [
        "cleanup",
        "rule_corrections",
        "hybrid_correction",
        "minhash_dedup",
        "embedding_dedup",
    ],
    "API_STANDARD": [
        "cleanup",
        "rule_corrections",
        "openrouter_correction",
        "minhash_dedup",
        "embedding_dedup",
    ],
    "API_FULL": [
        "cleanup",
        "rule_corrections",
        "openrouter_correction",
        "minhash_dedup",
        "openrouter_dedup",
    ],
}

_DEFAULT_MODE = "LOCAL_FAST"


class Pipeline:
    """Executes an ordered sequence of PostProcessStage instances.

    Stage instances are created once per Pipeline object and reused across
    process() calls. If a stage registry key is not yet registered (e.g.
    a stub not yet implemented), it is skipped with a warning.

    Args:
        mode:   Pipeline mode name (key in PIPELINE_MODES).
        config: Full application config dict.
    """

    def __init__(self, mode: str, config: dict) -> None:
        self._mode = mode
        self._config = config
        self._stages: list[PostProcessStage] = self._build_stages(mode)

    @property
    def mode(self) -> str:
        """Active pipeline mode name."""
        return self._mode

    @property
    def stage_ids(self) -> list[str]:
        """Ordered list of stage IDs that will be executed."""
        return [s.stage_id for s in self._stages]

    def process(self, results: list[OCRResult]) -> list[OCRResult]:
        """Run *results* through all pipeline stages in order.

        Args:
            results: Raw OCRResult list from the OCR engine.

        Returns:
            Post-processed OCRResult list.
        """
        logger.info(
            "Pipeline[%s]: processing %d results through %d stage(s).",
            self._mode, len(results), len(self._stages),
        )
        current = results
        for stage in self._stages:
            try:
                current = stage.process(current, self._config)
                logger.debug(
                    "Pipeline[%s]: after stage '%s': %d results.",
                    self._mode, stage.stage_id, len(current),
                )
            except Exception as exc:
                logger.error(
                    "Pipeline[%s]: stage '%s' raised %s: %s — skipping stage.",
                    self._mode, stage.stage_id, type(exc).__name__, exc,
                )
        return current

    @staticmethod
    def available_modes() -> list[str]:
        """Return the names of all defined pipeline modes."""
        return list(PIPELINE_MODES.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_stages(mode: str) -> list[PostProcessStage]:
        """Instantiate registered stages for the given *mode*.

        Unregistered stage keys are skipped with a warning — allows forward
        compatibility when not all stages are implemented yet.
        """
        stage_keys = PIPELINE_MODES.get(mode)
        if stage_keys is None:
            available = ", ".join(PIPELINE_MODES.keys())
            raise ValueError(
                f"Unknown pipeline mode '{mode}'. Available: {available}"
            )

        stages: list[PostProcessStage] = []
        for key in stage_keys:
            try:
                cls = PostProcessStage.get(key)
                stages.append(cls())
                logger.debug("Pipeline: registered stage '%s'.", key)
            except KeyError:
                logger.warning(
                    "Pipeline: stage '%s' not registered — skipping "
                    "(implement and import it to enable).",
                    key,
                )

        return stages
