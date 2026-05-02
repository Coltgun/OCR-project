"""
PostProcessStage ABC — base class for all OCR post-processing stages.

Register a new stage:
    class MyStage(PostProcessStage, register_as="my_stage"):
        ...

Pipeline modes are defined in ocr/pipeline.py as ordered name lists.
Adding a new stage = create a new file + add the name to the relevant modes.
No changes to existing code required.
"""

from __future__ import annotations

from abc import abstractmethod

from core.registry import Registrable
from core.types import OCRResult


class PostProcessStage(Registrable):
    """Abstract base for pipeline post-processing stages.

    Each stage receives a list of OCRResult objects, transforms them
    (correction, deduplication, normalisation, etc.), and returns
    the processed list.

    Stages must be stateless with respect to individual pipeline runs —
    any per-run state should be local to the process() call.
    """

    @abstractmethod
    def process(self, results: list[OCRResult], config: dict) -> list[OCRResult]:
        """Transform *results* and return the processed list.

        Args:
            results: Input OCR results from the previous stage.
            config:  Full application config dict.

        Returns:
            Processed list of OCRResult objects (may be a different length).
        """

    @property
    @abstractmethod
    def stage_id(self) -> str:
        """Human-readable identifier for this stage (e.g. 'cleanup', 'bert_correction')."""
