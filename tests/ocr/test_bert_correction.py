"""
Tests for BertCorrectionStage.

All subprocess calls are mocked — no torch/pycorrector import required.
Tests cover: registry, process() text replacement, field preservation,
subprocess error fallback, length mismatch fallback, config forwarding,
and script builder structural checks.
"""

from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from core.types import BoundingBox, OCRResult
from ocr.stages.base import PostProcessStage
from ocr.stages.bert_correction import BertCorrectionStage


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


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_bert_correction(self) -> None:
        assert PostProcessStage.get("bert_correction") is BertCorrectionStage

    def test_stage_id(self) -> None:
        assert BertCorrectionStage().stage_id == "bert_correction"


# ---------------------------------------------------------------------------
# process() — subprocess mocked
# ---------------------------------------------------------------------------

class TestProcess:
    _cfg: dict = {}

    def _patch_subprocess(self, corrected: list[str]):
        return patch.object(
            BertCorrectionStage,
            "_run_subprocess",
            return_value=corrected,
        )

    def test_empty_returns_empty(self) -> None:
        stage = BertCorrectionStage()
        assert stage.process([], self._cfg) == []

    def test_single_result_text_corrected(self) -> None:
        stage = BertCorrectionStage()
        r = make_result("他走了。")
        with self._patch_subprocess(["他走了。"]):
            out = stage.process([r], self._cfg)
        assert len(out) == 1
        assert out[0].text == "他走了。"

    def test_correction_applied(self) -> None:
        stage = BertCorrectionStage()
        r = make_result("地走了。")  # 地 → 他 (OCR misread)
        with self._patch_subprocess(["他走了。"]):
            out = stage.process([r], self._cfg)
        assert out[0].text == "他走了。"

    def test_confidence_unchanged_after_correction(self) -> None:
        stage = BertCorrectionStage()
        r = make_result("错误文字", confidence=0.73)
        with self._patch_subprocess(["正确文字"]):
            out = stage.process([r], self._cfg)
        assert out[0].confidence == 0.73

    def test_bbox_unchanged_after_correction(self) -> None:
        stage = BertCorrectionStage()
        bbox = BoundingBox(x1=5, y1=10, x2=100, y2=30)
        r = OCRResult(text="错误", confidence=0.9, bbox=bbox, image_id="1/0001")
        with self._patch_subprocess(["正确"]):
            out = stage.process([r], self._cfg)
        assert out[0].bbox == bbox

    def test_image_id_unchanged_after_correction(self) -> None:
        stage = BertCorrectionStage()
        r = make_result("文字", image_id="3/0007")
        with self._patch_subprocess(["文字"]):
            out = stage.process([r], self._cfg)
        assert out[0].image_id == "3/0007"

    def test_multiple_results_all_corrected(self) -> None:
        stage = BertCorrectionStage()
        results = [make_result(f"原始{i}") for i in range(3)]
        corrected = [f"修正{i}" for i in range(3)]
        with self._patch_subprocess(corrected):
            out = stage.process(results, self._cfg)
        assert [r.text for r in out] == corrected

    def test_subprocess_failure_returns_unchanged(self) -> None:
        stage = BertCorrectionStage()
        results = [make_result("文字一"), make_result("文字二")]
        with patch.object(
            BertCorrectionStage,
            "_run_subprocess",
            side_effect=RuntimeError("subprocess failed"),
        ):
            out = stage.process(results, self._cfg)
        assert [r.text for r in out] == ["文字一", "文字二"]

    def test_length_mismatch_returns_unchanged(self) -> None:
        stage = BertCorrectionStage()
        results = [make_result("文字一"), make_result("文字二")]
        with self._patch_subprocess(["只有一条"]):   # wrong length
            out = stage.process(results, self._cfg)
        assert [r.text for r in out] == ["文字一", "文字二"]

    def test_config_keys_forwarded(self) -> None:
        stage = BertCorrectionStage()
        results = [make_result("文字")]
        cfg = {
            "bert_model": "shibing624/macbert4csc-base-chinese",
            "bert_max_length": 64,
            "bert_batch_size": 16,
        }
        with patch.object(
            BertCorrectionStage,
            "_run_subprocess",
            return_value=["文字"],
        ) as mock_sub:
            stage.process(results, cfg)
        mock_sub.assert_called_once_with(
            ["文字"],
            "shibing624/macbert4csc-base-chinese",
            64,
            16,
        )

    def test_reading_order_preserved(self) -> None:
        stage = BertCorrectionStage()
        texts = ["第一", "第二", "第三", "第四", "第五"]
        results = [make_result(t) for t in texts]
        corrected = [t + "修" for t in texts]
        with self._patch_subprocess(corrected):
            out = stage.process(results, self._cfg)
        assert [r.text for r in out] == corrected


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

    def test_valid_json_list_returned(self) -> None:
        corrected = ["修正文字一", "修正文字二"]
        with patch("subprocess.run", return_value=self._make_completed(json.dumps(corrected))):
            result = BertCorrectionStage._run_subprocess(
                ["文字一", "文字二"],
                "shibing624/macbert4csc-base-chinese",
                128,
                32,
            )
        assert result == corrected

    def test_subprocess_nonzero_raises(self) -> None:
        with patch("subprocess.run", return_value=self._make_completed("", returncode=1)):
            with pytest.raises(RuntimeError, match="subprocess failed"):
                BertCorrectionStage._run_subprocess(["文字"], "m", 128, 32)

    def test_empty_output_raises(self) -> None:
        with patch("subprocess.run", return_value=self._make_completed("")):
            with pytest.raises(RuntimeError, match="empty output"):
                BertCorrectionStage._run_subprocess(["文字"], "m", 128, 32)

    def test_invalid_json_raises(self) -> None:
        with patch("subprocess.run", return_value=self._make_completed("not-json")):
            with pytest.raises(RuntimeError, match="invalid JSON"):
                BertCorrectionStage._run_subprocess(["文字"], "m", 128, 32)

    def test_non_list_json_raises(self) -> None:
        with patch("subprocess.run", return_value=self._make_completed('{"key": "val"}')):
            with pytest.raises(RuntimeError, match="unexpected type"):
                BertCorrectionStage._run_subprocess(["文字"], "m", 128, 32)

    def test_results_coerced_to_str(self) -> None:
        with patch("subprocess.run", return_value=self._make_completed("[42, 43]")):
            result = BertCorrectionStage._run_subprocess(["a", "b"], "m", 128, 32)
        assert result == ["42", "43"]


# ---------------------------------------------------------------------------
# _build_subprocess_script — structural checks
# ---------------------------------------------------------------------------

class TestBuildSubprocessScript:
    def test_imports_pycorrector(self) -> None:
        from ocr.stages.bert_correction import _build_subprocess_script
        script = _build_subprocess_script('{"texts":[],"model":"m","max_length":128,"batch_size":32}')
        assert "pycorrector" in script
        assert "MacBertCorrector" in script

    def test_registers_nvidia_dirs(self) -> None:
        from ocr.stages.bert_correction import _build_subprocess_script
        script = _build_subprocess_script('{"texts":[],"model":"m","max_length":128,"batch_size":32}')
        assert "add_dll_directory" in script

    def test_prints_json(self) -> None:
        from ocr.stages.bert_correction import _build_subprocess_script
        script = _build_subprocess_script('{"texts":[],"model":"m","max_length":128,"batch_size":32}')
        assert "print(json.dumps" in script

    def test_calls_correct_batch(self) -> None:
        from ocr.stages.bert_correction import _build_subprocess_script
        script = _build_subprocess_script('{"texts":[],"model":"m","max_length":128,"batch_size":32}')
        assert "correct_batch" in script
