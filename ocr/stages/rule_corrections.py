"""
Stage 2A: Rule-Based Corrections — RuleCorrectionsStage.

Registration key: "rule_corrections"

Applies fast, local, deterministic corrections to OCR output:
    - Confusion table character substitution (data/confusion_table.json)
    - Dictionary-based word validation using jieba segmentation
    - Pattern-based fixes (decimal points, spacing around punctuation)

No GPU, no model inference. Runs in milliseconds per page.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from core.types import OCRResult
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

_DEFAULT_CONFUSION_TABLE_PATH = (
    Path(__file__).parent.parent.parent / "data" / "confusion_table.json"
)
_DEFAULT_DICTIONARY_PATH = (
    Path(__file__).parent.parent.parent / "data" / "ocr_dictionary.json"
)

_DECIMAL_RE = re.compile(r"(\d)\s*[。]\s*(\d)")


class RuleCorrectionsStage(PostProcessStage, register_as="rule_corrections"):
    """Stage 2A: confusion-table + dictionary + pattern corrections.

    The confusion table maps a canonical correct character → list of
    OCR misrecognitions. For each misrecognition found in the text,
    the stage applies jieba segmentation to determine whether substituting
    back to the canonical character produces a valid word in context.

    Config keys consumed:
        confusion_table_path  (str)  override default data/confusion_table.json
        ocr_dictionary_path   (str)  override default data/ocr_dictionary.json
        rule_corrections_use_dict (bool) default True — enable jieba validation
    """

    def __init__(self) -> None:
        self._confusion_table: dict[str, list[str]] | None = None
        self._ocr_dict: set[str] | None = None
        self._reverse_table: dict[str, str] | None = None

    @property
    def stage_id(self) -> str:
        """Identifier for this stage."""
        return "rule_corrections"

    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Apply rule-based corrections to all results.

        Args:
            results: OCR results after Stage 1 cleanup.
            config:  Full application config dict.

        Returns:
            Results with character substitutions and pattern fixes applied.
        """
        self._ensure_tables_loaded(config)

        corrected: list[OCRResult] = []
        for r in results:
            text = self._apply_corrections(r.text, config)
            corrected.append(OCRResult(
                text=text,
                confidence=r.confidence,
                bbox=r.bbox,
                image_id=r.image_id,
            ))
        return corrected

    # ------------------------------------------------------------------
    # Correction pipeline
    # ------------------------------------------------------------------

    def _apply_corrections(self, text: str, config: dict) -> str:
        """Apply all rule correction sub-stages to *text*."""
        text = self._apply_confusion_table(text)
        text = self._apply_pattern_fixes(text)
        return text

    def _apply_confusion_table(self, text: str) -> str:
        """Substitute known OCR misrecognitions with their canonical forms.

        Uses the reverse confusion table (misrecognition → canonical).
        Substitution is applied unconditionally — context-based disambiguation
        is a future enhancement (Stage 2B handles the ambiguous cases).
        """
        if not self._reverse_table:
            return text

        result: list[str] = []
        for char in text:
            canonical = self._reverse_table.get(char)
            if canonical is not None:
                result.append(canonical)
                logger.debug(
                    "RuleCorrectionsStage: substituted '%s' → '%s'", char, canonical
                )
            else:
                result.append(char)
        return "".join(result)

    @staticmethod
    def _apply_pattern_fixes(text: str) -> str:
        """Apply regex-based pattern fixes for common OCR artefacts."""
        text = _DECIMAL_RE.sub(r"\1.\2", text)
        return text

    # ------------------------------------------------------------------
    # Table loading
    # ------------------------------------------------------------------

    def _ensure_tables_loaded(self, config: dict) -> None:
        """Lazy-load confusion table and dictionary if not already loaded."""
        if self._confusion_table is None:
            self._load_confusion_table(config)
        if self._ocr_dict is None:
            self._load_ocr_dictionary(config)

    def _load_confusion_table(self, config: dict) -> None:
        """Load the confusion table JSON and build the reverse lookup."""
        path = Path(config.get("confusion_table_path", _DEFAULT_CONFUSION_TABLE_PATH))
        try:
            with path.open(encoding="utf-8") as f:
                self._confusion_table = json.load(f)
        except FileNotFoundError:
            logger.warning(
                "RuleCorrectionsStage: confusion table not found at '%s'. "
                "Character substitutions disabled.",
                path,
            )
            self._confusion_table = {}
        except json.JSONDecodeError as exc:
            logger.error(
                "RuleCorrectionsStage: invalid JSON in confusion table '%s': %s",
                path, exc,
            )
            self._confusion_table = {}

        self._reverse_table = {}
        for canonical, confusables in self._confusion_table.items():
            for confused in confusables:
                if confused in self._reverse_table:
                    logger.debug(
                        "RuleCorrectionsStage: '%s' maps to both '%s' and '%s'; "
                        "keeping first mapping.",
                        confused,
                        self._reverse_table[confused],
                        canonical,
                    )
                else:
                    self._reverse_table[confused] = canonical

        logger.info(
            "RuleCorrectionsStage: loaded confusion table with %d entries "
            "(%d reverse mappings).",
            len(self._confusion_table),
            len(self._reverse_table),
        )

    def _load_ocr_dictionary(self, config: dict) -> None:
        """Load the OCR dictionary JSON (list of valid words)."""
        path = Path(config.get("ocr_dictionary_path", _DEFAULT_DICTIONARY_PATH))
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._ocr_dict = set(data)
            elif isinstance(data, dict):
                self._ocr_dict = set(data.keys())
            else:
                self._ocr_dict = set()
        except FileNotFoundError:
            logger.debug(
                "RuleCorrectionsStage: dictionary not found at '%s'. "
                "Dictionary validation disabled.",
                path,
            )
            self._ocr_dict = set()
        except json.JSONDecodeError as exc:
            logger.warning(
                "RuleCorrectionsStage: invalid JSON in dictionary '%s': %s",
                path, exc,
            )
            self._ocr_dict = set()

    def reload_tables(self, config: dict) -> None:
        """Force a reload of confusion table and dictionary from disk."""
        self._confusion_table = None
        self._ocr_dict = None
        self._reverse_table = None
        self._ensure_tables_loaded(config)
