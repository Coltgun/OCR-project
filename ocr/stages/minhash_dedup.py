"""
MinHashDeduplicationStage — near-duplicate OCR result removal using MinHash LSH.

Registration key: "minhash_dedup"

Algorithm:
    1. Tokenise each result's text into character-level shingles (n=2 by default).
    2. Compute a MinHash signature for each result.
    3. Use a MinHash LSH index to find near-duplicates (Jaccard similarity ≥ threshold).
    4. Keep only the highest-confidence result from each duplicate group.
       If confidences are equal, keep the first occurrence (preserves reading order).

Config keys consumed:
    dedup_threshold     (float)  Jaccard similarity threshold  [default: 0.85]
    dedup_num_perm      (int)    Number of MinHash permutations [default: 128]
    dedup_shingle_size  (int)    Character n-gram size          [default: 2]

Why this stage:
    PaddleOCR occasionally returns duplicate or near-duplicate lines when the
    capture region slightly overlaps with a previous frame, or when text
    regions are detected multiple times at slightly different bounding boxes.
    MinHash LSH removes these duplicates in O(n) average time without needing
    to compare every pair.
"""

from __future__ import annotations

import logging

from datasketch import MinHash, MinHashLSH

from core.types import OCRResult
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 0.85
_DEFAULT_NUM_PERM = 128
_DEFAULT_SHINGLE_SIZE = 2


class MinHashDeduplicationStage(PostProcessStage, register_as="minhash_dedup"):
    """Remove near-duplicate OCRResult entries using MinHash LSH.

    Duplicate groups are resolved by keeping the highest-confidence result.
    Original reading order is preserved among non-duplicate results.
    """

    @property
    def stage_id(self) -> str:
        """Stage identifier."""
        return "minhash_dedup"

    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Remove near-duplicates from *results*.

        Args:
            results: Input OCR results.
            config:  Full application config dict.

        Returns:
            De-duplicated list in original reading order.
        """
        if len(results) < 2:
            return results

        threshold: float = float(config.get("dedup_threshold", _DEFAULT_THRESHOLD))
        num_perm: int = int(config.get("dedup_num_perm", _DEFAULT_NUM_PERM))
        shingle_size: int = int(config.get("dedup_shingle_size", _DEFAULT_SHINGLE_SIZE))

        minhashes = [
            self._compute_minhash(r.text, num_perm, shingle_size)
            for r in results
        ]

        duplicate_of: dict[int, int] = self._find_duplicates(
            minhashes, threshold, num_perm
        )

        kept = self._resolve_groups(results, duplicate_of)
        removed = len(results) - len(kept)
        if removed:
            logger.info(
                "MinHashDeduplicationStage: removed %d near-duplicate(s) "
                "(threshold=%.2f, %d results remain).",
                removed, threshold, len(kept),
            )
        return kept

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _shingles(text: str, n: int) -> set[bytes]:
        """Return the set of character n-gram shingles from *text* as bytes."""
        if len(text) < n:
            return {text.encode("utf-8")} if text else set()
        return {text[i : i + n].encode("utf-8") for i in range(len(text) - n + 1)}

    @staticmethod
    def _compute_minhash(text: str, num_perm: int, shingle_size: int) -> MinHash:
        """Build a MinHash object for *text*."""
        m = MinHash(num_perm=num_perm)
        for shingle in MinHashDeduplicationStage._shingles(text, shingle_size):
            m.update(shingle)
        return m

    @staticmethod
    def _find_duplicates(
        minhashes: list[MinHash],
        threshold: float,
        num_perm: int,
    ) -> dict[int, int]:
        """Return a mapping of duplicate_index → canonical_index.

        For each pair that meets the threshold, the later-indexed item is
        marked as a duplicate of the earlier-indexed item.  This preserves
        reading order: the first occurrence is always canonical.
        """
        lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)

        duplicate_of: dict[int, int] = {}

        for idx, mh in enumerate(minhashes):
            key = str(idx)
            candidates = lsh.query(mh)
            if candidates:
                # Mark this idx as duplicate of the first (lowest-index) candidate
                canonical = min(int(c) for c in candidates)
                duplicate_of[idx] = canonical
                logger.debug(
                    "MinHashDeduplicationStage: result[%d] is near-duplicate of result[%d].",
                    idx, canonical,
                )
            else:
                try:
                    lsh.insert(key, mh)
                except ValueError:
                    pass  # key already present — shouldn't happen, but safe

        return duplicate_of

    @staticmethod
    def _resolve_groups(
        results: list[OCRResult],
        duplicate_of: dict[int, int],
    ) -> list[OCRResult]:
        """From each duplicate group keep the highest-confidence result.

        Iterates results in original order to preserve reading order.
        """
        # Build groups: canonical_idx → list of (idx, result)
        groups: dict[int, list[tuple[int, OCRResult]]] = {}
        for idx, result in enumerate(results):
            canonical = duplicate_of.get(idx, idx)
            groups.setdefault(canonical, []).append((idx, result))

        # For each group pick the member with highest confidence; break ties by
        # lowest index (earlier in reading order wins)
        best: dict[int, tuple[int, OCRResult]] = {}
        for canonical, members in groups.items():
            winner_idx, winner = max(
                members, key=lambda t: (t[1].confidence, -t[0])
            )
            best[canonical] = (winner_idx, winner)

        # Re-sort winners by their original index to maintain reading order
        ordered = sorted(best.values(), key=lambda t: t[0])
        return [result for _, result in ordered]
