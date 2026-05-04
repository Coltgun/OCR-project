"""
OpenRouterCorrectionStage — OCR error correction via the OpenRouter API.

Registration key: "openrouter_correction"

Uses the same JSON-batch correction protocol as LlmCorrectionStage but
targets the OpenRouter API endpoint.  OpenRouter requires an API key and
recommends passing HTTP-Referer and X-Title headers for usage tracking.

No subprocess isolation required (openai library, no torch).

Config keys consumed:
    openrouter_model        (str)   Model slug               [default: qwen/qwen-2.5-7b-instruct]
    openrouter_api_key      (str)   OpenRouter API key       [default: ""]
    openrouter_base_url     (str)   API base URL             [default: https://openrouter.ai/api/v1]
    openrouter_batch_size   (int)   Results per API call     [default: 10]
    openrouter_temperature  (float) Model temperature        [default: 0.0]
    openrouter_timeout      (float) Seconds per request      [default: 60.0]
    openrouter_site_url     (str)   HTTP-Referer header      [default: https://github.com/Coltgun/OCR-project]
    openrouter_site_name    (str)   X-Title header           [default: Chinese OCR App]
"""

from __future__ import annotations

from openai import OpenAI

from ocr.stages.llm_correction_base import LlmCorrectionBase

_DEFAULT_MODEL = "qwen/qwen-2.5-7b-instruct"
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_BATCH_SIZE = 10
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_TIMEOUT = 60.0
_DEFAULT_SITE_URL = "https://github.com/Coltgun/OCR-project"
_DEFAULT_SITE_NAME = "Chinese OCR App"


class OpenRouterCorrectionStage(LlmCorrectionBase, register_as="openrouter_correction"):
    """Correct OCR errors in Chinese text via the OpenRouter API.

    Processes results in batches.  Any batch that fails (API error, parse
    error, wrong length) is returned with original texts preserved.
    Confidence, bbox, and image_id are unchanged.

    The OpenRouter API key must be set in config["openrouter_api_key"] or
    the OPENROUTER_API_KEY environment variable — never hardcoded.
    """

    @property
    def stage_id(self) -> str:
        """Stage identifier."""
        return "openrouter_correction"

    def _make_client(self, config: dict) -> OpenAI:
        """Return an OpenAI client pointed at OpenRouter."""
        import os
        api_key = str(
            config.get("openrouter_api_key")
            or os.environ.get("OPENROUTER_API_KEY", "")
        )
        base_url = str(config.get("openrouter_base_url") or _DEFAULT_BASE_URL)
        return OpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    def _read_config(self, config: dict) -> tuple[str, float, float, int]:
        """Return (model, temperature, timeout, batch_size) from config."""
        return (
            str(config.get("openrouter_model") or _DEFAULT_MODEL),
            float(config.get("openrouter_temperature", _DEFAULT_TEMPERATURE)),
            float(config.get("openrouter_timeout", _DEFAULT_TIMEOUT)),
            int(config.get("openrouter_batch_size", _DEFAULT_BATCH_SIZE)),
        )

    def _extra_create_kwargs(self, config: dict) -> dict:
        """Return extra_headers for OpenRouter usage tracking."""
        site_url = str(config.get("openrouter_site_url", _DEFAULT_SITE_URL))
        site_name = str(config.get("openrouter_site_name", _DEFAULT_SITE_NAME))
        return {
            "extra_headers": {
                "HTTP-Referer": site_url,
                "X-Title": site_name,
            }
        }
