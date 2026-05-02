"""
Tests for PaddleOCREngine.

PaddleOCR and paddle are NOT imported here — all tests mock them out.
This keeps the test suite runnable in the main process (no cuDNN DLL conflict).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from core.types import BoundingBox, OCRResult
from core.vram_manager import VRAMManager
from ocr.engines.base import OCREngine
from ocr.engines.paddle_engine import PaddleOCREngine, _REGISTRY_NAME, _VRAM_MB_DEFAULT


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fresh_vram() -> VRAMManager:
    """Return a VRAMManager with 8 GB budget and no allocations."""
    return VRAMManager(total_mb=7680)


@pytest.fixture()
def engine() -> PaddleOCREngine:
    return PaddleOCREngine()


@pytest.fixture()
def min_config() -> dict:
    """Minimal config that selects CPU to avoid needing a GPU in tests."""
    return {"paddleocr_use_gpu": False, "paddleocr_lang": "ch", "paddleocr_orientation": False}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_under_paddleocr(self) -> None:
        cls = OCREngine.get("paddleocr")
        assert cls is PaddleOCREngine

    def test_registry_name_constant(self) -> None:
        assert _REGISTRY_NAME == "paddleocr"

    def test_is_subclass_of_ocr_engine(self) -> None:
        assert issubclass(PaddleOCREngine, OCREngine)


# ---------------------------------------------------------------------------
# vram_mb property
# ---------------------------------------------------------------------------

class TestVramMb:
    def test_default_vram_mb(self, engine: PaddleOCREngine) -> None:
        assert engine.vram_mb == _VRAM_MB_DEFAULT

    def test_vram_mb_type_is_int(self, engine: PaddleOCREngine) -> None:
        assert isinstance(engine.vram_mb, int)


# ---------------------------------------------------------------------------
# initialize()
# ---------------------------------------------------------------------------

class TestInitialize:
    def _make_mock_paddle_ocr(self):
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        return mock_cls, mock_instance

    def test_initialize_allocates_vram(
        self, engine: PaddleOCREngine, min_config: dict, fresh_vram: VRAMManager
    ) -> None:
        mock_cls, _ = self._make_mock_paddle_ocr()
        with (
            patch("ocr.engines.paddle_engine.vram_manager", fresh_vram),
            patch("ocr.engines.paddle_engine.register_nvidia_dll_dirs"),
            patch("builtins.__import__", side_effect=_selective_import(mock_cls)),
        ):
            engine.initialize(min_config)

        assert _REGISTRY_NAME in fresh_vram._allocated
        assert fresh_vram._allocated[_REGISTRY_NAME] == _VRAM_MB_DEFAULT

    def test_initialize_respects_custom_vram_mb(
        self, engine: PaddleOCREngine, fresh_vram: VRAMManager
    ) -> None:
        config = {"paddleocr_use_gpu": False, "paddleocr_vram_mb": 2000}
        mock_cls, _ = self._make_mock_paddle_ocr()
        with (
            patch("ocr.engines.paddle_engine.vram_manager", fresh_vram),
            patch("ocr.engines.paddle_engine.register_nvidia_dll_dirs"),
            patch("builtins.__import__", side_effect=_selective_import(mock_cls)),
        ):
            engine.initialize(config)

        assert fresh_vram._allocated[_REGISTRY_NAME] == 2000

    def test_initialize_raises_when_vram_insufficient(
        self, engine: PaddleOCREngine, min_config: dict
    ) -> None:
        tiny_vram = VRAMManager(total_mb=100)
        with (
            patch("ocr.engines.paddle_engine.vram_manager", tiny_vram),
            patch("ocr.engines.paddle_engine.register_nvidia_dll_dirs"),
        ):
            with pytest.raises(RuntimeError, match="insufficient VRAM"):
                engine.initialize(min_config)

    def test_initialize_twice_is_noop(
        self, engine: PaddleOCREngine, min_config: dict, fresh_vram: VRAMManager
    ) -> None:
        mock_cls, _ = self._make_mock_paddle_ocr()
        with (
            patch("ocr.engines.paddle_engine.vram_manager", fresh_vram),
            patch("ocr.engines.paddle_engine.register_nvidia_dll_dirs"),
            patch("builtins.__import__", side_effect=_selective_import(mock_cls)),
        ):
            engine.initialize(min_config)
            engine.initialize(min_config)  # second call should be silent no-op

        assert mock_cls.call_count == 1


# ---------------------------------------------------------------------------
# unload()
# ---------------------------------------------------------------------------

class TestUnload:
    def test_unload_releases_vram(
        self, engine: PaddleOCREngine, min_config: dict, fresh_vram: VRAMManager
    ) -> None:
        mock_cls = MagicMock()
        mock_paddle = MagicMock()
        with (
            patch("ocr.engines.paddle_engine.vram_manager", fresh_vram),
            patch("ocr.engines.paddle_engine.register_nvidia_dll_dirs"),
            patch("builtins.__import__", side_effect=_selective_import(mock_cls, mock_paddle)),
        ):
            engine.initialize(min_config)
            assert _REGISTRY_NAME in fresh_vram._allocated
            engine.unload()

        assert _REGISTRY_NAME not in fresh_vram._allocated

    def test_unload_clears_engine_instance(
        self, engine: PaddleOCREngine, min_config: dict, fresh_vram: VRAMManager
    ) -> None:
        mock_cls = MagicMock()
        with (
            patch("ocr.engines.paddle_engine.vram_manager", fresh_vram),
            patch("ocr.engines.paddle_engine.register_nvidia_dll_dirs"),
            patch("builtins.__import__", side_effect=_selective_import(mock_cls)),
        ):
            engine.initialize(min_config)
            engine.unload()

        assert engine._engine is None

    def test_unload_before_initialize_is_safe(
        self, engine: PaddleOCREngine, fresh_vram: VRAMManager
    ) -> None:
        with patch("ocr.engines.paddle_engine.vram_manager", fresh_vram):
            engine.unload()  # must not raise


# ---------------------------------------------------------------------------
# recognize() — without calling real PaddleOCR
# ---------------------------------------------------------------------------

class TestRecognize:
    def test_recognize_before_init_raises(self, engine: PaddleOCREngine) -> None:
        import numpy as np
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        with pytest.raises(RuntimeError, match="before initialize"):
            engine.recognize(img)

    def test_recognize_returns_list_of_ocr_results(
        self, engine: PaddleOCREngine, min_config: dict, fresh_vram: VRAMManager
    ) -> None:
        import numpy as np
        img = np.zeros((100, 100, 3), dtype=np.uint8)

        mock_raw = _make_paddle_raw([
            ([[10, 20], [110, 20], [110, 40], [10, 40]], ("测试", 0.95)),
            ([[10, 50], [100, 50], [100, 70], [10, 70]], ("文字", 0.82)),
        ])
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.ocr.return_value = mock_raw
        mock_cls.return_value = mock_instance

        with (
            patch("ocr.engines.paddle_engine.vram_manager", fresh_vram),
            patch("ocr.engines.paddle_engine.register_nvidia_dll_dirs"),
            patch("builtins.__import__", side_effect=_selective_import(mock_cls)),
        ):
            engine.initialize(min_config)
            results = engine.recognize(img)

        assert len(results) == 2
        assert all(isinstance(r, OCRResult) for r in results)
        assert results[0].text == "测试"
        assert abs(results[0].confidence - 0.95) < 1e-6
        assert results[1].text == "文字"

    def test_recognize_empty_raw_returns_empty(
        self, engine: PaddleOCREngine, min_config: dict, fresh_vram: VRAMManager
    ) -> None:
        import numpy as np
        img = np.zeros((50, 50, 3), dtype=np.uint8)

        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.ocr.return_value = [[]]
        mock_cls.return_value = mock_instance

        with (
            patch("ocr.engines.paddle_engine.vram_manager", fresh_vram),
            patch("ocr.engines.paddle_engine.register_nvidia_dll_dirs"),
            patch("builtins.__import__", side_effect=_selective_import(mock_cls)),
        ):
            engine.initialize(min_config)
            results = engine.recognize(img)

        assert results == []

    def test_recognize_none_raw_returns_empty(
        self, engine: PaddleOCREngine, min_config: dict, fresh_vram: VRAMManager
    ) -> None:
        import numpy as np
        img = np.zeros((50, 50, 3), dtype=np.uint8)

        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.ocr.return_value = None
        mock_cls.return_value = mock_instance

        with (
            patch("ocr.engines.paddle_engine.vram_manager", fresh_vram),
            patch("ocr.engines.paddle_engine.register_nvidia_dll_dirs"),
            patch("builtins.__import__", side_effect=_selective_import(mock_cls)),
        ):
            engine.initialize(min_config)
            results = engine.recognize(img)

        assert results == []


# ---------------------------------------------------------------------------
# _parse_results()
# ---------------------------------------------------------------------------

class TestParseResults:
    def test_well_formed_line(self) -> None:
        raw = _make_paddle_raw([
            ([[0, 0], [100, 0], [100, 20], [0, 20]], ("你好", 0.99)),
        ])
        results = PaddleOCREngine._parse_results(raw)
        assert len(results) == 1
        r = results[0]
        assert r.text == "你好"
        assert abs(r.confidence - 0.99) < 1e-6
        assert r.bbox == BoundingBox(x1=0, y1=0, x2=100, y2=20)

    def test_none_raw_returns_empty(self) -> None:
        assert PaddleOCREngine._parse_results(None) == []

    def test_malformed_line_skipped(self) -> None:
        raw = [[None, "garbage_line"]]
        results = PaddleOCREngine._parse_results(raw)
        assert results == []

    def test_multiple_pages(self) -> None:
        page1 = [([[0, 0], [10, 0], [10, 5], [0, 5]], ("A", 0.9))]
        page2 = [([[0, 0], [10, 0], [10, 5], [0, 5]], ("B", 0.8))]
        raw = [page1, page2]
        results = PaddleOCREngine._parse_results(raw)
        assert len(results) == 2
        assert results[0].text == "A"
        assert results[1].text == "B"


# ---------------------------------------------------------------------------
# _quad_to_bbox()
# ---------------------------------------------------------------------------

class TestQuadToBbox:
    def test_axis_aligned_quad(self) -> None:
        points = [[10, 20], [90, 20], [90, 60], [10, 60]]
        bbox = PaddleOCREngine._quad_to_bbox(points)
        assert bbox == BoundingBox(x1=10, y1=20, x2=90, y2=60)

    def test_skewed_quad_uses_extremes(self) -> None:
        points = [[5, 10], [95, 8], [100, 55], [0, 58]]
        bbox = PaddleOCREngine._quad_to_bbox(points)
        assert bbox.x1 == 0
        assert bbox.y1 == 8
        assert bbox.x2 == 100
        assert bbox.y2 == 58


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_paddle_raw(lines: list) -> list:
    """Wrap lines in PaddleOCR's page-list format: [[line, ...]]."""
    return [lines]


def _selective_import(mock_paddle_ocr_cls, mock_paddle_module=None):
    """Return a side_effect function that intercepts paddle/paddleocr imports."""
    import builtins
    real_import = builtins.__import__

    def _import(name, *args, **kwargs):
        if name == "paddleocr":
            mod = MagicMock()
            mod.PaddleOCR = mock_paddle_ocr_cls
            return mod
        if name == "paddle" and mock_paddle_module is not None:
            return mock_paddle_module
        if name == "paddle":
            return MagicMock()
        return real_import(name, *args, **kwargs)

    return _import
