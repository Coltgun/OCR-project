"""
Tests for OCRWorker pipeline dispatch (FEAT-pipeline-config).

ocr.worker imports PySide6 at module level, which triggers a DLL conflict
when cv2 (conda-forge) is already loaded in the pytest process on Windows.
We therefore use two strategies:

1. Source-scan tests (TestWorkerPipelineSourceWiring) — read worker.py
   as text to verify the wiring is present without importing Qt.

2. Pipeline integration tests (TestPipelineDispatchLogic) — exercise the
   pipeline selection / fallback logic directly using ocr.pipeline (no Qt).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.types import OCRResult
from ocr.pipeline import Pipeline, PIPELINE_MODES, _DEFAULT_MODE

# Import stage modules to trigger self-registration before Pipeline tests.
import ocr.stages.cleanup          # noqa: F401
import ocr.stages.rule_corrections  # noqa: F401
import ocr.stages.minhash_dedup    # noqa: F401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WORKER_SRC = (
    Path(__file__).parent.parent.parent / "ocr" / "worker.py"
).read_text(encoding="utf-8")


def _make_result(text: str = "好", conf: float = 0.9) -> OCRResult:
    return OCRResult(text=text, confidence=conf)


# ---------------------------------------------------------------------------
# 1. Source-scan wiring tests — no Qt import needed
# ---------------------------------------------------------------------------

class TestWorkerPipelineSourceWiring:
    def test_pipeline_imported_in_worker(self) -> None:
        assert "from ocr.pipeline import Pipeline" in _WORKER_SRC

    def test_pipeline_modes_imported_in_worker(self) -> None:
        assert "PIPELINE_MODES" in _WORKER_SRC

    def test_default_mode_imported_in_worker(self) -> None:
        assert "_DEFAULT_MODE" in _WORKER_SRC

    def test_ocr_pipeline_mode_read_from_config(self) -> None:
        assert '"ocr_pipeline_mode"' in _WORKER_SRC

    def test_unknown_mode_fallback_warning_present(self) -> None:
        assert "falling back" in _WORKER_SRC

    def test_pipeline_failure_catch_present(self) -> None:
        assert "pipeline failed" in _WORKER_SRC

    def test_pipeline_called_with_mode_and_config(self) -> None:
        assert "Pipeline(mode, self._config)" in _WORKER_SRC

    def test_pipeline_process_called_on_ocr_results(self) -> None:
        assert "pipeline.process(ocr_results)" in _WORKER_SRC

    def test_results_emitted_after_pipeline(self) -> None:
        src = _WORKER_SRC
        emit_idx = src.index("signals.results_ready.emit(ocr_results)")
        pipeline_idx = src.index("pipeline.process(ocr_results)")
        assert pipeline_idx < emit_idx, "pipeline.process must precede results_ready.emit"


# ---------------------------------------------------------------------------
# 2. Pipeline logic tests — no Qt, exercises real Pipeline + stages
# ---------------------------------------------------------------------------

class TestPipelineDispatchLogic:
    def test_default_mode_is_valid(self) -> None:
        assert _DEFAULT_MODE in PIPELINE_MODES

    def test_pipeline_local_fast_processes_results(self) -> None:
        results = [_make_result("你 好"), _make_result("世界")]
        pipeline = Pipeline("LOCAL_FAST", {})
        out = pipeline.process(results)
        assert isinstance(out, list)

    def test_pipeline_preserves_non_empty_text(self) -> None:
        r = _make_result("世界")
        out = Pipeline("LOCAL_FAST", {}).process([r])
        assert len(out) >= 1

    def test_pipeline_returns_empty_for_empty_input(self) -> None:
        out = Pipeline("LOCAL_FAST", {}).process([])
        assert out == []

    def test_all_modes_construct_without_error(self) -> None:
        for mode in PIPELINE_MODES:
            p = Pipeline(mode, {})
            assert p.mode == mode

    def test_all_modes_process_empty_without_error(self) -> None:
        for mode in PIPELINE_MODES:
            out = Pipeline(mode, {}).process([])
            assert out == []

    def test_unknown_mode_key_falls_back_to_default(self) -> None:
        """Replicate the worker fallback logic directly."""
        mode = "NONEXISTENT_XYZ"
        if mode not in PIPELINE_MODES:
            mode = _DEFAULT_MODE
        assert mode == _DEFAULT_MODE
        p = Pipeline(mode, {})
        assert p.mode == _DEFAULT_MODE

    def test_config_mode_key_selects_correct_pipeline(self) -> None:
        config = {"ocr_pipeline_mode": "LOCAL_FAST"}
        mode = str(config.get("ocr_pipeline_mode", _DEFAULT_MODE))
        if mode not in PIPELINE_MODES:
            mode = _DEFAULT_MODE
        p = Pipeline(mode, config)
        assert p.mode == "LOCAL_FAST"

    def test_pipeline_cleanup_stage_strips_whitespace(self) -> None:
        r = _make_result("  你好  ")
        out = Pipeline("LOCAL_FAST", {}).process([r])
        assert out[0].text == "你好"

    def test_pipeline_dedup_merges_identical(self) -> None:
        """MinHash dedup collapses near-identical lines (threshold=0.5 forces match)."""
        r1 = _make_result("完全相同的文字", conf=0.9)
        r2 = _make_result("完全相同的文字", conf=0.7)
        cfg = {"dedup_threshold": 0.5}
        out = Pipeline("LOCAL_FAST", cfg).process([r1, r2])
        texts = [r.text for r in out]
        assert texts.count("完全相同的文字") == 1

    def test_pipeline_keeps_confidence_winner_on_dedup(self) -> None:
        r1 = _make_result("重复内容", conf=0.95)
        r2 = _make_result("重复内容", conf=0.50)
        cfg = {"dedup_threshold": 0.5}
        out = Pipeline("LOCAL_FAST", cfg).process([r1, r2])
        assert out[0].confidence == pytest.approx(0.95)
