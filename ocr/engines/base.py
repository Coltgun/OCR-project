"""
OCREngine ABC — base class for all OCR engine implementations.

Register a new engine:
    class MyEngine(OCREngine, register_as="myengine"):
        ...

Retrieve at runtime:
    engine_cls = OCREngine.get(config["ocr_engine"])
    engine = engine_cls()
    engine.initialize(config)
    results = engine.recognize(image_array)
    engine.unload()
"""

from __future__ import annotations

from abc import abstractmethod

import numpy as np

from core.registry import Registrable
from core.types import OCRResult


class OCREngine(Registrable):
    """Abstract base for OCR engine implementations.

    Lifecycle contract:
        1. initialize(config) — load models into memory/VRAM.
        2. recognize(image)   — run inference; may be called many times.
        3. unload()           — release all VRAM/memory resources.

    Every implementation MUST call vram_manager.allocate() inside initialize()
    and vram_manager.release() inside unload().
    """

    @abstractmethod
    def initialize(self, config: dict) -> None:
        """Load models and allocate VRAM.

        Args:
            config: Full application config dict.
        """

    @abstractmethod
    def recognize(self, image: np.ndarray) -> list[OCRResult]:
        """Run OCR on a single image array (HxWxC, BGR or RGB uint8).

        Args:
            image: NumPy image array.

        Returns:
            List of OCRResult objects in detection order.
        """

    @abstractmethod
    def unload(self) -> None:
        """Release all models and free VRAM.

        Must call vram_manager.release(self.registry_name).
        """

    @property
    @abstractmethod
    def vram_mb(self) -> int:
        """Approximate VRAM footprint in MB when the model is loaded."""
