"""
Tests for llm/cache.py — LlmResultCache.

Tests cover: get/put, cache-miss, eviction, disk persistence,
from_config factory, and integration with _correct_batch in llm_correction_base.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llm.cache import LlmResultCache


# ---------------------------------------------------------------------------
# Basic get / put
# ---------------------------------------------------------------------------

class TestGetPut:
    def test_miss_returns_none(self) -> None:
        c = LlmResultCache()
        assert c.get("stage", "model", "prompt", "text") is None

    def test_put_then_get_returns_value(self) -> None:
        c = LlmResultCache()
        c.put("stage", "model", "prompt", "text", "corrected")
        assert c.get("stage", "model", "prompt", "text") == "corrected"

    def test_different_text_is_miss(self) -> None:
        c = LlmResultCache()
        c.put("stage", "model", "prompt", "textA", "correctedA")
        assert c.get("stage", "model", "prompt", "textB") is None

    def test_different_model_is_miss(self) -> None:
        c = LlmResultCache()
        c.put("stage", "model-1", "prompt", "text", "v1")
        assert c.get("stage", "model-2", "prompt", "text") is None

    def test_different_stage_is_miss(self) -> None:
        c = LlmResultCache()
        c.put("stageA", "model", "prompt", "text", "val")
        assert c.get("stageB", "model", "prompt", "text") is None

    def test_different_prompt_is_miss(self) -> None:
        c = LlmResultCache()
        c.put("stage", "model", "prompt-v1", "text", "val")
        assert c.get("stage", "model", "prompt-v2", "text") is None

    def test_len(self) -> None:
        c = LlmResultCache()
        assert len(c) == 0
        c.put("s", "m", "p", "t1", "r1")
        c.put("s", "m", "p", "t2", "r2")
        assert len(c) == 2

    def test_duplicate_put_does_not_grow(self) -> None:
        c = LlmResultCache()
        c.put("s", "m", "p", "t", "r1")
        c.put("s", "m", "p", "t", "r2")
        assert len(c) == 1
        assert c.get("s", "m", "p", "t") == "r2"


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------

class TestEviction:
    def test_evicts_oldest_when_full(self) -> None:
        c = LlmResultCache(max_entries=5)
        for i in range(6):
            c.put("s", "m", "p", f"text{i}", f"res{i}")
        assert len(c) == 5

    def test_evicts_10_percent(self) -> None:
        c = LlmResultCache(max_entries=10)
        for i in range(11):
            c.put("s", "m", "p", f"t{i}", f"r{i}")
        assert len(c) == 10

    def test_earliest_entry_evicted(self) -> None:
        c = LlmResultCache(max_entries=3)
        c.put("s", "m", "p", "first", "r0")
        c.put("s", "m", "p", "second", "r1")
        c.put("s", "m", "p", "third", "r2")
        c.put("s", "m", "p", "fourth", "r3")  # triggers eviction: removes oldest 1
        assert c.get("s", "m", "p", "first") is None
        assert c.get("s", "m", "p", "fourth") == "r3"


# ---------------------------------------------------------------------------
# Disk persistence
# ---------------------------------------------------------------------------

class TestDiskPersistence:
    def test_flush_creates_file(self, tmp_path: Path) -> None:
        p = tmp_path / "cache.json"
        c = LlmResultCache(disk_path=p)
        c.put("s", "m", "prompt", "text", "corrected")
        c.flush()
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "entries" in data
        assert len(data["entries"]) == 1

    def test_load_from_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "cache.json"
        c1 = LlmResultCache(disk_path=p)
        c1.put("s", "m", "prompt", "text", "corrected")
        c1.flush()

        c2 = LlmResultCache(disk_path=p)
        assert c2.get("s", "m", "prompt", "text") == "corrected"

    def test_flush_noop_when_no_disk_path(self) -> None:
        c = LlmResultCache(disk_path=None)
        c.put("s", "m", "p", "t", "r")
        c.flush()

    def test_corrupted_file_starts_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "cache.json"
        p.write_text("not json", encoding="utf-8")
        c = LlmResultCache(disk_path=p)
        assert len(c) == 0

    def test_missing_file_starts_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.json"
        c = LlmResultCache(disk_path=p)
        assert len(c) == 0


# ---------------------------------------------------------------------------
# from_config factory
# ---------------------------------------------------------------------------

class TestFromConfig:
    def test_off_returns_none(self) -> None:
        assert LlmResultCache.from_config({"llm_result_cache": "off"}) is None

    def test_default_is_off(self) -> None:
        assert LlmResultCache.from_config({}) is None

    def test_memory_returns_instance(self) -> None:
        c = LlmResultCache.from_config({"llm_result_cache": "memory"})
        assert isinstance(c, LlmResultCache)
        assert c._disk_path is None

    def test_disk_resolves_working_root(self, tmp_path: Path) -> None:
        cfg = {
            "llm_result_cache": "disk",
            "llm_result_cache_path": "{working_root_dir}/.llm_cache.json",
        }
        c = LlmResultCache.from_config(cfg, working_root=tmp_path)
        assert c is not None
        assert c._disk_path == tmp_path / ".llm_cache.json"

    def test_custom_max_entries(self) -> None:
        c = LlmResultCache.from_config({
            "llm_result_cache": "memory",
            "llm_result_cache_max_entries": 999,
        })
        assert c._max_entries == 999


# ---------------------------------------------------------------------------
# Integration: _correct_batch uses cache
# ---------------------------------------------------------------------------

class TestCorrectionBaseIntegration:
    def _make_mock_client(self, response_texts: list[str]) -> MagicMock:
        msg = MagicMock()
        msg.content = json.dumps(response_texts, ensure_ascii=False)
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        client = MagicMock()
        client.chat.completions.create.return_value = resp
        return client

    def test_cache_hit_skips_api_call(self) -> None:
        from core.types import BoundingBox, OCRResult
        from ocr.stages.llm_correction import LlmCorrectionStage

        cache = LlmResultCache()
        stage = LlmCorrectionStage()
        model = "qwen2.5:7b-instruct-q4_K_M"

        from ocr.stages.llm_correction_base import _SYSTEM_PROMPT
        cache.put(stage.stage_id, model, _SYSTEM_PROMPT, "错误文字", "正确文字")

        result = OCRResult(
            text="错误文字",
            confidence=0.9,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            image_id="1/0001",
        )
        client = self._make_mock_client(["should not be called"])
        corrected = stage._correct_batch(client, [result], model, 0.0, 30.0, {}, cache)
        client.chat.completions.create.assert_not_called()
        assert corrected == ["正确文字"]

    def test_cache_miss_calls_api_and_populates(self) -> None:
        from core.types import BoundingBox, OCRResult
        from ocr.stages.llm_correction import LlmCorrectionStage
        from ocr.stages.llm_correction_base import _SYSTEM_PROMPT

        cache = LlmResultCache()
        stage = LlmCorrectionStage()
        model = "qwen2.5:7b-instruct-q4_K_M"

        result = OCRResult(
            text="错误文字",
            confidence=0.9,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            image_id="1/0001",
        )
        client = self._make_mock_client(["正确文字"])
        corrected = stage._correct_batch(client, [result], model, 0.0, 30.0, {}, cache)
        client.chat.completions.create.assert_called_once()
        assert corrected == ["正确文字"]
        assert cache.get(stage.stage_id, model, _SYSTEM_PROMPT, "错误文字") == "正确文字"

    def test_partial_cache_hit_sends_only_misses(self) -> None:
        from core.types import BoundingBox, OCRResult
        from ocr.stages.llm_correction import LlmCorrectionStage
        from ocr.stages.llm_correction_base import _SYSTEM_PROMPT

        cache = LlmResultCache()
        stage = LlmCorrectionStage()
        model = "m"
        cache.put(stage.stage_id, model, _SYSTEM_PROMPT, "cached", "hit")

        def make_r(text: str) -> OCRResult:
            return OCRResult(
                text=text,
                confidence=0.9,
                bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
                image_id="1/0001",
            )

        batch = [make_r("cached"), make_r("uncached")]
        client = self._make_mock_client(["fixed"])
        corrected = stage._correct_batch(client, batch, model, 0.0, 30.0, {}, cache)

        call_args = client.chat.completions.create.call_args
        sent_content = json.loads(
            next(m["content"] for m in call_args.kwargs["messages"] if m["role"] == "user")
        )
        assert sent_content == ["uncached"]
        assert corrected == ["hit", "fixed"]
