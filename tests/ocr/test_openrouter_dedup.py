"""
Tests for OpenRouterDeduplicationStage.

All OpenAI client calls are mocked — no live API required.
Tests cover: registry, _resolve_groups logic, process() end-to-end,
_request_assignments error paths, and JSON response parsing.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from core.types import BoundingBox, OCRResult
from ocr.stages.base import PostProcessStage
from ocr.stages.openrouter_dedup import OpenRouterDeduplicationStage


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


def make_response(assignments: list[int]) -> MagicMock:
    msg = MagicMock()
    msg.content = json.dumps(assignments)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def make_client(assignments: list[int]) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = make_response(assignments)
    return client


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_openrouter_dedup(self) -> None:
        assert PostProcessStage.get("openrouter_dedup") is OpenRouterDeduplicationStage

    def test_stage_id(self) -> None:
        assert OpenRouterDeduplicationStage().stage_id == "openrouter_dedup"


# ---------------------------------------------------------------------------
# _resolve_groups
# ---------------------------------------------------------------------------

class TestResolveGroups:
    def test_no_duplicates_all_kept(self) -> None:
        results = [make_result(f"文字{i}") for i in range(3)]
        out = OpenRouterDeduplicationStage._resolve_groups(results, [0, 1, 2])
        assert [r.text for r in out] == [r.text for r in results]

    def test_duplicate_pair_keeps_higher_confidence(self) -> None:
        low = make_result("重复", confidence=0.6)
        high = make_result("重复", confidence=0.95)
        out = OpenRouterDeduplicationStage._resolve_groups([low, high], [0, 0])
        assert len(out) == 1
        assert out[0].confidence == 0.95

    def test_equal_confidence_first_kept(self) -> None:
        first = make_result("同", confidence=0.9)
        second = make_result("同", confidence=0.9)
        out = OpenRouterDeduplicationStage._resolve_groups([first, second], [0, 0])
        assert len(out) == 1
        assert out[0] is first

    def test_reading_order_preserved(self) -> None:
        r0 = make_result("A", confidence=0.9)
        r1 = make_result("A_dup", confidence=0.8)  # dup of r0
        r2 = make_result("B", confidence=0.9)
        r3 = make_result("B_dup", confidence=0.95)  # dup of r2 but higher conf
        out = OpenRouterDeduplicationStage._resolve_groups(
            [r0, r1, r2, r3], [0, 0, 2, 2]
        )
        assert len(out) == 2
        assert out[0].text == "A"        # winner of group 0 by idx
        assert out[1].confidence == 0.95  # winner of group 2 by confidence


# ---------------------------------------------------------------------------
# _request_assignments — mocked at client level
# ---------------------------------------------------------------------------

class TestRequestAssignments:
    def test_valid_response(self) -> None:
        results = [make_result("a"), make_result("b"), make_result("c")]
        client = make_client([0, 0, 2])
        out = OpenRouterDeduplicationStage._request_assignments(
            client, results, "model", 0.0, 60.0, "url", "name"
        )
        assert out == [0, 0, 2]

    def test_api_error_raises_runtime_error(self) -> None:
        from openai import OpenAIError
        results = [make_result("a"), make_result("b")]
        client = MagicMock()
        client.chat.completions.create.side_effect = OpenAIError("timeout")
        with pytest.raises(RuntimeError, match="API error"):
            OpenRouterDeduplicationStage._request_assignments(
                client, results, "m", 0.0, 60.0, "u", "n"
            )

    def test_invalid_json_raises(self) -> None:
        results = [make_result("a")]
        client = MagicMock()
        msg = MagicMock()
        msg.content = "not json"
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        client.chat.completions.create.return_value = resp
        with pytest.raises(RuntimeError, match="Invalid JSON"):
            OpenRouterDeduplicationStage._request_assignments(
                client, results, "m", 0.0, 60.0, "u", "n"
            )

    def test_non_list_raises(self) -> None:
        results = [make_result("a")]
        client = MagicMock()
        msg = MagicMock()
        msg.content = '{"key": 0}'
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        client.chat.completions.create.return_value = resp
        with pytest.raises(RuntimeError, match="non-list"):
            OpenRouterDeduplicationStage._request_assignments(
                client, results, "m", 0.0, 60.0, "u", "n"
            )

    def test_wrong_length_raises(self) -> None:
        results = [make_result("a"), make_result("b"), make_result("c")]
        client = make_client([0, 1])  # only 2 for 3 inputs
        with pytest.raises(RuntimeError, match="3 inputs"):
            OpenRouterDeduplicationStage._request_assignments(
                client, results, "m", 0.0, 60.0, "u", "n"
            )

    def test_out_of_range_index_raises(self) -> None:
        results = [make_result("a"), make_result("b")]
        client = make_client([0, 5])  # 5 out of range
        with pytest.raises(RuntimeError, match="out of range"):
            OpenRouterDeduplicationStage._request_assignments(
                client, results, "m", 0.0, 60.0, "u", "n"
            )

    def test_markdown_fence_stripped(self) -> None:
        results = [make_result("a"), make_result("b")]
        client = MagicMock()
        msg = MagicMock()
        msg.content = "```json\n[0, 1]\n```"
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        client.chat.completions.create.return_value = resp
        out = OpenRouterDeduplicationStage._request_assignments(
            client, results, "m", 0.0, 60.0, "u", "n"
        )
        assert out == [0, 1]

    def test_extra_headers_sent(self) -> None:
        results = [make_result("a"), make_result("b")]
        client = make_client([0, 1])
        OpenRouterDeduplicationStage._request_assignments(
            client, results, "model", 0.0, 60.0, "https://site.com", "My App"
        )
        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["extra_headers"]["HTTP-Referer"] == "https://site.com"
        assert call_kwargs["extra_headers"]["X-Title"] == "My App"


# ---------------------------------------------------------------------------
# process() — end-to-end mocked
# ---------------------------------------------------------------------------

class TestProcess:
    def _patch_request(self, assignments: list[int]):
        return patch.object(
            OpenRouterDeduplicationStage,
            "_request_assignments",
            return_value=assignments,
        )

    def test_empty_returns_empty(self) -> None:
        assert OpenRouterDeduplicationStage().process([], {}) == []

    def test_single_returns_unchanged(self) -> None:
        r = make_result("文字")
        assert OpenRouterDeduplicationStage().process([r], {}) == [r]

    def test_no_duplicates_all_kept(self) -> None:
        stage = OpenRouterDeduplicationStage()
        results = [make_result(f"独特{i}") for i in range(3)]
        with self._patch_request([0, 1, 2]):
            out = stage.process(results, {})
        assert len(out) == 3

    def test_duplicates_removed(self) -> None:
        stage = OpenRouterDeduplicationStage()
        results = [make_result("重复"), make_result("重复"), make_result("独特")]
        with self._patch_request([0, 0, 2]):
            out = stage.process(results, {})
        assert len(out) == 2

    def test_api_failure_returns_unchanged(self) -> None:
        stage = OpenRouterDeduplicationStage()
        results = [make_result("文字一"), make_result("文字二")]
        with patch.object(
            OpenRouterDeduplicationStage,
            "_request_assignments",
            side_effect=RuntimeError("API error"),
        ):
            out = stage.process(results, {})
        assert [r.text for r in out] == ["文字一", "文字二"]

    def test_config_api_key_used(self) -> None:
        stage = OpenRouterDeduplicationStage()
        results = [make_result("a"), make_result("b")]
        with self._patch_request([0, 1]):
            with patch("ocr.stages.openrouter_dedup.OpenAI") as mock_cls:
                mock_cls.return_value = MagicMock()
                stage.process(results, {"openrouter_api_key": "key-123"})
        mock_cls.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="key-123",
        )

    def test_env_var_api_key_used(self) -> None:
        stage = OpenRouterDeduplicationStage()
        results = [make_result("a"), make_result("b")]
        with self._patch_request([0, 1]):
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-key"}):
                with patch("ocr.stages.openrouter_dedup.OpenAI") as mock_cls:
                    mock_cls.return_value = MagicMock()
                    stage.process(results, {})
        mock_cls.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="env-key",
        )

    def test_custom_model_forwarded(self) -> None:
        stage = OpenRouterDeduplicationStage()
        results = [make_result("a"), make_result("b")]
        cfg = {"openrouter_dedup_model": "anthropic/claude-3-haiku"}
        with patch.object(
            OpenRouterDeduplicationStage,
            "_request_assignments",
            return_value=[0, 1],
        ) as mock_req:
            stage.process(results, cfg)
        call_args = mock_req.call_args
        assert call_args.args[2] == "anthropic/claude-3-haiku"
