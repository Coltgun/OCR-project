"""
LlmCorrectionStage — OCR error correction via a local Ollama LLM.

Registration key: "llm_correction"

No subprocess isolation required: the openai library has no torch dependency,
so this stage runs directly in the main process without DLL conflicts.

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

from openai import OpenAI

from llm.clients import get_openai_client
from ocr.stages.llm_correction_base import LlmCorrectionBase

_DEFAULT_MODEL = "qwen2.5:7b-instruct-q4_K_M"
_DEFAULT_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_API_KEY = "ollama"
_DEFAULT_BATCH_SIZE = 10
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_TIMEOUT = 60.0


class LlmCorrectionStage(LlmCorrectionBase, register_as="llm_correction"):
    """Correct OCR errors in Chinese text using a local Ollama LLM.

    Processes results in batches.  Any batch that fails (API error, parse
    error, wrong length) is returned with original texts preserved.
    Confidence, bbox, and image_id are unchanged.
    """

    @property
    def stage_id(self) -> str:
        """Stage identifier."""
        return "llm_correction"

    def _make_client(self, config: dict) -> OpenAI:
        """Return a cached OpenAI client pointed at the local Ollama server."""
        timeout = float(config.get("llm_timeout", _DEFAULT_TIMEOUT))
        return get_openai_client(
            base_url=str(config.get("llm_base_url") or _DEFAULT_BASE_URL),
            api_key=str(config.get("llm_api_key") or _DEFAULT_API_KEY),
            timeout=timeout,
        )

    def _read_config(self, config: dict) -> tuple[str, float, float, int]:
        """Return (model, temperature, timeout, batch_size) from config."""
        return (
            str(config.get("llm_model") or _DEFAULT_MODEL),
            float(config.get("llm_temperature", _DEFAULT_TEMPERATURE)),
            float(config.get("llm_timeout", _DEFAULT_TIMEOUT)),
            int(config.get("llm_batch_size", _DEFAULT_BATCH_SIZE)),
        )
