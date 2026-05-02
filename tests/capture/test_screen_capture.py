"""Tests for ScreenCapture — rotation logic (headless, no real screen needed)."""

from __future__ import annotations

import numpy as np
import pytest

from capture.screen_capture import CaptureRegion, ScreenCapture


# ---------------------------------------------------------------------------
# CaptureRegion
# ---------------------------------------------------------------------------

class TestCaptureRegion:
    def test_to_mss_monitor(self) -> None:
        r = CaptureRegion(x=10, y=20, width=300, height=400)
        m = r.to_mss_monitor()
        assert m == {"top": 20, "left": 10, "width": 300, "height": 400}

    def test_frozen(self) -> None:
        r = CaptureRegion(x=0, y=0, width=100, height=100)
        with pytest.raises(Exception):
            r.x = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# apply_rotation — pure numpy/cv2, no display needed
# ---------------------------------------------------------------------------

def _solid_image(h: int, w: int, colour: tuple[int, int, int] = (128, 64, 32)) -> np.ndarray:
    """Return a solid-colour HxWx3 uint8 BGR image."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = colour
    return img


def _landscape() -> np.ndarray:
    """Wide image (800x200) — aspect ratio heuristic should rotate 90CW."""
    return _solid_image(200, 800)


def _portrait() -> np.ndarray:
    """Tall image (800x200) — aspect ratio heuristic should NOT rotate."""
    return _solid_image(800, 200)


def _square() -> np.ndarray:
    """Near-square image (400x400) — falls through to Hough path."""
    return _solid_image(400, 400)


class TestApplyRotationNone:
    def test_none_returns_identical_array(self) -> None:
        img = _landscape()
        result = ScreenCapture.apply_rotation(img, "none")
        assert result is img  # same object, no copy

    def test_none_case_insensitive(self) -> None:
        img = _landscape()
        result = ScreenCapture.apply_rotation(img, "NONE")
        assert result is img


class TestApplyRotationFixed:
    def test_90cw_swaps_dimensions(self) -> None:
        img = _landscape()  # 200 tall, 800 wide
        result = ScreenCapture.apply_rotation(img, "90cw")
        assert result.shape == (800, 200, 3)

    def test_90ccw_swaps_dimensions(self) -> None:
        img = _landscape()
        result = ScreenCapture.apply_rotation(img, "90ccw")
        assert result.shape == (800, 200, 3)

    def test_180_preserves_dimensions(self) -> None:
        img = _landscape()
        result = ScreenCapture.apply_rotation(img, "180")
        assert result.shape == img.shape

    def test_180_flips_content(self) -> None:
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        img[0, 0] = (255, 0, 0)
        result = ScreenCapture.apply_rotation(img, "180")
        assert tuple(result[3, 3]) == (255, 0, 0)

    def test_unknown_mode_returns_unchanged(self) -> None:
        img = _landscape()
        result = ScreenCapture.apply_rotation(img, "unknown_mode")
        assert result is img


class TestAutoRotate:
    def test_landscape_gets_rotated_90cw(self) -> None:
        """Width > Height * 1.3: should rotate 90CW → portrait shape."""
        img = _landscape()  # 200h x 800w
        result = ScreenCapture.apply_rotation(img, "auto")
        h, w = result.shape[:2]
        assert h > w, f"Expected portrait after auto-rotate, got {h}x{w}"

    def test_portrait_not_rotated(self) -> None:
        """Height > Width * 1.3: should remain portrait."""
        img = _portrait()  # 800h x 200w
        result = ScreenCapture.apply_rotation(img, "auto")
        h, w = result.shape[:2]
        assert h > w, f"Expected portrait shape to be preserved, got {h}x{w}"
        assert result.shape == img.shape

    def test_auto_square_returns_array(self) -> None:
        """Near-square falls to Hough path; must return a valid array."""
        img = _square()
        result = ScreenCapture.apply_rotation(img, "auto")
        assert isinstance(result, np.ndarray)
        assert result.ndim == 3


class TestDetectRotationAngle:
    def test_returns_float(self) -> None:
        img = _solid_image(200, 200)
        angle = ScreenCapture._detect_rotation_angle(img)
        assert isinstance(angle, float)

    def test_solid_image_returns_zero(self) -> None:
        """No edges → no lines → angle 0.0."""
        img = _solid_image(200, 200)
        angle = ScreenCapture._detect_rotation_angle(img)
        assert angle == 0.0


class TestApplyAngle:
    def test_zero_returns_same_object(self) -> None:
        img = _square()
        result = ScreenCapture._apply_angle(img, 0.0)
        assert result is img

    def test_90_swaps_dims(self) -> None:
        img = _solid_image(100, 200)  # HxW
        result = ScreenCapture._apply_angle(img, 90.0)
        assert result.shape[:2] == (200, 100)

    def test_minus_90_swaps_dims(self) -> None:
        img = _solid_image(100, 200)
        result = ScreenCapture._apply_angle(img, -90.0)
        assert result.shape[:2] == (200, 100)

    def test_180_preserves_dims(self) -> None:
        img = _solid_image(100, 200)
        result = ScreenCapture._apply_angle(img, 180.0)
        assert result.shape == img.shape

    def test_arbitrary_angle_returns_array(self) -> None:
        img = _square()
        result = ScreenCapture._apply_angle(img, 45.0)
        assert isinstance(result, np.ndarray)
        assert result.ndim == 3


# ---------------------------------------------------------------------------
# grab() — mss injection for headless testing
# ---------------------------------------------------------------------------

class FakeMssScreenShot:
    """Minimal stand-in for mss.ScreenShot with BGRA pixel data."""

    def __init__(self, h: int, w: int) -> None:
        self._arr = np.zeros((h, w, 4), dtype=np.uint8)
        self._arr[:, :, 0] = 100  # B
        self._arr[:, :, 1] = 150  # G
        self._arr[:, :, 2] = 200  # R
        self._arr[:, :, 3] = 255  # A

    def __array__(self, dtype=None, copy=None) -> np.ndarray:
        if dtype is not None:
            return self._arr.astype(dtype)
        return self._arr


class FakeMss:
    """Minimal stand-in for mss.mss() that returns a fixed BGRA image."""

    def __init__(self, h: int = 100, w: int = 200) -> None:
        self._h = h
        self._w = w

    def grab(self, monitor: dict) -> FakeMssScreenShot:
        return FakeMssScreenShot(self._h, self._w)


class TestGrab:
    def test_grab_returns_bgr_array(self) -> None:
        fake_mss = FakeMss(h=100, w=200)
        sc = ScreenCapture(mss_instance=fake_mss)
        region = CaptureRegion(x=0, y=0, width=200, height=100)
        result = sc.grab(region)
        assert isinstance(result, np.ndarray)
        assert result.ndim == 3
        assert result.shape[2] == 3  # BGR, no alpha

    def test_grab_correct_dimensions(self) -> None:
        fake_mss = FakeMss(h=100, w=200)
        sc = ScreenCapture(mss_instance=fake_mss)
        region = CaptureRegion(x=0, y=0, width=200, height=100)
        result = sc.grab(region)
        assert result.shape == (100, 200, 3)

    def test_grab_and_rotate_none(self) -> None:
        fake_mss = FakeMss(h=100, w=200)
        sc = ScreenCapture(mss_instance=fake_mss)
        region = CaptureRegion(x=0, y=0, width=200, height=100)
        result = sc.grab_and_rotate(region, "none")
        assert result.shape == (100, 200, 3)

    def test_grab_and_rotate_90cw(self) -> None:
        fake_mss = FakeMss(h=100, w=200)
        sc = ScreenCapture(mss_instance=fake_mss)
        region = CaptureRegion(x=0, y=0, width=200, height=100)
        result = sc.grab_and_rotate(region, "90cw")
        assert result.shape == (200, 100, 3)
