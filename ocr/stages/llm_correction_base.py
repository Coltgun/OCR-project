"""
LlmCorrectionBase — shared logic for LLM-based OCR correction stages.

Subclasses only need to override _make_client() and optionally
_extra_create_kwargs() to supply provider-specific options
(e.g. HTTP-Referer header for OpenRouter).

This base keeps all JSON-batch correction, response parsing,
fallback, and field-preservation logic in one place.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import abstractmethod
from dataclasses import replace
from typing import Optional

from openai import AsyncOpenAI, OpenAI, OpenAIError

from core.types import OCRResult
from llm.cache import LlmResultCache
from llm.clients import get_async_openai_client, get_openai_client
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 10
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_TIMEOUT = 60.0

_SYSTEM_PROMPT = (
    "你是中文OCR纠错专家。输入：中文文字JSON数组。"
    "规则：仅修正OCR形近字错误，勿改标点和内容，保持顺序和数量。"
    "输出：仅返回等长JSON数组。"
    "例：输入[\"天空是蓝色地\"]→输出[\"天空是蓝色的\"]"
)


class LlmCorrectionBase(PostProcessStage):
    """Abstract base for LLM OCR correction stages.

    Subclasses must implement _make_client() and provide
    model/temperature/timeout/batch_size from the config dict.
    """

    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Correct OCR errors using the configured LLM.

        Args:
            results: Input OCR results.
            config:  Full application config dict.

        Returns:
            Results with corrected text fields; all other fields unchanged.
        """
        if not results:
            return results

        model, temperature, timeout, batch_size = self._read_config(config)
        max_concurrency = self._max_concurrency(config)
        async_client = self._make_async_client(config) if max_concurrency > 1 else None
        cache = LlmResultCache.from_config(config)

        send_indices, send_results, skip_indices = self._partition_skip(results, config)

        if send_results:
            batches = [
                send_results[i : i + batch_size]
                for i in range(0, len(send_results), batch_size)
            ]

            if async_client is not None and max_concurrency > 1:
                batch_results = self._correct_batches_concurrent(
                    batches, async_client, model, temperature, timeout, config,
                    max_concurrency, cache,
                )
            else:
                sync_client = self._make_client(config)
                batch_results = [
                    self._correct_batch(
                        sync_client, b, model, temperature, timeout, config, cache
                    )
                    for b in batches
                ]

            if cache is not None:
                cache.flush()

            corrected_send: list[OCRResult] = []
            for batch, corrected_texts in zip(batches, batch_results):
                for result, new_text in zip(batch, corrected_texts):
                    if logger.isEnabledFor(logging.DEBUG) and new_text != result.text:
                        logger.debug(
                            "%s: corrected '%s' → '%s'",
                            self.stage_id, result.text, new_text,
                        )
                    corrected_send.append(replace(result, text=new_text))
        else:
            corrected_send = []

        output: list[OCRResult] = list(results)
        for orig_idx, corrected in zip(send_indices, corrected_send):
            output[orig_idx] = corrected

        return output

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def _make_client(self, config: dict) -> OpenAI:
        """Return a configured OpenAI client for this provider."""

    @abstractmethod
    def _read_config(self, config: dict) -> tuple[str, float, float, int]:
        """Return (model, temperature, timeout, batch_size) from config."""

    def _partition_skip(
        self,
        results: list[OCRResult],
        config: dict,
    ) -> tuple[list[int], list[OCRResult], list[int]]:
        """Partition results into those to send to the LLM and those to skip.

        Returns:
            send_indices:  original positions of results to be corrected.
            send_results:  the corresponding OCRResult objects.
            skip_indices:  original positions of results to skip unchanged.
        """
        threshold = float(
            config.get("llm_skip_high_confidence_threshold", 0.97)
        )
        send_indices: list[int] = []
        send_results: list[OCRResult] = []
        skip_indices: list[int] = []
        for i, r in enumerate(results):
            if self._should_skip(r, threshold):
                skip_indices.append(i)
            else:
                send_indices.append(i)
                send_results.append(r)
        return send_indices, send_results, skip_indices

    @staticmethod
    def _should_skip(result: OCRResult, threshold: float) -> bool:
        """Return True if this result should bypass the LLM."""
        if len(result.text.strip()) <= 1:
            return True
        if result.confidence >= threshold:
            return True
        return False

    def _extra_create_kwargs(self, config: dict) -> dict:
        """Extra kwargs to pass to chat.completions.create (e.g. extra_headers).

        Default: empty dict.  Override in subclasses that need it.
        """
        return {}

    def _make_async_client(self, config: dict) -> Optional[AsyncOpenAI]:
        """Return a cached AsyncOpenAI client for this provider, or None to use sync.

        Override in subclasses that support concurrent async batches.
        """
        return None

    def _max_concurrency(self, config: dict) -> int:
        """Return maximum concurrent API calls. 1 = sequential (default)."""
        return 1

    # ------------------------------------------------------------------
    # Shared implementation
    # ------------------------------------------------------------------

    def _correct_batches_concurrent(
        self,
        batches: list[list[OCRResult]],
        async_client: AsyncOpenAI,
        model: str,
        temperature: float,
        timeout: float,
        config: dict,
        max_concurrency: int,
        cache: Optional[LlmResultCache] = None,
    ) -> list[list[str]]:
        """Send all batches concurrently using asyncio.gather with a semaphore.

        Returns one list of corrected texts per batch, in the same order.
        """
        async def _run_all() -> list[list[str]]:
            sem = asyncio.Semaphore(max_concurrency)

            async def _one(batch: list[OCRResult]) -> list[str]:
                async with sem:
                    return await self._acorrect_batch(
                        async_client, batch, model, temperature, timeout, config, cache
                    )

            return list(await asyncio.gather(*(_one(b) for b in batches)))

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, _run_all()).result()
            return loop.run_until_complete(_run_all())
        except RuntimeError:
            return asyncio.run(_run_all())

    async def _acorrect_batch(
        self,
        async_client: AsyncOpenAI,
        batch: list[OCRResult],
        model: str,
        temperature: float,
        timeout: float,
        config: dict,
        cache: Optional[LlmResultCache] = None,
    ) -> list[str]:
        """Async version of _correct_batch."""
        texts = [r.text for r in batch]
        uncached_indices, uncached_texts, corrected = self._apply_cache_hits(
            texts, model, cache
        )
        if not uncached_texts:
            return corrected

        user_content = json.dumps(uncached_texts, ensure_ascii=False)
        extra = self._extra_create_kwargs(config)

        try:
            response = await async_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=temperature,
                timeout=timeout,
                **extra,
            )
        except OpenAIError as exc:
            logger.warning(
                "%s: async API error for batch of %d: %s — keeping originals.",
                self.stage_id, len(batch), exc,
            )
            return texts
        except Exception as exc:
            logger.warning(
                "%s: async unexpected error for batch of %d: %s — keeping originals.",
                self.stage_id, len(batch), exc,
            )
            return texts

        raw = response.choices[0].message.content or ""
        llm_results = self._parse_response(raw, uncached_texts)
        self._populate_cache(uncached_indices, uncached_texts, llm_results, model, cache)
        for idx, text in zip(uncached_indices, llm_results):
            corrected[idx] = text
        return corrected

    def _correct_batch(
        self,
        client: OpenAI,
        batch: list[OCRResult],
        model: str,
        temperature: float,
        timeout: float,
        config: dict,
        cache: Optional[LlmResultCache] = None,
    ) -> list[str]:
        """Send one batch to the LLM and return corrected texts.

        On any error falls back to original texts.
        """
        texts = [r.text for r in batch]
        uncached_indices, uncached_texts, corrected = self._apply_cache_hits(
            texts, model, cache
        )
        if not uncached_texts:
            return corrected

        user_content = json.dumps(uncached_texts, ensure_ascii=False)
        extra = self._extra_create_kwargs(config)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=temperature,
                timeout=timeout,
                **extra,
            )
        except OpenAIError as exc:
            logger.warning(
                "%s: API error for batch of %d: %s — keeping originals.",
                self.stage_id, len(batch), exc,
            )
            return texts
        except Exception as exc:
            logger.warning(
                "%s: unexpected error for batch of %d: %s — keeping originals.",
                self.stage_id, len(batch), exc,
            )
            return texts

        raw = response.choices[0].message.content or ""
        llm_results = self._parse_response(raw, uncached_texts)
        self._populate_cache(uncached_indices, uncached_texts, llm_results, model, cache)
        for idx, text in zip(uncached_indices, llm_results):
            corrected[idx] = text
        return corrected

    def _apply_cache_hits(
        self,
        texts: list[str],
        model: str,
        cache: Optional[LlmResultCache],
    ) -> tuple[list[int], list[str], list[str]]:
        """Split *texts* into cache hits and misses.

        Returns:
            uncached_indices: positions in *texts* that were not in cache.
            uncached_texts:   the texts at those positions.
            corrected:        full-length list, pre-filled with cached values
                              where available, originals elsewhere.
        """
        corrected = list(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []
        if cache is None:
            return list(range(len(texts))), list(texts), corrected
        for i, text in enumerate(texts):
            hit = cache.get(self.stage_id, model, _SYSTEM_PROMPT, text)
            if hit is None:
                uncached_indices.append(i)
                uncached_texts.append(text)
            else:
                corrected[i] = hit
        return uncached_indices, uncached_texts, corrected

    def _populate_cache(
        self,
        indices: list[int],
        original_texts: list[str],
        corrected_texts: list[str],
        model: str,
        cache: Optional[LlmResultCache],
    ) -> None:
        """Store LLM results in cache, skipping no-op corrections."""
        if cache is None:
            return
        for orig, corrected in zip(original_texts, corrected_texts):
            cache.put(self.stage_id, model, _SYSTEM_PROMPT, orig, corrected)

    @staticmethod
    def _parse_response(raw: str, originals: list[str]) -> list[str]:
        """Parse the LLM JSON response into a list of corrected strings.

        Strips markdown code fences, then tries progressively more lenient
        strategies before falling back to *originals*.
        """
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        # Strategy 1: parse the whole response as JSON
        parsed = None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Strategy 2: extract first JSON array from anywhere in the response
        if not isinstance(parsed, list):
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass

        if not isinstance(parsed, list):
            logger.warning(
                "LlmCorrectionBase._parse_response: could not extract a JSON array "
                "— keeping originals."
            )
            return originals

        expected = len(originals)
        if len(parsed) == expected:
            return [str(t) for t in parsed]

        # Strategy 3: length mismatch — pad short responses with originals,
        # truncate long ones. Better than discarding all corrections.
        logger.warning(
            "LlmCorrectionBase._parse_response: length %d != expected %d "
            "— using partial corrections.", len(parsed), expected,
        )
        result = list(originals)
        for i, t in enumerate(parsed[:expected]):
            result[i] = str(t)
        return result
