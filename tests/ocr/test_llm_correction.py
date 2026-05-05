"""
Tests for LlmCorrectionStage.

All OpenAI client calls are mocked — no live Ollama instance required.
Tests cover: registry, process() text replacement, field preservation,
API error fallback, parse error fallback, length mismatch fallback,
batching, config forwarding, _parse_response edge cases.
"""

from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import MagicMock, patch, call

import pytest

from core.types import BoundingBox, OCRResult
from ocr.stages.base import PostProcessStage
from ocr.stages.llm_correction import LlmCorrectionStage
from ocr.stages.llm_correction_base import _SYSTEM_PROMPT


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


def make_response(texts: list[str]) -> MagicMock:
    """Build a mock OpenAI ChatCompletion response returning *texts* as JSON."""
    msg = MagicMock()
    msg.content = json.dumps(texts, ensure_ascii=False)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_prompt_under_150_chars(self) -> None:
        """Regression: compressed prompt must stay compact."""
        assert len(_SYSTEM_PROMPT) < 150, (
            f"_SYSTEM_PROMPT is {len(_SYSTEM_PROMPT)} chars — should be < 150"
        )

    def test_prompt_contains_key_rules(self) -> None:
        assert "OCR" in _SYSTEM_PROMPT
        assert "JSON" in _SYSTEM_PROMPT


class TestRegistry:
    def test_registered_as_llm_correction(self) -> None:
        assert PostProcessStage.get("llm_correction") is LlmCorrectionStage

    def test_stage_id(self) -> None:
        assert LlmCorrectionStage().stage_id == "llm_correction"


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_valid_json_list(self) -> None:
        originals = ["a", "b"]
        out = LlmCorrectionStage._parse_response('["x","y"]', originals)
        assert out == ["x", "y"]

    def test_invalid_json_returns_originals(self) -> None:
        originals = ["a", "b"]
        out = LlmCorrectionStage._parse_response("not json", originals)
        assert out == originals

    def test_non_list_returns_originals(self) -> None:
        originals = ["a"]
        out = LlmCorrectionStage._parse_response('{"key":"val"}', originals)
        assert out == originals

    def test_length_mismatch_uses_partial_corrections(self) -> None:
        originals = ["a", "b", "c"]
        # Short response: first two corrected, third preserved from originals
        out = LlmCorrectionStage._parse_response('["x","y"]', originals)
        assert out == ["x", "y", "c"]

    def test_length_mismatch_truncates_long_response(self) -> None:
        originals = ["a", "b"]
        out = LlmCorrectionStage._parse_response('["x","y","z"]', originals)
        assert out == ["x", "y"]

    def test_array_extracted_from_preamble(self) -> None:
        originals = ["a", "b"]
        raw = 'Here are the corrections: ["x", "y"]'
        out = LlmCorrectionStage._parse_response(raw, originals)
        assert out == ["x", "y"]

    def test_markdown_code_fence_stripped(self) -> None:
        originals = ["a"]
        raw = "```json\n[\"x\"]\n```"
        out = LlmCorrectionStage._parse_response(raw, originals)
        assert out == ["x"]

    def test_plain_code_fence_stripped(self) -> None:
        originals = ["a"]
        raw = "```\n[\"x\"]\n```"
        out = LlmCorrectionStage._parse_response(raw, originals)
        assert out == ["x"]

    def test_elements_coerced_to_str(self) -> None:
        originals = ["a"]
        out = LlmCorrectionStage._parse_response("[42]", originals)
        assert out == ["42"]

    def test_empty_originals_empty_response(self) -> None:
        out = LlmCorrectionStage._parse_response("[]", [])
        assert out == []


# ---------------------------------------------------------------------------
# process() — client mocked
# ---------------------------------------------------------------------------

