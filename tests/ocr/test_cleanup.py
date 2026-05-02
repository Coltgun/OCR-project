"""Tests for CleanupStage (Stage 1)."""

from __future__ import annotations

import pytest

from core.types import BoundingBox, OCRResult
from ocr.stages.base import PostProcessStage
from ocr.stages.cleanup import CleanupStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(text: str, confidence: float = 0.95) -> OCRResult:
    return OCRResult(text=text, confidence=confidence)


def run_cleanup(results: list[OCRResult], **cfg_overrides) -> list[OCRResult]:
    config = {
        "cleanup_confidence_threshold": 0.5,
        "cleanup_min_cjk_ratio": 0.3,
        "cleanup_min_length": 1,
        **cfg_overrides,
    }
    return CleanupStage().process(results, config)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_cleanup(self) -> None:
        assert PostProcessStage.get("cleanup") is CleanupStage

    def test_stage_id(self) -> None:
        assert CleanupStage().stage_id == "cleanup"


# ---------------------------------------------------------------------------
# 1A: normalize_encoding
# ---------------------------------------------------------------------------

class TestNormalizeEncoding:
    def test_nfc_normalization(self) -> None:
        composed = "\u00e9"        # é precomposed
        decomposed = "e\u0301"     # e + combining acute
        assert CleanupStage.normalize_encoding(decomposed) == composed

    def test_plain_text_unchanged(self) -> None:
        t = "你好世界"
        assert CleanupStage.normalize_encoding(t) == t


# ---------------------------------------------------------------------------
# 1B: normalize_fullwidth
# ---------------------------------------------------------------------------

class TestNormalizeFullwidth:
    def test_fullwidth_digits_converted(self) -> None:
        assert CleanupStage.normalize_fullwidth("１２３") == "123"

    def test_fullwidth_letters_converted(self) -> None:
        assert CleanupStage.normalize_fullwidth("ＡＢＣ") == "ABC"

    def test_fullwidth_space_converted(self) -> None:
        assert CleanupStage.normalize_fullwidth("\u3000") == " "

    def test_chinese_punctuation_preserved(self) -> None:
        punct = "，。！？；：《》【】"
        assert CleanupStage.normalize_fullwidth(punct) == punct

    def test_fullwidth_punctuation_outside_alphanum_range_preserved(self) -> None:
        assert CleanupStage.normalize_fullwidth("，") == "，"  # U+FF0C preserved
        assert CleanupStage.normalize_fullwidth("！") == "！"  # U+FF01 preserved
        assert CleanupStage.normalize_fullwidth("？") == "？"  # U+FF1F preserved

    def test_mixed_text(self) -> None:
        result = CleanupStage.normalize_fullwidth("测试１２３ＡＢＣ，。")
        assert result == "测试123ABC，。"  # punctuation ，。 preserved, alphanum converted


# ---------------------------------------------------------------------------
# 1C: cleanup_cjk_spaces
# ---------------------------------------------------------------------------

class TestCleanupCjkSpaces:
    def test_single_space_between_cjk_removed(self) -> None:
        assert CleanupStage.cleanup_cjk_spaces("你 好") == "你好"

    def test_multiple_spaces_removed(self) -> None:
        assert CleanupStage.cleanup_cjk_spaces("你   好   世   界") == "你好世界"

    def test_applied_iteratively(self) -> None:
        result = CleanupStage.cleanup_cjk_spaces("你 好 世 界")
        assert result == "你好世界"

    def test_space_between_cjk_and_latin_preserved(self) -> None:
        text = "第 3 章"
        assert CleanupStage.cleanup_cjk_spaces(text) == "第 3 章"

    def test_no_cjk_unchanged(self) -> None:
        text = "hello world"
        assert CleanupStage.cleanup_cjk_spaces(text) == text

    def test_leading_trailing_spaces_preserved(self) -> None:
        text = " 你好 "
        assert CleanupStage.cleanup_cjk_spaces(text) == " 你好 "


# ---------------------------------------------------------------------------
# 1D: normalize_punctuation
# ---------------------------------------------------------------------------

class TestNormalizePunctuation:
    def test_ellipsis_normalized(self) -> None:
        assert CleanupStage.normalize_punctuation("等等...") == "等等\u2026\u2026"

    def test_double_dash_normalized(self) -> None:
        assert CleanupStage.normalize_punctuation("--") == "\u2014\u2014"

    def test_no_change_for_clean_text(self) -> None:
        text = "你好世界。"
        assert CleanupStage.normalize_punctuation(text) == text


# ---------------------------------------------------------------------------
# 1E/1F: garbage filtering
# ---------------------------------------------------------------------------

class TestGarbageFilter:
    def test_solid_cjk_not_garbage(self) -> None:
        assert CleanupStage._is_garbage("你好世界", 0.3) is False

    def test_repeated_char_is_garbage(self) -> None:
        assert CleanupStage._is_garbage("————————", 0.3) is True

    def test_low_cjk_ratio_is_garbage(self) -> None:
        assert CleanupStage._is_garbage("abc你de", 0.5) is True

    def test_pure_latin_with_cjk_threshold_ok(self) -> None:
        assert CleanupStage._is_garbage("hello world", 0.3) is False

    def test_empty_string_is_garbage(self) -> None:
        assert CleanupStage._is_garbage("", 0.3) is True

    def test_five_repeated_chars_is_garbage(self) -> None:
        assert CleanupStage._is_garbage("aaaaa", 0.3) is True

    def test_four_repeated_chars_not_garbage(self) -> None:
        assert CleanupStage._is_garbage("aaaa", 0.3) is False


# ---------------------------------------------------------------------------
# process() integration
# ---------------------------------------------------------------------------

class TestProcess:
    def test_low_confidence_dropped(self) -> None:
        results = [make_result("你好", confidence=0.3)]
        assert run_cleanup(results, cleanup_confidence_threshold=0.5) == []

    def test_high_confidence_kept(self) -> None:
        results = [make_result("你好", confidence=0.9)]
        out = run_cleanup(results)
        assert len(out) == 1

    def test_fullwidth_cleaned(self) -> None:
        results = [make_result("测试１２３")]
        out = run_cleanup(results)
        assert out[0].text == "测试123"

    def test_cjk_spaces_removed(self) -> None:
        results = [make_result("你 好 世 界")]
        out = run_cleanup(results)
        assert out[0].text == "你好世界"

    def test_garbage_filtered(self) -> None:
        results = [make_result("————————————")]
        out = run_cleanup(results)
        assert out == []

    def test_bbox_and_image_id_preserved(self) -> None:
        r = OCRResult(
            text="你好世界",
            confidence=0.9,
            bbox=BoundingBox(0, 0, 100, 20),
            image_id="0042",
        )
        out = run_cleanup([r])
        assert out[0].bbox == r.bbox
        assert out[0].image_id == r.image_id

    def test_empty_input_returns_empty(self) -> None:
        assert run_cleanup([]) == []

    def test_multiple_results_processed(self) -> None:
        results = [
            make_result("你好世界", 0.9),
            make_result("测试１２３", 0.8),
            make_result("低置信度", 0.1),
        ]
        out = run_cleanup(results, cleanup_confidence_threshold=0.5)
        assert len(out) == 2
        assert out[1].text == "测试123"
