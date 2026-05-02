"""
Shared data types used across the OCR pipeline.

These dataclasses flow through every stage: from OCREngine output
through PostProcessStages and into OutputFormatters.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BoundingBox:
    """Axis-aligned bounding box in screen/image coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        """Width of the bounding box in pixels."""
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        """Height of the bounding box in pixels."""
        return self.y2 - self.y1


@dataclass
class OCRResult:
    """A single recognised text region from the OCR engine.

    Attributes:
        text:       The recognised text string (may be empty).
        confidence: Per-line confidence score in [0.0, 1.0].
        bbox:       Bounding box in image pixel coordinates, or None if unavailable.
        image_id:   Opaque identifier for the source image (e.g. "0001" or a path stem).
    """

    text: str
    confidence: float
    bbox: BoundingBox | None = None
    image_id: str = ""


@dataclass
class Chapter:
    """An ordered collection of OCR results that form one chapter.

    Attributes:
        number:  Chapter number (1-based). Used for numeric sorting — never sort by str.
        results: OCR results in reading order (image order within the chapter).
        title:   Optional display title; defaults to "第{number}章".
    """

    number: int
    results: list[OCRResult] = field(default_factory=list)
    title: str = ""

    def __post_init__(self) -> None:
        if not self.title:
            self.title = f"第{self.number}章"
