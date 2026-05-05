"""Tests for utils/perf.py — Timer and StageTimings."""

from __future__ import annotations

import logging
import time

import pytest

from utils.perf import StageTimings, Timer


class TestTimer:
    def test_measures_elapsed(self) -> None:
        with Timer("test_stage") as t:
            time.sleep(0.01)
        assert t.elapsed_ms >= 10.0

    def test_results_out_set_inside_block(self) -> None:
        with Timer("s") as t:
            t.results_out = 42
        assert t.results_out == 42

    def test_records_to_timings(self) -> None:
        timings = StageTimings()
        with Timer("cleanup", timings, results_in=10) as t:
            t.results_out = 8
        assert len(timings.records) == 1
        rec = timings.records[0]
        assert rec["stage"] == "cleanup"
        assert rec["results_in"] == 10
        assert rec["results_out"] == 8
        assert rec["ms"] >= 0.0

    def test_no_timings_arg_does_not_raise(self) -> None:
        with Timer("solo") as t:
            t.results_out = 5
        assert t.elapsed_ms >= 0.0


class TestStageTimings:
    def test_total_ms(self) -> None:
        timings = StageTimings()
        timings.record("a", 100.0, 10, 10)
        timings.record("b", 200.0, 10, 8)
        assert timings.total_ms() == pytest.approx(300.0)

    def test_records_returns_copy(self) -> None:
        timings = StageTimings()
        timings.record("x", 50.0, 5, 5)
        records = timings.records
        records.clear()
        assert len(timings.records) == 1

    def test_perf_log_prefix(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="utils.perf"):
            timings = StageTimings()
            timings.record("minhash_dedup", 33.3, 20, 19)
        assert any("[PERF]" in r.message for r in caplog.records)
        assert any("stage=minhash_dedup" in r.message for r in caplog.records)


class TestPipelineIntegration:
    """Verify pipeline emits [PERF] lines per stage when perf_timing=True."""

    def test_pipeline_emits_perf_lines(self, caplog: pytest.LogCaptureFixture) -> None:
        from core.types import OCRResult
        from ocr.pipeline import Pipeline

        results = [
            OCRResult(text="测试", confidence=0.95, bbox=None, image_id="img1"),
        ]
        config = {"perf_timing": True}

        with caplog.at_level(logging.INFO, logger="utils.perf"):
            pipeline = Pipeline("LOCAL_FAST", config)
            pipeline.process(results)

        perf_messages = [r.message for r in caplog.records if "[PERF]" in r.message]
        assert len(perf_messages) >= 1, "Expected at least one [PERF] log line"
        stage_lines = [m for m in perf_messages if "stage=" in m]
        assert len(stage_lines) >= 1

    def test_pipeline_no_perf_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        from core.types import OCRResult
        from ocr.pipeline import Pipeline

        results = [OCRResult(text="测试", confidence=0.95, bbox=None, image_id="img1")]
        config = {"perf_timing": False}

        with caplog.at_level(logging.INFO, logger="utils.perf"):
            pipeline = Pipeline("LOCAL_FAST", config)
            pipeline.process(results)

        perf_messages = [r.message for r in caplog.records if "[PERF]" in r.message]
        assert len(perf_messages) == 0
