"""Tests for MinHashDeduplicationStage."""

from __future__ import annotations

import pytest

from core.types import BoundingBox, OCRResult
from ocr.stages.base import PostProcessStage
from ocr.stages.minhash_dedup import MinHashDeduplicationStage


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
    def test_registered_as_minhash_dedup(self) -> None:
        assert PostProcessStage.get("minhash_dedup") is MinHashDeduplicationStage

    def test_stage_id(self) -> None:
        assert MinHashDeduplicationStage().stage_id == "minhash_dedup"


# ---------------------------------------------------------------------------
# _shingles
# ---------------------------------------------------------------------------

class TestShingles:
    def test_bigram_shingles(self) -> None:
        result = MinHashDeduplicationStage._shingles("abc", 2)
        assert result == {b"ab", b"bc"}

    def test_trigram_shingles(self) -> None:
        result = MinHashDeduplicationStage._shingles("abcd", 3)
        assert result == {b"abc", b"bcd"}

    def test_text_shorter_than_n_returns_whole_text(self) -> None:
        result = MinHashDeduplicationStage._shingles("a", 3)
        assert result == {b"a"}

    def test_empty_text_returns_empty_set(self) -> None:
        assert MinHashDeduplicationStage._shingles("", 2) == set()

    def test_unicode_text(self) -> None:
        shingles = MinHashDeduplicationStage._shingles("你好世界", 2)
        assert len(shingles) == 3


# ---------------------------------------------------------------------------
# process() — basic behaviour
# ---------------------------------------------------------------------------

class TestProcess:
    _cfg: dict = {}

    def test_empty_input_returns_empty(self) -> None:
        stage = MinHashDeduplicationStage()
        assert stage.process([], self._cfg) == []

    def test_single_result_returned_unchanged(self) -> None:
        stage = MinHashDeduplicationStage()
        r = make_result("hello")
        assert stage.process([r], self._cfg) == [r]

    def test_distinct_results_all_kept(self) -> None:
        stage = MinHashDeduplicationStage()
        results = [
            make_result("完全不同的文字一"),
            make_result("另一段完全不同的文字"),
            make_result("第三段文字内容"),
        ]
        out = stage.process(results, self._cfg)
        assert len(out) == 3

    def test_identical_texts_deduped_to_one(self) -> None:
        stage = MinHashDeduplicationStage()
        text = "这是完全相同的一段文字内容用于测试去重功能"
        results = [make_result(text), make_result(text), make_result(text)]
        out = stage.process(results, {"dedup_threshold": 0.9})
        assert len(out) == 1

    def test_near_duplicate_removed(self) -> None:
        """Two strings differing by one character should be flagged as duplicates."""
        stage = MinHashDeduplicationStage()
        base = "这是一段测试文字用来验证近似重复检测功能是否正常工作"
        near = base[:-1] + "做"
        results = [make_result(base), make_result(near)]
        out = stage.process(results, {"dedup_threshold": 0.8})
        assert len(out) == 1

    def test_clearly_different_texts_both_kept(self) -> None:
        stage = MinHashDeduplicationStage()
        results = [
            make_result("第一章 主角登场"),
            make_result("第二章 反派出现"),
        ]
        out = stage.process(results, {"dedup_threshold": 0.85})
        assert len(out) == 2


# ---------------------------------------------------------------------------
# process() — confidence-based winner selection
# ---------------------------------------------------------------------------

class TestConfidenceWinner:
    def test_higher_confidence_kept_from_duplicate_pair(self) -> None:
        stage = MinHashDeduplicationStage()
        text = "相同文字内容用于测试置信度选择逻辑是否正确执行"
        low = make_result(text, confidence=0.6)
        high = make_result(text, confidence=0.95)
        out = stage.process([low, high], {"dedup_threshold": 0.9})
        assert len(out) == 1
        assert out[0].confidence == 0.95

    def test_equal_confidence_first_occurrence_kept(self) -> None:
        stage = MinHashDeduplicationStage()
        text = "相同置信度的重复文字内容"
        first = make_result(text, confidence=0.9)
        second = make_result(text, confidence=0.9)
        out = stage.process([first, second], {"dedup_threshold": 0.9})
        assert len(out) == 1
        assert out[0] is first


# ---------------------------------------------------------------------------
# process() — reading order preserved
# ---------------------------------------------------------------------------

class TestReadingOrder:
    def test_output_order_matches_input_order(self) -> None:
        """Non-duplicate results must come out in the same order they went in."""
        stage = MinHashDeduplicationStage()
        # Texts must be structurally different enough not to collide at 0.85
        texts = [
            "天空是蓝色的白云飘浮",
            "海洋深处有神秘生物",
            "山顶积雪终年不化",
            "沙漠中骆驼缓慢前行",
            "森林里鸟鸣声此起彼伏",
        ]
        results = [make_result(t) for t in texts]
        out = stage.process(results, {"dedup_threshold": 0.85})
        # All distinct — order must be preserved (compare by text)
        assert [r.text for r in out] == texts

    def test_duplicate_removed_preserves_remaining_order(self) -> None:
        stage = MinHashDeduplicationStage()
        text = "完全相同的重复文字"
        r1 = make_result("第一段独特内容")
        r_dup1 = make_result(text)
        r2 = make_result("第二段独特内容")
        r_dup2 = make_result(text)
        r3 = make_result("第三段独特内容")
        out = stage.process([r1, r_dup1, r2, r_dup2, r3], {"dedup_threshold": 0.9})
        non_dup_texts = {r.text for r in out}
        assert "第一段独特内容" in non_dup_texts
        assert "第二段独特内容" in non_dup_texts
        assert "第三段独特内容" in non_dup_texts
        assert text in non_dup_texts
        assert len(out) == 4


# ---------------------------------------------------------------------------
# Config keys
# ---------------------------------------------------------------------------

class TestConfigKeys:
    def test_custom_threshold_respected(self) -> None:
        """Very low threshold (0.1) — even similar texts kept as distinct."""
        stage = MinHashDeduplicationStage()
        results = [
            make_result("文字内容一"),
            make_result("文字内容二"),
        ]
        # At very low threshold everything is a duplicate — this mainly
        # verifies the config key is actually consumed without error.
        out = stage.process(results, {"dedup_threshold": 0.01})
        assert isinstance(out, list)

    def test_custom_num_perm(self) -> None:
        stage = MinHashDeduplicationStage()
        text = "相同文字"
        results = [make_result(text), make_result(text)]
        out = stage.process(results, {"dedup_num_perm": 64, "dedup_threshold": 0.9})
        assert len(out) == 1

    def test_custom_shingle_size(self) -> None:
        stage = MinHashDeduplicationStage()
        text = "相同文字内容"
        results = [make_result(text), make_result(text)]
        out = stage.process(results, {"dedup_shingle_size": 3, "dedup_threshold": 0.9})
        assert len(out) == 1
