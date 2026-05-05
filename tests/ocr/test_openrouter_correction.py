"""
Tests for OpenRouterCorrectionStage.

All OpenAI client calls are mocked.  Tests verify: registry, provider-specific
config (model/base_url/api_key/headers), field preservation, fallbacks, and
that the shared base class logic (batching, _parse_response) is exercised.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from core.types import BoundingBox, OCRResult
from ocr.stages.base import PostProcessStage
from ocr.stages.llm_correction_base import LlmCorrectionBase
from ocr.stages.openrouter_correction import OpenRouterCorrectionStage


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
    msg = MagicMock()
    msg.content = json.dumps(texts, ensure_ascii=False)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Registry & inheritance
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_openrouter_correction(self) -> None:
        assert PostProcessStage.get("openrouter_correction") is OpenRouterCorrectionStage

    def test_stage_id(self) -> None:
        assert OpenRouterCorrectionStage().stage_id == "openrouter_correction"

    def test_is_subclass_of_llm_correction_base(self) -> None:
        assert issubclass(OpenRouterCorrectionStage, LlmCorrectionBase)


# ---------------------------------------------------------------------------
# _make_client — API key resolution
# ---------------------------------------------------------------------------

class TestMakeClient:
    def test_uses_config_api_key(self) -> None:
        stage = OpenRouterCorrectionStage()
        with patch("ocr.stages.openrouter_correction.get_openai_client") as mock_fn:
            mock_fn.return_value = MagicMock()
            stage._make_client({"openrouter_api_key": "test-key-123"})
        mock_fn.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key-123",
            timeout=60.0,
        )

    def test_uses_env_var_when_config_key_absent(self) -> None:
        stage = OpenRouterCorrectionStage()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-key-456"}):
            with patch("ocr.stages.openrouter_correction.get_openai_client") as mock_fn:
                mock_fn.return_value = MagicMock()
                stage._make_client({})
            mock_fn.assert_called_once_with(
                base_url="https://openrouter.ai/api/v1",
                api_key="env-key-456",
                timeout=60.0,
            )

    def test_custom_base_url(self) -> None:
        stage = OpenRouterCorrectionStage()
        with patch("ocr.stages.openrouter_correction.get_openai_client") as mock_fn:
            mock_fn.return_value = MagicMock()
            stage._make_client({
                "openrouter_api_key": "k",
                "openrouter_base_url": "https://custom.api/v1",
            })
        mock_fn.assert_called_once_with(
            base_url="https://custom.api/v1",
            api_key="k",
            timeout=60.0,
        )


# ---------------------------------------------------------------------------
# _read_config
# ---------------------------------------------------------------------------

class TestReadConfig:
    def test_defaults(self) -> None:
        stage = OpenRouterCorrectionStage()
        model, temp, timeout, batch = stage._read_config({})
        assert model == "qwen/qwen-2.5-7b-instruct"
        assert temp == 0.0
        assert timeout == 60.0
        assert batch == 10

    def test_custom_values(self) -> None:
        stage = OpenRouterCorrectionStage()
        cfg = {
            "openrouter_model": "anthropic/claude-3-haiku",
            "openrouter_temperature": 0.2,
            "openrouter_timeout": 30.0,
            "openrouter_batch_size": 5,
        }
        model, temp, timeout, batch = stage._read_config(cfg)
        assert model == "anthropic/claude-3-haiku"
        assert temp == 0.2
        assert timeout == 30.0
        assert batch == 5


# ---------------------------------------------------------------------------
# _extra_create_kwargs — OpenRouter headers
# ---------------------------------------------------------------------------

class TestExtraCreateKwargs:
    def test_default_headers(self) -> None:
        stage = OpenRouterCorrectionStage()
        extra = stage._extra_create_kwargs({})
        assert "extra_headers" in extra
        assert "HTTP-Referer" in extra["extra_headers"]
        assert "X-Title" in extra["extra_headers"]

    def test_custom_site_url_and_name(self) -> None:
        stage = OpenRouterCorrectionStage()
        extra = stage._extra_create_kwargs({
            "openrouter_site_url": "https://myapp.com",
            "openrouter_site_name": "My OCR App",
        })
        assert extra["extra_headers"]["HTTP-Referer"] == "https://myapp.com"
        assert extra["extra_headers"]["X-Title"] == "My OCR App"

    def test_headers_passed_to_api_call(self) -> None:
        stage = OpenRouterCorrectionStage()
        results = [make_result("文字")]
        cfg = {"openrouter_api_key": "k", "openrouter_site_url": "https://test.com"}
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_response(["文字"])
        with patch("ocr.stages.openrouter_correction.get_openai_client", return_value=mock_client):
            stage.process(results, cfg)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "extra_headers" in call_kwargs
        assert call_kwargs["extra_headers"]["HTTP-Referer"] == "https://test.com"


# ---------------------------------------------------------------------------
# process() — end-to-end via mocked client
# ---------------------------------------------------------------------------

class TestProcess:
    def _patch_client(self, responses: list[list[str]]):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            make_response(r) for r in responses
        ]
        return patch(
            "ocr.stages.openrouter_correction.get_openai_client", return_value=mock_client
        )

    def test_empty_returns_empty(self) -> None:
        assert OpenRouterCorrectionStage().process([], {}) == []

    def test_correction_applied(self) -> None:
        stage = OpenRouterCorrectionStage()
        r = make_result("地走了。")
        with self._patch_client([["他走了。"]]):
            out = stage.process([r], {"openrouter_api_key": "k"})
        assert out[0].text == "他走了。"

    def test_confidence_unchanged(self) -> None:
        stage = OpenRouterCorrectionStage()
        r = make_result("错误", confidence=0.55)
        with self._patch_client([["正确"]]):
            out = stage.process([r], {"openrouter_api_key": "k"})
        assert out[0].confidence == 0.55

    def test_bbox_unchanged(self) -> None:
        stage = OpenRouterCorrectionStage()
        bbox = BoundingBox(x1=3, y1=7, x2=80, y2=25)
        r = OCRResult(text="错误", confidence=0.9, bbox=bbox, image_id="1/0001")
        with self._patch_client([["正确"]]):
            out = stage.process([r], {"openrouter_api_key": "k"})
        assert out[0].bbox == bbox

    def test_image_id_unchanged(self) -> None:
        stage = OpenRouterCorrectionStage()
        r = make_result("文字", image_id="7/0003")
        with self._patch_client([["文字"]]):
            out = stage.process([r], {"openrouter_api_key": "k"})
        assert out[0].image_id == "7/0003"

    def test_api_error_keeps_originals(self) -> None:
        from openai import OpenAIError
        stage = OpenRouterCorrectionStage()
        results = [make_result("文字一"), make_result("文字二")]
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = OpenAIError("rate limit")
        with patch("ocr.stages.openrouter_correction.get_openai_client", return_value=mock_client):
            out = stage.process(results, {"openrouter_api_key": "k"})
        assert [r.text for r in out] == ["文字一", "文字二"]

    def test_batching(self) -> None:
        stage = OpenRouterCorrectionStage()
        results = [make_result(f"文字{i}") for i in range(4)]
        cfg = {"openrouter_api_key": "k", "openrouter_batch_size": 2}
        with self._patch_client([["修正0", "修正1"], ["修正2", "修正3"]]) as mock_cls:
            out = stage.process(results, cfg)
        assert mock_cls.return_value.chat.completions.create.call_count == 2
        assert [r.text for r in out] == ["修正0", "修正1", "修正2", "修正3"]

    def test_model_forwarded_in_api_call(self) -> None:
        stage = OpenRouterCorrectionStage()
        results = [make_result("文字")]
        cfg = {
            "openrouter_api_key": "k",
            "openrouter_model": "anthropic/claude-3-haiku",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_response(["文字"])
        with patch("ocr.stages.openrouter_correction.get_openai_client", return_value=mock_client):
            stage.process(results, cfg)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "anthropic/claude-3-haiku"


# ---------------------------------------------------------------------------
# Concurrent path (openrouter_concurrency > 1)
# ---------------------------------------------------------------------------

class TestConcurrentPath:
    def _make_async_mock(self, responses: list[list[str]]) -> MagicMock:
        """Build an AsyncMock client whose create() returns each response."""
        from unittest.mock import AsyncMock
        async_client = MagicMock()
        async_client.chat.completions.create = AsyncMock(
            side_effect=[make_response(r) for r in responses]
        )
        return async_client

    def test_concurrent_path_returns_corrected_texts(self) -> None:
        stage = OpenRouterCorrectionStage()
        results = [make_result(f"文字{i}") for i in range(4)]
        corrected = [[f"修正{i}", f"修正{i+1}"] for i in range(0, 4, 2)]
        flat = [t for batch in corrected for t in batch]
        cfg = {
            "openrouter_api_key": "k",
            "openrouter_batch_size": 2,
            "openrouter_concurrency": 2,
        }
        async_mock = self._make_async_mock(corrected)
        with patch("ocr.stages.openrouter_correction.get_async_openai_client", return_value=async_mock):
            out = stage.process(results, cfg)
        assert [r.text for r in out] == flat

    def test_concurrent_calls_respect_semaphore(self) -> None:
        """All batches are dispatched; call count equals number of batches."""
        from unittest.mock import AsyncMock
        stage = OpenRouterCorrectionStage()
        results = [make_result(f"文字{i}") for i in range(6)]
        responses = [[f"修正{i}", f"修正{i+1}"] for i in range(0, 6, 2)]
        cfg = {
            "openrouter_api_key": "k",
            "openrouter_batch_size": 2,
            "openrouter_concurrency": 3,
        }
        async_mock = MagicMock()
        async_mock.chat.completions.create = AsyncMock(
            side_effect=[make_response(r) for r in responses]
        )
        with patch("ocr.stages.openrouter_correction.get_async_openai_client", return_value=async_mock):
            stage.process(results, cfg)
        assert async_mock.chat.completions.create.call_count == 3

    def test_concurrent_async_error_falls_back_per_batch(self) -> None:
        """A failed async batch returns originals for that batch only."""
        from openai import OpenAIError
        from unittest.mock import AsyncMock
        stage = OpenRouterCorrectionStage()
        results = [make_result("文字A"), make_result("文字B")]
        cfg = {
            "openrouter_api_key": "k",
            "openrouter_batch_size": 1,
            "openrouter_concurrency": 2,
        }
        async_mock = MagicMock()
        async_mock.chat.completions.create = AsyncMock(
            side_effect=[make_response(["修正A"]), OpenAIError("timeout")]
        )
        with patch("ocr.stages.openrouter_correction.get_async_openai_client", return_value=async_mock):
            out = stage.process(results, cfg)
        assert out[0].text == "修正A"
        assert out[1].text == "文字B"

    def test_sequential_path_used_when_concurrency_is_1(self) -> None:
        """With concurrency=1 the sync client path is taken, not async."""
        stage = OpenRouterCorrectionStage()
        results = [make_result("文字")]
        cfg = {"openrouter_api_key": "k", "openrouter_concurrency": 1}
        mock_sync = MagicMock()
        mock_sync.chat.completions.create.return_value = make_response(["修正"])
        with patch("ocr.stages.openrouter_correction.get_openai_client", return_value=mock_sync) as p_sync, \
             patch("ocr.stages.openrouter_correction.get_async_openai_client") as p_async:
            out = stage.process(results, cfg)
        p_async.assert_not_called()
        assert out[0].text == "修正"

    def test_max_concurrency_reads_from_config(self) -> None:
        stage = OpenRouterCorrectionStage()
        assert stage._max_concurrency({"openrouter_concurrency": 4}) == 4
        assert stage._max_concurrency({}) == 1

    def test_make_async_client_returns_async_openai(self) -> None:
        from openai import AsyncOpenAI
        stage = OpenRouterCorrectionStage()
        cfg = {"openrouter_api_key": "k", "openrouter_base_url": "https://openrouter.ai/api/v1"}
        client = stage._make_async_client(cfg)
        assert isinstance(client, AsyncOpenAI)
