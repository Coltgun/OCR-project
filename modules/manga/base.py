"""
MangaProcessor ABC — stub for future speech-bubble detection and panel ordering.

Do NOT implement this class until the manga module is formally scoped.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field

import numpy as np

from core.registry import Registrable


@dataclass
class Panel:
    """A single manga panel region within a page image."""

    bbox_x1: int
    bbox_y1: int
    bbox_x2: int
    bbox_y2: int
    reading_order: int = 0


@dataclass
class TextBubble:
    """A speech bubble or caption region within a panel."""

    bbox_x1: int
    bbox_y1: int
    bbox_x2: int
    bbox_y2: int
    text: str = ""
    bubbles: list["TextBubble"] = field(default_factory=list)


class MangaProcessor(Registrable):
    """Abstract base for manga processing implementations (future feature)."""

    @abstractmethod
    def detect_panels(self, image: np.ndarray) -> list[Panel]:
        """Detect and return manga panels in *image*."""

    @abstractmethod
    def detect_bubbles(self, panel: Panel) -> list[TextBubble]:
        """Detect speech bubbles and captions within *panel*."""

    @abstractmethod
    def order_reading_sequence(self, panels: list[Panel]) -> list[Panel]:
        """Return *panels* in manga reading order (right-to-left, top-to-bottom)."""