class TestProcess:
    _cfg: dict = {}

    def _patch_client(self, responses: list[list[str]]):
        """Patch get_openai_client so completions.create returns each response in sequence."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            make_response(r) for r in responses
        ]
        return patch("ocr.stages.llm_correction.get_openai_client", return_value=mock_client)

    def test_empty_returns_empty(self) -> None:
        stage = LlmCorrectionStage()
        assert stage.process([], self._cfg) == []

    def test_single_result_corrected(self) -> None:
        stage = LlmCorrectionStage()
        r = make_result("地走了。")
        with self._patch_client([["他走了。"]]):
            out = stage.process([r], self._cfg)
        assert out[0].text == "他走了。"

    def test_confidence_unchanged(self) -> None:
        stage = LlmCorrectionStage()
        r = make_result("错误", confidence=0.65)
        with self._patch_client([["正确"]]):
            out = stage.process([r], self._cfg)
        assert out[0].confidence == 0.65

    def test_bbox_unchanged(self) -> None:
        stage = LlmCorrectionStage()
        bbox = BoundingBox(x1=1, y1=2, x2=50, y2=20)
        r = OCRResult(text="错误", confidence=0.9, bbox=bbox, image_id="1/0001")
        with self._patch_client([["正确"]]):
            out = stage.process([r], self._cfg)
        assert out[0].bbox == bbox

    def test_image_id_unchanged(self) -> None:
        stage = LlmCorrectionStage()
        r = make_result("文字", image_id="5/0012")
        with self._patch_client([["文字"]]):
            out = stage.process([r], self._cfg)
        assert out[0].image_id == "5/0012"

    def test_multiple_results_corrected(self) -> None:
        stage = LlmCorrectionStage()
        results = [make_result(f"错误{i}") for i in range(3)]
        corrected = [f"正确{i}" for i in range(3)]
        with self._patch_client([corrected]):
            out = stage.process(results, self._cfg)
        assert [r.text for r in out] == corrected

    def test_reading_order_preserved(self) -> None:
        stage = LlmCorrectionStage()
        texts = ["第一", "第二", "第三"]
        results = [make_result(t) for t in texts]
        corrected = ["第一修", "第二修", "第三修"]
        with self._patch_client([corrected]):
            out = stage.process(results, self._cfg)
        assert [r.text for r in out] == corrected

    def test_api_error_keeps_originals(self) -> None:
        from openai import OpenAIError
        stage = LlmCorrectionStage()
        results = [make_result("文字一"), make_result("文字二")]
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = OpenAIError("timeout")
        with patch("ocr.stages.llm_correction.get_openai_client", return_value=mock_client):
            out = stage.process(results, self._cfg)
        assert [r.text for r in out] == ["文字一", "文字二"]

    def test_parse_error_keeps_originals(self) -> None:
        stage = LlmCorrectionStage()
        results = [make_result("文字")]
        msg = MagicMock()
        msg.content = "not json at all"
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = resp
        with patch("ocr.stages.llm_correction.get_openai_client", return_value=mock_client):
            out = stage.process(results, self._cfg)
        assert out[0].text == "文字"

    def test_batching_uses_multiple_api_calls(self) -> None:
        """With batch_size=2 and 5 results, expect 3 API calls."""
        stage = LlmCorrectionStage()
        results = [make_result(f"文字{i}") for i in range(5)]
        cfg = {"llm_batch_size": 2}
        # batches: [0,1], [2,3], [4]
        responses = [
            ["修正0", "修正1"],
            ["修正2", "修正3"],
            ["修正4"],
        ]
        with self._patch_client(responses) as mock_cls:
            out = stage.process(results, cfg)
        client_instance = mock_cls.return_value
        assert client_instance.chat.completions.create.call_count == 3
        assert [r.text for r in out] == [f"修正{i}" for i in range(5)]

    def test_config_keys_forwarded(self) -> None:
        stage = LlmCorrectionStage()
        results = [make_result("文字")]
        cfg = {
            "llm_model": "qwen2.5:7b-instruct-q4_K_M",
            "llm_base_url": "http://localhost:11434/v1",
            "llm_api_key": "ollama",
            "llm_temperature": 0.1,
            "llm_timeout": 30.0,
            "llm_batch_size": 5,
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_response(["文字"])
        with patch("ocr.stages.llm_correction.get_openai_client", return_value=mock_client) as mock_fn:
            stage.process(results, cfg)
        mock_fn.assert_called_once_with(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            timeout=30.0,
        )
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "qwen2.5:7b-instruct-q4_K_M"
        assert call_kwargs.kwargs["temperature"] == 0.1
        assert call_kwargs.kwargs["timeout"] == 30.0

    def test_partial_batch_failure_preserves_successful_batches(self) -> None:
        """If batch 2 fails, batches 1 and 3 should still be corrected."""
        from openai import OpenAIError
        stage = LlmCorrectionStage()
        results = [make_result(f"文字{i}") for i in range(3)]
        cfg = {"llm_batch_size": 1}
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            make_response(["修正0"]),
            OpenAIError("error on batch 2"),
            make_response(["修正2"]),
        ]
        with patch("ocr.stages.llm_correction.get_openai_client", return_value=mock_client):
            out = stage.process(results, cfg)
        assert out[0].text == "修正0"
        assert out[1].text == "文字1"   # fallback
        assert out[2].text == "修正2"


# ---------------------------------------------------------------------------
# Skip gate — _should_skip and _partition_skip
# ---------------------------------------------------------------------------

class TestSkipGate:
    def _r(self, text: str, confidence: float = 0.9) -> OCRResult:
        return OCRResult(
            text=text,
            confidence=confidence,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            image_id="1/0001",
        )

    def test_should_skip_short_text(self) -> None:
        assert LlmCorrectionStage._should_skip(self._r(""), 0.97) is True
        assert LlmCorrectionStage._should_skip(self._r(" "), 0.97) is True
        assert LlmCorrectionStage._should_skip(self._r("一"), 0.5) is True

    def test_should_skip_high_confidence(self) -> None:
        assert LlmCorrectionStage._should_skip(self._r("正常文字", 0.97), 0.97) is True
        assert LlmCorrectionStage._should_skip(self._r("正常文字", 0.99), 0.97) is True

    def test_should_not_skip_normal(self) -> None:
        assert LlmCorrectionStage._should_skip(self._r("错误文字", 0.85), 0.97) is False

    def test_should_not_skip_at_threshold_boundary(self) -> None:
        assert LlmCorrectionStage._should_skip(self._r("文字", 0.96), 0.97) is False

    def test_partition_separates_skip_and_send(self) -> None:
        stage = LlmCorrectionStage()
        results = [
            self._r("跳过", 0.99),       # skip: high confidence
            self._r("发送", 0.8),        # send
            self._r("一", 0.5),          # skip: short text
            self._r("也发送", 0.85),     # send
        ]
        cfg = {"llm_skip_high_confidence_threshold": 0.97}
        send_idx, send_res, skip_idx = stage._partition_skip(results, cfg)
        assert send_idx == [1, 3]
        assert skip_idx == [0, 2]
        assert [r.text for r in send_res] == ["发送", "也发送"]

    def test_high_confidence_results_preserved_in_output(self) -> None:
        stage = LlmCorrectionStage()
        results = [
            self._r("高置信", 0.99),
            self._r("低置信", 0.8),
        ]
        cfg = {"llm_skip_high_confidence_threshold": 0.97}
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_response(["已修正"])
        with patch("ocr.stages.llm_correction.get_openai_client", return_value=mock_client):
            out = stage.process(results, cfg)
        assert out[0].text == "高置信"
        assert out[1].text == "已修正"
        mock_client.chat.completions.create.call_count == 1
        sent = json.loads(
            mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        )
        assert sent == ["低置信"]

    def test_all_skipped_makes_no_api_call(self) -> None:
        stage = LlmCorrectionStage()
        results = [self._r("高", 0.99), self._r("一", 0.5)]
        cfg = {"llm_skip_high_confidence_threshold": 0.97}
        mock_client = MagicMock()
        with patch("ocr.stages.llm_correction.get_openai_client", return_value=mock_client):
            out = stage.process(results, cfg)
        mock_client.chat.completions.create.assert_not_called()
        assert [r.text for r in out] == ["高", "一"]

    def test_custom_threshold_respected(self) -> None:
        stage = LlmCorrectionStage()
        r = self._r("文字", 0.85)
        assert stage._should_skip(r, 0.80) is True
        assert stage._should_skip(r, 0.90) is False

    def test_reading_order_preserved_with_mixed_skip_send(self) -> None:
        stage = LlmCorrectionStage()
        results = [
            self._r("一", 0.5),         # skip idx 0
            self._r("错误A", 0.7),      # send idx 1
            self._r("高置信", 0.99),    # skip idx 2
            self._r("错误B", 0.6),      # send idx 3
        ]
        cfg = {"llm_skip_high_confidence_threshold": 0.97}
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_response(["修正A", "修正B"])
        with patch("ocr.stages.llm_correction.get_openai_client", return_value=mock_client):
            out = stage.process(results, cfg)
        assert [r.text for r in out] == ["一", "修正A", "高置信", "修正B"]
