"""
utils/perf — lightweight performance timing for the OCR pipeline.

Usage:
    from utils.perf import Timer, StageTimings

    timings = StageTimings()
    with Timer("cleanup", timings) as t:
        result = stage.process(results, config)
    # Each Timer logs [PERF] stage=cleanup ms=42 results_in=100 results_out=98
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_PERF_PREFIX = "[PERF]"


class StageTimings:
    """Accumulates per-stage timing records for one pipeline run."""

    def __init__(self) -> None:
        self._records: list[dict] = []

    def record(self, stage_id: str, elapsed_ms: float, results_in: int, results_out: int) -> None:
        """Store a timing record and emit an INFO log line."""
        self._records.append(
            {
                "stage": stage_id,
                "ms": round(elapsed_ms, 1),
                "results_in": results_in,
                "results_out": results_out,
            }
        )
        logger.info(
            "%s stage=%s ms=%.1f results_in=%d results_out=%d",
            _PERF_PREFIX,
            stage_id,
            elapsed_ms,
            results_in,
            results_out,
        )

    @property
    def records(self) -> list[dict]:
        """Return a copy of all recorded timing dicts."""
        return list(self._records)

    def total_ms(self) -> float:
        """Sum of all recorded stage durations."""
        return sum(r["ms"] for r in self._records)


class Timer:
    """Context manager that measures wall-clock time for a named stage.

    Args:
        stage_id:   Human-readable stage identifier (used in log output).
        timings:    Optional StageTimings accumulator; if None only logs.
        results_in: Number of results entering the stage (set before entering
                    context, or override via attribute before __exit__).
    """

    def __init__(
        self,
        stage_id: str,
        timings: Optional[StageTimings] = None,
        results_in: int = 0,
    ) -> None:
        self.stage_id = stage_id
        self._timings = timings
        self.results_in = results_in
        self.results_out = 0
        self._start: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0
        if self._timings is not None:
            self._timings.record(
                self.stage_id, self.elapsed_ms, self.results_in, self.results_out
            )
