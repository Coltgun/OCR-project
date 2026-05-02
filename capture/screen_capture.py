"""
ScreenCapture — grab a screen region with mss and optionally auto-rotate.

Usage:
    sc = ScreenCapture()
    image_array = sc.grab(region)           # returns HxWx3 BGR numpy array
    rotated = sc.apply_rotation(image, "90cw")

Rotation modes (config["rotation_mode"]):
    "none"   — no rotation (default)
    "90cw"   — rotate 90° clockwise
    "90ccw"  — rotate 90° counter-clockwise
    "180"    — rotate 180°
    "auto"   — aspect ratio heuristic, then Hough line fallback

The mss instance can be injected for testing without a real display.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaptureRegion:
    """Screen region to capture in mss monitor-dict format."""

    x: int
    y: int
    width: int
    height: int

    def to_mss_monitor(self) -> dict[str, int]:
        """Return a dict compatible with mss sct.grab()."""
        return {"top": self.y, "left": self.x, "width": self.width, "height": self.height}


class MssProtocol(Protocol):
    """Minimal protocol for the mss screen-capture object (for test injection)."""

    def grab(self, monitor: dict) -> object:
        """Grab a screen region and return an mss ScreenShot object."""
        ...


class ScreenCapture:
    """Grabs screen regions using mss and applies rotation as configured.

    Args:
        mss_instance: Optional injected mss context manager for testing.
                      If None, a real mss.mss() instance is created on first use.
    """

    def __init__(self, mss_instance: MssProtocol | None = None) -> None:
        self._mss = mss_instance
        self._owns_mss = mss_instance is None

    def grab(self, region: CaptureRegion) -> np.ndarray:
        """Capture *region* from the screen and return a BGR numpy array.

        Args:
            region: Screen region to capture.

        Returns:
            HxWx3 uint8 numpy array in BGR colour order (OpenCV convention).
        """
        import mss as mss_lib  # noqa: PLC0415 — lazy import avoids display requirement at module load

        monitor = region.to_mss_monitor()

        if self._mss is not None:
            sct_img = self._mss.grab(monitor)
        else:
            with mss_lib.mss() as sct:
                sct_img = sct.grab(monitor)

        arr = np.array(sct_img)
        if arr.ndim == 3 and arr.shape[2] == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
        return arr

    def grab_and_rotate(self, region: CaptureRegion, rotation_mode: str) -> np.ndarray:
        """Capture *region* then apply rotation according to *rotation_mode*.

        Args:
            region:        Screen region to capture.
            rotation_mode: One of "none", "90cw", "90ccw", "180", "auto".

        Returns:
            HxWx3 uint8 BGR numpy array after rotation.
        """
        image = self.grab(region)
        return self.apply_rotation(image, rotation_mode)

    @staticmethod
    def apply_rotation(image: np.ndarray, rotation_mode: str) -> np.ndarray:
        """Apply *rotation_mode* to *image* and return the result.

        Args:
            image:         HxWx3 BGR numpy array.
            rotation_mode: "none", "90cw", "90ccw", "180", or "auto".

        Returns:
            Rotated (or unmodified) HxWx3 BGR numpy array.
        """
        mode = rotation_mode.lower().strip()
        if mode == "none":
            return image
        if mode == "90cw":
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        if mode == "90ccw":
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if mode == "180":
            return cv2.rotate(image, cv2.ROTATE_180)
        if mode == "auto":
            return ScreenCapture._auto_rotate(image)
        logger.warning(
            "ScreenCapture: unknown rotation_mode '%s', returning unchanged.", rotation_mode
        )
        return image

    @staticmethod
    def _auto_rotate(image: np.ndarray) -> np.ndarray:
        """Determine and apply rotation automatically.

        Step 1: Aspect ratio heuristic (<5 ms).
        Step 2: Hough line fallback for near-square images (<50 ms target).

        Args:
            image: HxWx3 BGR numpy array.

        Returns:
            Rotated image.
        """
        h, w = image.shape[:2]

        if w > h * 1.3:
            logger.debug("ScreenCapture: auto-rotate: landscape → rotate 90CW.")
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)

        if h > w * 1.3:
            logger.debug("ScreenCapture: auto-rotate: portrait → no rotation.")
            return image

        angle = ScreenCapture._detect_rotation_angle(image)
        logger.debug("ScreenCapture: auto-rotate: Hough angle=%.1f°", angle)
        return ScreenCapture._apply_angle(image, angle)

    @staticmethod
    def _detect_rotation_angle(image: np.ndarray) -> float:
        """Estimate dominant text/line angle using Hough transform.

        Returns the snapped angle closest to 0, ±90, or 180 degrees,
        or 0.0 if no lines are detected.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180,
            threshold=80, minLineLength=50, maxLineGap=10,
        )
        if lines is None or len(lines) == 0:
            return 0.0

        angles: list[float] = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            angles.append(angle)

        median_angle = float(np.median(angles))
        for snap in (-90.0, 0.0, 90.0, 180.0):
            if abs(median_angle - snap) < 15:
                return snap
        return median_angle

    @staticmethod
    def _apply_angle(image: np.ndarray, angle: float) -> np.ndarray:
        """Rotate *image* by *angle* degrees (counter-clockwise positive).

        Uses warpAffine for arbitrary angles; cv2.rotate for exact 90/180.
        """
        if angle == 0.0:
            return image
        if angle == 90.0:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if angle == -90.0:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        if abs(angle) == 180.0:
            return cv2.rotate(image, cv2.ROTATE_180)

        h, w = image.shape[:2]
        center = (w / 2.0, h / 2.0)
        M = cv2.getRotationMatrix2D(center, -angle, 1.0)
        return cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
