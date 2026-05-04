"""Post-processing pipeline stage implementations."""

from ocr.stages import (  # noqa: F401 — imports trigger register_as self-registration
    cleanup,
    rule_corrections,
    minhash_dedup,
    bert_correction,
    llm_correction,
    hybrid_correction,
    embedding_dedup,
    openrouter_correction,
    openrouter_dedup,
)
