"""Tests for RuleCorrectionsStage (Stage 2A)."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from core.types import OCRResult
from ocr.stages.base import PostProcessStage
from ocr.stages.rule_corrections import RuleCorrectionsStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(text: str, confidence: float = 0.9) -> OCRResult:
    return OCRResult(text=text, confidence=confidence)


def run_stage(
    stage: RuleCorrectionsStage,
    results: list[OCRResult],
    config: dict | None = None,
) -> list[OCRResult]:
    return stage.process(results, config or {})


@pytest.fixture()
def stage_with_table(tmp_path: Path) -> tuple[RuleCorrectionsStage, dict]:
    """Return a stage with a small in-memory confusion table via temp file."""
    table = {
        "己": ["已", "巳"],
        "末": ["未"],
        "1": ["l", "I"],
    }
    table_path = tmp_path / "confusion.json"
    table_path.write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")

    dict_path = tmp_path / "dictionary.json"
    dict_path.write_text("[]", encoding="utf-8")

    config = {
        "confusion_table_path": str(table_path),
        "ocr_dictionary_path": str(dict_path),
    }
    return RuleCorrectionsStage(), config


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_rule_corrections(self) -> None:
        assert PostProcessStage.get("rule_corrections") is RuleCorrectionsStage

    def test_stage_id(self) -> None:
        assert RuleCorrectionsStage().stage_id == "rule_corrections"


# ---------------------------------------------------------------------------
# Confusion table loading
# ---------------------------------------------------------------------------

class TestTableLoading:
    def test_loads_table_from_path(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        stage._ensure_tables_loaded(config)
        assert stage._confusion_table is not None
        assert "己" in stage._confusion_table

    def test_builds_reverse_table(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        stage._ensure_tables_loaded(config)
        assert stage._reverse_table is not None
        assert stage._reverse_table.get("已") == "己"
        assert stage._reverse_table.get("巳") == "己"
        assert stage._reverse_table.get("未") == "末"

    def test_missing_table_file_graceful(self, tmp_path: Path) -> None:
        config = {
            "confusion_table_path": str(tmp_path / "nonexistent.json"),
            "ocr_dictionary_path": str(tmp_path / "nonexistent2.json"),
        }
        stage = RuleCorrectionsStage()
        stage._ensure_tables_loaded(config)
        assert stage._confusion_table == {}

    def test_invalid_json_graceful(self, tmp_path: Path) -> None:
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("{invalid json", encoding="utf-8")
        dict_path = tmp_path / "d.json"
        dict_path.write_text("[]", encoding="utf-8")
        config = {
            "confusion_table_path": str(bad_path),
            "ocr_dictionary_path": str(dict_path),
        }
        stage = RuleCorrectionsStage()
        stage._ensure_tables_loaded(config)
        assert stage._confusion_table == {}

    def test_table_only_loaded_once(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        stage._ensure_tables_loaded(config)
        first = id(stage._confusion_table)
        stage._ensure_tables_loaded(config)
        assert id(stage._confusion_table) == first


# ---------------------------------------------------------------------------
# Confusion table substitution
# ---------------------------------------------------------------------------

class TestConfusionSubstitution:
    def test_substitutes_known_misrecognition(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        results = [make_result("自已为是")]
        out = run_stage(stage, results, config)
        assert out[0].text == "自己为是"

    def test_no_substitution_for_unknown(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        results = [make_result("你好世界")]
        out = run_stage(stage, results, config)
        assert out[0].text == "你好世界"

    def test_multiple_substitutions_in_one_text(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        results = [make_result("未来已到来")]
        out = run_stage(stage, results, config)
        assert out[0].text == "末来己到来"

    def test_digit_misrecognition_substituted(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        results = [make_result("第l章")]
        out = run_stage(stage, results, config)
        assert out[0].text == "第1章"

    def test_confidence_and_bbox_preserved(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        from core.types import BoundingBox
        stage, config = stage_with_table
        r = OCRResult(
            text="自已",
            confidence=0.75,
            bbox=BoundingBox(0, 0, 50, 10),
            image_id="0003",
        )
        out = run_stage(stage, [r], config)
        assert out[0].confidence == 0.75
        assert out[0].bbox == r.bbox
        assert out[0].image_id == r.image_id


# ---------------------------------------------------------------------------
# Pattern fixes
# ---------------------------------------------------------------------------

class TestPatternFixes:
    def test_decimal_point_fixed(self) -> None:
        text = RuleCorrectionsStage._apply_pattern_fixes("3。14")
        assert text == "3.14"

    def test_decimal_with_spaces_fixed(self) -> None:
        text = RuleCorrectionsStage._apply_pattern_fixes("3 。 14")
        assert text == "3.14"

    def test_no_decimal_fix_for_non_numeric(self) -> None:
        text = RuleCorrectionsStage._apply_pattern_fixes("好。坏")
        assert text == "好。坏"


# ---------------------------------------------------------------------------
# process() integration
# ---------------------------------------------------------------------------

class TestProcess:
    def test_empty_input_returns_empty(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        assert run_stage(stage, [], config) == []

    def test_multiple_results_all_corrected(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        results = [
            make_result("自已为是"),
            make_result("末来"),
            make_result("你好"),
        ]
        out = run_stage(stage, results, config)
        assert len(out) == 3
        assert out[0].text == "自己为是"
        assert out[1].text == "末来"
        assert out[2].text == "你好"

    def test_uses_real_confusion_table_by_default(self) -> None:
        stage = RuleCorrectionsStage()
        config = {}
        results = [make_result("自已为是")]
        out = run_stage(stage, results, config)
        assert out[0].text == "自己为是"

    def test_reload_tables_forces_reload(
        self, stage_with_table: tuple[RuleCorrectionsStage, dict]
    ) -> None:
        stage, config = stage_with_table
        stage._ensure_tables_loaded(config)
        original_id = id(stage._confusion_table)
        stage.reload_tables(config)
        assert id(stage._confusion_table) != original_id
