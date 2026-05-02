"""
LlmCorrectionStage — OCR error correction via a local Ollama LLM.

Registration key: "llm_correction"

No subprocess isolation required: the openai library has no torch dependency,
so this stage runs directly in the main process without DLL conflicts.

The stage sends each OCR result's text to the local Ollama API and replaces
the text with the model's correction.  Results are processed in batches to
keep prompt size manageable.  On any API failure the original text is kept.

Prompt design:
    The system prompt instructs the model to act as a Chinese OCR corrector:
    fix character-level OCR errors (misread strokes, similar-looking chars),
    preserve punctuation, do NOT paraphrase or add content, return ONLY the
    corrected text.  A compact JSON batch protocol is used to avoid parsing
    ambiguity.

Config keys consumed:
    llm_model          (str)   Ollama model tag       [default: qwen2.5:7b-instruct-q4_K_M]
    llm_base_url       (str)   Ollama API base URL    [default: http://localhost:11434/v1]
    llm_api_key        (str)   API key (Ollama ignores it, but openai requires one)
                               [default: ollama]
    llm_batch_size     (int)   results per API call   [default: 10]
    llm_temperature    (float) model temperature      [default: 0.0]
    llm_timeout        (float) seconds per request    [default: 60.0]
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI, OpenAIError

from core.types import OCRResult
from ocr.stages.base import PostProcessStage

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "qwen2.5:7b-instruct-q4_K_M"
_DEFAULT_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_API_KEY = "ollama"
_DEFAULT_BATCH_SIZE = 10
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_TIMEOUT = 60.0

_SYSTEM_PROMPT = (
    "你是一个中文OCR后处理专家。用户会发给你一个JSON数组，"
    "每个元素是一段从图片中识别出来的中文文字。\n"
    "你的任务：\n"
    "1. 修正OCR误识别导致的字符错误（例如形近字、笔画缺失）。\n"
    "2. 不要改动标点符号（除非标点本身是OCR错误）。\n"
    "3. 不要改写、补充或删除内容，只修正OCR错误。\n"
    "4. 按照原始顺序返回一个JSON数组，元素个数必须与输入完全相同。\n"
    "5. 只输出JSON数组，不要输出任何其他内容。\n"
    "示例输入：[\"他走了\", \"天空是蓝色地\"]\n"
    "示例输出：[\"他走了\", \"天空是蓝色的\"]"
)


class LlmCorrectionStage(PostProcessStage, register_as="llm_correction"):
    """Correct OCR errors in Chinese text using a local Ollama LLM.

    Processes results in batches.  Any batch that fails (API error, parse
    error, wrong length) is returned with original texts preserved.
    Confidence, bbox, and image_id are unchanged.
    """

    @property
    def stage_id(self) -> str:
        """Stage identifier."""
        return "llm_correction"

    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Correct spelling/character errors in each OCRResult's text.

        Args:
            results: Input OCR results.
            config:  Full application config dict.

        Returns:
            Results with corrected text fields; all other fields unchanged.
        """
        if not results:
            return results

        model: str = str(config.get("llm_model", _DEFAULT_MODEL))
        base_url: str = str(config.get("llm_base_url", _DEFAULT_BASE_URL))
        api_key: str = str(config.get("llm_api_key", _DEFAULT_API_KEY))
        batch_size: int = int(config.get("llm_batch_size", _DEFAULT_BATCH_SIZE))
        temperature: float = float(config.get("llm_temperature", _DEFAULT_TEMPERATURE))
        timeout: float = float(config.get("llm_timeout", _DEFAULT_TIMEOUT))

        client = OpenAI(base_url=base_url, api_key=api_key)

        output: list[OCRResult] = []
        for i in range(0, len(results), batch_size):
            batch = results[i : i + batch_size]
            corrected_texts = self._correct_batch(
                client, batch, model, temperature, timeout
            )
            for result, new_text in zip(batch, corrected_texts):
                if new_text != result.text:
                    logger.debug(
                        "LlmCorrectionStage: corrected '%s' → '%s'",
                        result.text, new_text,
                    )
                from dataclasses import replace
                output.append(replace(result, text=new_text))

        return output

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _correct_batch(
        self,
        client: OpenAI,
        batch: list[OCRResult],
        model: str,
        temperature: float,
        timeout: float,
    ) -> list[str]:
        """Send one batch to the LLM and return corrected texts.

        On any error (API, JSON parse, length mismatch) returns the
        original texts unchanged.

        Args:
            client:      Configured OpenAI client.
            batch:       OCRResult batch to correct.
            model:       Ollama model tag.
            temperature: Sampling temperature.
            timeout:     Request timeout in seconds.

        Returns:
            List of corrected text strings, same length as *batch*.
        """
        texts = [r.text for r in batch]
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
            )
        except OpenAIError as exc:
            logger.warning(
                "LlmCorrectionStage: API error for batch of %d: %s — "
                "keeping originals.",
                len(batch), exc,
            )
            return texts
        except Exception as exc:
            logger.warning(
                "LlmCorrectionStage: unexpected error for batch of %d: %s — "
                "keeping originals.",
                len(batch), exc,
            )
            return texts

        raw = response.choices[0].message.content or ""
        return self._parse_response(raw, texts)

    @staticmethod
    def _parse_response(raw: str, originals: list[str]) -> list[str]:
        """Parse the LLM JSON response into a list of corrected strings.

        Falls back to *originals* on any parse error or length mismatch.

        Args:
            raw:       Raw LLM response string.
            originals: Original texts to fall back to.

        Returns:
            List of corrected texts, same length as *originals*.
        """
        raw = raw.strip()
        # Strip markdown code fences if the model wrapped the JSON
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                line for line in lines
                if not line.startswith("```")
            ).strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                "LlmCorrectionStage: JSON parse error (%s) — keeping originals.",
                exc,
            )
            return originals

        if not isinstance(parsed, list):
            logger.warning(
                "LlmCorrectionStage: response is not a list (%s) — keeping originals.",
                type(parsed).__name__,
            )
            return originals

        if len(parsed) != len(originals):
            logger.warning(
                "LlmCorrectionStage: response length %d != expected %d — "
                "keeping originals.",
                len(parsed), len(originals),
            )
            return originals

        return [str(t) for t in parsed]
