"""
PaddleOCREngine — OCREngine implementation using PaddleOCR (PP-OCRv5).

Registration key: "paddleocr"

Usage (via registry):
    from ocr.engines.base import OCREngine
    engine = OCREngine.get("paddleocr")()
    engine.initialize(config)
    results = engine.recognize(image_bgr)
    engine.unload()

IMPORTANT — process isolation:
    PaddleOCR (paddle) and PyTorch-based models (MacBERT, BGE-M3) bundle
    incompatible cuDNN DLL builds on Windows. They MUST NOT be imported in the
    same process. When running LOCAL_STANDARD or HYBRID_TIERED pipeline modes,
    use ocr/worker.py to run PaddleOCR in a subprocess.

API notes for PaddleOCR >= 3.3 (PP-OCRv5):
    - use_gpu        → device="gpu" or device="cpu"
    - use_angle_cls  → use_textline_orientation=True/False
    - show_log removed; suppress via logging level instead
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from core.types import BoundingBox, OCRResult
from core.vram_manager import vram_manager
from ocr.engines.base import OCREngine
from utils.cuda_utils import register_nvidia_dll_dirs

logger = logging.getLogger(__name__)

_VRAM_MB_DEFAULT = 1500
_REGISTRY_NAME = "paddleocr"


class PaddleOCREngine(OCREngine, register_as=_REGISTRY_NAME):
    """PaddleOCR-backed OCR engine for Simplified Chinese text.

    VRAM footprint: ~1500 MB (configurable via config["paddleocr_vram_mb"]).

    Config keys consumed:
        vram_tier           (str)  "8gb" / "16gb"  — selects default vram_mb
        paddleocr_vram_mb   (int)  override VRAM footprint estimate
        paddleocr_use_gpu   (bool) default True
        paddleocr_lang      (str)  default "ch"
        paddleocr_orientation (bool) default True — use_textline_orientation
    """

    def __init__(self) -> None:
        self._engine: Any | None = None
        self._vram_mb: int = _VRAM_MB_DEFAULT

    # ------------------------------------------------------------------
    # OCREngine ABC implementation
    # ------------------------------------------------------------------

    @property
    def vram_mb(self) -> int:
        """Approximate VRAM footprint in MB when the model is loaded."""
        return self._vram_mb

    def initialize(self, config: dict) -> None:
        """Load PaddleOCR model and allocate VRAM budget.

        Args:
            config: Full application config dict.

        Raises:
            RuntimeError: If there is not enough VRAM budget available.
        """
        if self._engine is not None:
            logger.debug("PaddleOCREngine: already initialised, skipping.")
            return

        self._vram_mb = int(config.get("paddleocr_vram_mb", _VRAM_MB_DEFAULT))

        if not vram_manager.allocate(_REGISTRY_NAME, self._vram_mb):
            raise RuntimeError(
                f"PaddleOCREngine: insufficient VRAM — need {self._vram_mb} MB, "
                f"available {vram_manager.available_mb} MB. "
                "Call unload() on other models first."
            )

        use_gpu: bool = bool(config.get("paddleocr_use_gpu", True))
        lang: str = str(config.get("paddleocr_lang", "ch"))
        use_orientation: bool = bool(config.get("paddleocr_orientation", True))
        device: str = "gpu" if use_gpu else "cpu"

        logger.info(
            "PaddleOCREngine: initialising (device=%s, lang=%s, orientation=%s).",
            device, lang, use_orientation,
        )

        register_nvidia_dll_dirs()

        from paddleocr import PaddleOCR  # noqa: PLC0415
        self._engine = PaddleOCR(
            use_textline_orientation=use_orientation,
            lang=lang,
            device=device,
        )
        logger.info("PaddleOCREngine: ready.")

    def recognize(self, image: np.ndarray) -> list[OCRResult]:
        """Run OCR on a single BGR image array.

        Args:
            image: HxWx3 uint8 numpy array (BGR or RGB — PaddleOCR handles both).

        Returns:
            List of OCRResult objects, one per detected text line, in detection order.

        Raises:
            RuntimeError: If initialize() has not been called.
        """
        if self._engine is None:
            raise RuntimeError(
                "PaddleOCREngine.recognize() called before initialize(). "
                "Call initialize(config) first."
            )

        raw = self._engine.ocr(image, cls=True)
        return self._parse_results(raw)

    def unload(self) -> None:
        """Release PaddleOCR model and free VRAM budget."""
        if self._engine is None:
            logger.debug("PaddleOCREngine.unload(): already unloaded.")
            return

        self._engine = None
        vram_manager.release(_REGISTRY_NAME)

        try:
            import paddle  # noqa: PLC0415
            paddle.device.cuda.empty_cache()
            logger.info("PaddleOCREngine: unloaded and CUDA cache cleared.")
        except Exception as exc:
            logger.warning(
                "PaddleOCREngine: could not clear CUDA cache: %s", exc
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_results(raw: Any) -> list[OCRResult]:
        """Convert PaddleOCR raw output to a list of OCRResult objects.

        PaddleOCR >= 3.x returns a list of pages; each page is a list of
        line results. Each line result is:
            [polygon_points, (text, confidence)]

        Where polygon_points is a list of 4 [x, y] pairs (quadrilateral).
        We convert the quad to an axis-aligned BoundingBox.

        Args:
            raw: Raw return value from PaddleOCR.ocr().

        Returns:
            Flat list of OCRResult objects.
        """
        results: list[OCRResult] = []

        if raw is None:
            return results

        for page in raw:
            if page is None:
                continue
            for line in page:
                if line is None:
                    continue
                try:
                    points, (text, conf) = line
                    bbox = PaddleOCREngine._quad_to_bbox(points)
                    results.append(
                        OCRResult(
                            text=str(text),
                            confidence=float(conf),
                            bbox=bbox,
                        )
                    )
                except (ValueError, TypeError, IndexError) as exc:
                    logger.warning(
                        "PaddleOCREngine: skipping malformed result line: %s — %s",
                        line, exc,
                    )

        return results

    @staticmethod
    def _quad_to_bbox(points: list) -> BoundingBox:
        """Convert a quadrilateral (4 corner points) to an axis-aligned BoundingBox.

        Args:
            points: List of 4 [x, y] coordinate pairs.

        Returns:
            Axis-aligned BoundingBox enclosing all four points.
        """
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        return BoundingBox(
            x1=int(min(xs)),
            y1=int(min(ys)),
            x2=int(max(xs)),
            y2=int(max(ys)),
        )
