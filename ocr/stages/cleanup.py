"""
Stage 1: Raw Text Cleanup — CleanupStage.

Registration key: "cleanup"

Performs fast, deterministic, rule-based cleanup of raw OCR text:
    1A  Encoding normalization (NFC)
    1B  Full-width / half-width normalization (alphanumeric only)
    1C  CJK whitespace cleanup (remove spaces between CJK chars)
    1D  Punctuation normalization (... → ……, -- → ——)
    1E  Garbage text filtering (low confidence, high non-CJK ratio, repeats)

All operations are pure string transformations. No model inference.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from core.types import OCRResult
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

_CJK_RANGES = (
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Extension A
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
)

_CJK_PATTERN = r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u309f\u30a0-\u30ff]"
_CJK_SPACE_RE = re.compile(rf"({_CJK_PATTERN})\s+({_CJK_PATTERN})")

_REPEAT_CHAR_RE = re.compile(r"(.)\1{4,}")


class CleanupStage(PostProcessStage, register_as="cleanup"):
    """Stage 1: deterministic rule-based text cleanup.

    Config keys consumed:
        cleanup_confidence_threshold  (float) default 0.5  — drop lines below this
        cleanup_min_cjk_ratio         (float) default 0.3  — drop lines with less CJK content
        cleanup_min_length            (int)   default 1    — drop lines shorter than this
    """

    @property
    def stage_id(self) -> str:
        """Identifier for this stage."""
        return "cleanup"

    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Apply all cleanup sub-stages to each OCRResult in *results*.

        Args:
            results: Raw OCR results from the engine.
            config:  Full application config dict.

        Returns:
            Cleaned results; low-quality lines are filtered out.
        """
        conf_threshold: float = float(config.get("cleanup_confidence_threshold", 0.5))
        min_cjk_ratio: float = float(config.get("cleanup_min_cjk_ratio", 0.3))
        min_length: int = int(config.get("cleanup_min_length", 1))

        cleaned: list[OCRResult] = []
        for r in results:
            if r.confidence < conf_threshold:
                logger.debug(
                    "CleanupStage: dropped (conf=%.2f < %.2f): %r",
                    r.confidence, conf_threshold, r.text[:40],
                )
                continue

            text = self._clean_text(r.text, min_cjk_ratio, min_length)
            if text is None:
                continue

            cleaned.append(OCRResult(
                text=text,
                confidence=r.confidence,
                bbox=r.bbox,
                image_id=r.image_id,
            ))

        logger.debug(
            "CleanupStage: %d → %d results.", len(results), len(cleaned)
        )
        return cleaned

    # ------------------------------------------------------------------
    # Pipeline sub-stages (also available as static methods for testing)
    # ------------------------------------------------------------------

    def _clean_text(
        self, text: str, min_cjk_ratio: float, min_length: int
    ) -> str | None:
        """Apply all text-level cleanup sub-stages.

        Returns cleaned text, or None if the text should be discarded.
        """
        text = self.normalize_encoding(text)
        text = self.normalize_fullwidth(text)
        text = self.cleanup_cjk_spaces(text)
        text = self.normalize_punctuation(text)
        text = text.strip()

        if len(text) < min_length:
            return None

        if self._is_garbage(text, min_cjk_ratio):
            logger.debug("CleanupStage: filtered garbage: %r", text[:40])
            return None

        return text

    @staticmethod
    def normalize_encoding(text: str) -> str:
        """1A: Normalize text to NFC Unicode form."""
        return unicodedata.normalize("NFC", text)

    @staticmethod
    def normalize_fullwidth(text: str) -> str:
        """1B: Convert full-width ASCII alphanumeric to half-width.

        Chinese punctuation (，。！？etc.) is intentionally preserved.
        Only full-width Latin letters, digits, and certain ASCII symbols
        in the range FF01–FF5E are converted.
        """
        result: list[str] = []
        for char in text:
            cp = ord(char)
            # Full-width digits 0-9 (FF10-FF19) → ASCII digits
            # Full-width upper A-Z (FF21-FF3A) → ASCII upper
            # Full-width lower a-z (FF41-FF5A) → ASCII lower
            # Full-width punctuation (FF01-FF0F, FF1A-FF20, FF3B-FF40, FF5B-FF5E)
            # is intentionally preserved (，。！？；：etc.)
            if (0xFF10 <= cp <= 0xFF19  # digits
                    or 0xFF21 <= cp <= 0xFF3A  # uppercase
                    or 0xFF41 <= cp <= 0xFF5A):  # lowercase
                result.append(chr(cp - 0xFEE0))
            elif cp == 0x3000:
                result.append(" ")
            else:
                result.append(char)
        return "".join(result)

    @staticmethod
    def cleanup_cjk_spaces(text: str) -> str:
        """1C: Remove spaces between adjacent CJK characters.

        Spaces between CJK and Latin/numeric are preserved.
        Applied iteratively until stable.
        """
        while True:
            new_text = _CJK_SPACE_RE.sub(r"\1\2", text)
            if new_text == text:
                break
            text = new_text
        return text

    @staticmethod
    def normalize_punctuation(text: str) -> str:
        """1D: Normalize common OCR punctuation artefacts."""
        text = text.replace("...", "\u2026\u2026")
        text = text.replace("--", "\u2014\u2014")
        return text

    @staticmethod
    def _is_cjk(char: str) -> bool:
        """Return True if *char* is in a CJK Unicode block."""
        cp = ord(char)
        return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)

    @staticmethod
    def _is_garbage(text: str, min_cjk_ratio: float) -> bool:
        """1E/1F: Return True if *text* looks like OCR garbage.

        Criteria:
        - CJK character ratio is below min_cjk_ratio (for lines that contain
          at least one CJK character — pure Latin/number lines are kept as-is).
        - A single character repeated 5+ times (border/separator artefact).
        """
        if not text:
            return True

        cjk_count = sum(1 for c in text if CleanupStage._is_cjk(c))
        has_any_cjk = cjk_count > 0

        if has_any_cjk:
            ratio = cjk_count / len(text)
            if ratio < min_cjk_ratio:
                return True

        if _REPEAT_CHAR_RE.search(text):
            return True

        return False
