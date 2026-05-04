"""
OpenRouterDeduplicationStage — semantic deduplication via the OpenRouter API.

Registration key: "openrouter_dedup"

Uses an LLM via OpenRouter to semantically identify duplicate OCR lines.
This is the API-tier equivalent of EmbeddingDeduplicationStage: it catches
near-duplicate lines that differ in wording rather than exact text, without
requiring a local embedding model or subprocess.

Protocol:
    The stage sends OCR texts as a JSON array to the LLM with a system
    prompt asking it to return a same-length JSON array of canonical indices
    (group_assignments[i] = lowest index in the duplicate group of result i,
    or i itself if not a duplicate).  Group resolution keeps the highest-
    confidence result per group and preserves reading order.

On any API, parse, or shape error the stage returns results unchanged.

Config keys consumed:
    openrouter_dedup_model        (str)   Model slug
                                          [default: qwen/qwen-2.5-7b-instruct]
    openrouter_api_key            (str)   OpenRouter API key  [default: ""]
    openrouter_base_url           (str)   API base URL
                                          [default: https://openrouter.ai/api/v1]
    openrouter_dedup_temperature  (float) Model temperature   [default: 0.0]
    openrouter_dedup_timeout      (float) Seconds per request [default: 60.0]
    openrouter_site_url           (str)   HTTP-Referer header
    openrouter_site_name          (str)   X-Title header
"""

from __future__ import annotations

import json
import logging
import os

from openai import OpenAI, OpenAIError

from core.types import OCRResult
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "qwen/qwen-2.5-7b-instruct"
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_TIMEOUT = 60.0
_DEFAULT_SITE_URL = "https://github.com/Coltgun/OCR-project"
_DEFAULT_SITE_NAME = "Chinese OCR App"

_SYSTEM_PROMPT = (
    "你是一个中文OCR后处理专家，专门负责去除重复内容。\n"
    "用户会发给你一个JSON数组，每个元素是一段OCR识别出的文字（带有索引0, 1, 2...）。\n"
    "你的任务：\n"
    "1. 找出语义上重复或高度相似的条目。\n"
    "2. 对每个条目，返回其所属重复组中最小的索引（即规范索引）。\n"
    "   如果该条目没有重复，返回其自身的索引。\n"
    "3. 按照原始顺序返回一个JSON整数数组，元素个数必须与输入完全相同。\n"
    "4. 只输出JSON数组，不要输出任何其他内容。\n"
    "示例输入：[\"他走了\", \"他走了。\", \"天空是蓝色的\"]\n"
    "示例输出：[0, 0, 2]"
)


class OpenRouterDeduplicationStage(PostProcessStage, register_as="openrouter_dedup"):
    """Remove semantic duplicates from OCR results using the OpenRouter API.

    Sends texts to an LLM to identify duplicate groups, then keeps the
    highest-confidence result per group in original reading order.
    Falls back to returning results unchanged on any error.
    """

    @property
    def stage_id(self) -> str:
        """Stage identifier."""
        return "openrouter_dedup"

    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Remove semantic duplicates from *results*.

        Args:
            results: Input OCR results.
            config:  Full application config dict.

        Returns:
            De-duplicated list in original reading order.
        """
        if len(results) < 2:
            return results

        model: str = str(config.get("openrouter_dedup_model") or _DEFAULT_MODEL)
        base_url: str = str(config.get("openrouter_base_url") or _DEFAULT_BASE_URL)
        api_key: str = str(
            config.get("openrouter_api_key")
            or os.environ.get("OPENROUTER_API_KEY", "")
        )
        temperature: float = float(
            config.get("openrouter_dedup_temperature", _DEFAULT_TEMPERATURE)
        )
        timeout: float = float(config.get("openrouter_dedup_timeout", _DEFAULT_TIMEOUT))
        site_url: str = str(config.get("openrouter_site_url", _DEFAULT_SITE_URL))
        site_name: str = str(config.get("openrouter_site_name", _DEFAULT_SITE_NAME))

        client = OpenAI(base_url=base_url, api_key=api_key)

        try:
            group_assignments = self._request_assignments(
                client, results, model, temperature, timeout, site_url, site_name
            )
        except Exception as exc:
            logger.error(
                "OpenRouterDeduplicationStage: failed (%s) — returning unchanged.", exc
            )
            return results

        kept = self._resolve_groups(results, group_assignments)
        removed = len(results) - len(kept)
        if removed:
            logger.info(
                "OpenRouterDeduplicationStage: removed %d duplicate(s), %d remain.",
                removed, len(kept),
            )
        return kept

    # ------------------------------------------------------------------
    # API call
    # ------------------------------------------------------------------

    @staticmethod
    def _request_assignments(
        client: OpenAI,
        results: list[OCRResult],
        model: str,
        temperature: float,
        timeout: float,
        site_url: str,
        site_name: str,
    ) -> list[int]:
        """Call the LLM and return group_assignments list.

        Raises:
            RuntimeError: On API error, parse error, or shape mismatch.
        """
        texts = [r.text for r in results]
        user_content = json.dumps(texts, ensure_ascii=False)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=temperature,
                timeout=timeout,
                extra_headers={
                    "HTTP-Referer": site_url,
                    "X-Title": site_name,
                },
            )
        except OpenAIError as exc:
            raise RuntimeError(f"OpenRouter API error: {exc}") from exc

        raw = (response.choices[0].message.content or "").strip()

        # Strip markdown fences
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(line for line in lines if not line.startswith("```")).strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from LLM: {exc}") from exc

        if not isinstance(parsed, list):
            raise RuntimeError(f"LLM returned non-list: {type(parsed).__name__}")

        if len(parsed) != len(results):
            raise RuntimeError(
                f"LLM returned {len(parsed)} assignments for {len(results)} inputs."
            )

        # Validate and coerce to int; clamp to valid range
        n = len(results)
        assignments: list[int] = []
        for val in parsed:
            try:
                idx = int(val)
            except (TypeError, ValueError):
                raise RuntimeError(f"Non-integer assignment value: {val!r}")
            if not (0 <= idx < n):
                raise RuntimeError(f"Assignment index {idx} out of range [0, {n}).")
            assignments.append(idx)

        return assignments

    # ------------------------------------------------------------------
    # Group resolution (same pattern as EmbeddingDeduplicationStage)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_groups(
        results: list[OCRResult],
        group_assignments: list[int],
    ) -> list[OCRResult]:
        """Keep the highest-confidence result per duplicate group.

        Args:
            results:          Input OCR results.
            group_assignments: group_assignments[i] == canonical index for i.

        Returns:
            De-duplicated list in original reading order.
        """
        groups: dict[int, list[tuple[int, OCRResult]]] = {}
        for idx, result in enumerate(results):
            canonical = group_assignments[idx]
            groups.setdefault(canonical, []).append((idx, result))

        best: dict[int, tuple[int, OCRResult]] = {}
        for canonical, members in groups.items():
            winner_idx, winner = max(
                members, key=lambda t: (t[1].confidence, -t[0])
            )
            best[canonical] = (winner_idx, winner)

        ordered = sorted(best.values(), key=lambda t: t[0])
        return [result for _, result in ordered]
