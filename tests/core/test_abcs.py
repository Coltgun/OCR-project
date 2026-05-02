"""Tests for ARCH-002: all ABCs and shared data types.

Verifies:
- ABCs cannot be instantiated directly (TypeError)
- Concrete subclasses with all methods implemented can be instantiated
- register_as= correctly registers each ABC subclass
- Shared data types (OCRResult, Chapter, BoundingBox) behave correctly
"""

from __future__ import annotations

import numpy as np
import pytest

from core.types import BoundingBox, Chapter, OCRResult


# ---------------------------------------------------------------------------
# Shared data types
# ---------------------------------------------------------------------------

class TestBoundingBox:
    def test_width_and_height(self) -> None:
        bb = BoundingBox(x1=10, y1=20, x2=110, y2=70)
        assert bb.width == 100
        assert bb.height == 50

    def test_zero_size(self) -> None:
        bb = BoundingBox(0, 0, 0, 0)
        assert bb.width == 0
        assert bb.height == 0


class TestOCRResult:
    def test_defaults(self) -> None:
        r = OCRResult(text="你好", confidence=0.95)
        assert r.bbox is None
        assert r.image_id == ""

    def test_with_bbox(self) -> None:
        bb = BoundingBox(0, 0, 100, 30)
        r = OCRResult(text="测试", confidence=0.8, bbox=bb, image_id="0001")
        assert r.bbox is bb
        assert r.image_id == "0001"


class TestChapter:
    def test_default_title_generated(self) -> None:
        ch = Chapter(number=3)
        assert ch.title == "第3章"

    def test_custom_title_preserved(self) -> None:
        ch = Chapter(number=1, title="序章")
        assert ch.title == "序章"

    def test_results_default_empty(self) -> None:
        ch = Chapter(number=1)
        assert ch.results == []

    def test_results_not_shared_between_instances(self) -> None:
        ch1 = Chapter(number=1)
        ch2 = Chapter(number=2)
        ch1.results.append(OCRResult("a", 0.9))
        assert ch2.results == []


# ---------------------------------------------------------------------------
# OCREngine ABC
# ---------------------------------------------------------------------------

class TestOCREngineABC:
    def test_cannot_instantiate_base_directly(self) -> None:
        from ocr.engines.base import OCREngine
        with pytest.raises(TypeError):
            OCREngine()  # type: ignore[abstract]

    def test_concrete_subclass_registers_and_instantiates(self) -> None:
        from ocr.engines.base import OCREngine

        class _TestEngine(OCREngine, register_as="_test_ocr_engine"):
            def initialize(self, config: dict) -> None:
                pass

            def recognize(self, image: np.ndarray) -> list:
                return []

            def unload(self) -> None:
                pass

            @property
            def vram_mb(self) -> int:
                return 500

        cls = OCREngine.get("_test_ocr_engine")
        engine = cls()
        assert engine.vram_mb == 500
        assert engine.recognize(np.zeros((10, 10, 3), dtype=np.uint8)) == []

    def test_incomplete_subclass_cannot_instantiate(self) -> None:
        from ocr.engines.base import OCREngine

        class _Incomplete(OCREngine, register_as="_incomplete_ocr"):
            def initialize(self, config: dict) -> None:
                pass
            # Missing recognize, unload, vram_mb

        with pytest.raises(TypeError):
            _Incomplete()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# PostProcessStage ABC
# ---------------------------------------------------------------------------

class TestPostProcessStageABC:
    def test_cannot_instantiate_base_directly(self) -> None:
        from ocr.stages.base import PostProcessStage
        with pytest.raises(TypeError):
            PostProcessStage()  # type: ignore[abstract]

    def test_concrete_subclass_registers_and_works(self) -> None:
        from ocr.stages.base import PostProcessStage

        class _PassThrough(PostProcessStage, register_as="_test_passthrough"):
            def process(self, results: list, config: dict) -> list:
                return results

            @property
            def stage_id(self) -> str:
                return "passthrough"

        cls = PostProcessStage.get("_test_passthrough")
        stage = cls()
        sample = [OCRResult("text", 0.9)]
        assert stage.process(sample, {}) == sample
        assert stage.stage_id == "passthrough"


# ---------------------------------------------------------------------------
# OutputFormatter ABC
# ---------------------------------------------------------------------------

class TestOutputFormatterABC:
    def test_cannot_instantiate_base_directly(self) -> None:
        from output.base import OutputFormatter
        with pytest.raises(TypeError):
            OutputFormatter()  # type: ignore[abstract]

    def test_concrete_subclass_registers_and_works(self) -> None:
        from output.base import OutputFormatter

        class _DummyFormatter(OutputFormatter, register_as="_test_formatter"):
            def format(self, chapters: list, config: dict) -> bytes:
                return b"output"

            def file_extension(self) -> str:
                return "txt"

        cls = OutputFormatter.get("_test_formatter")
        fmt = cls()
        assert fmt.format([], {}) == b"output"
        assert fmt.file_extension() == "txt"


# ---------------------------------------------------------------------------
# InputSource ABC
# ---------------------------------------------------------------------------

class TestInputSourceABC:
    def test_cannot_instantiate_base_directly(self) -> None:
        from input.base import InputSource
        with pytest.raises(TypeError):
            InputSource()  # type: ignore[abstract]

    def test_concrete_subclass_registers_and_yields(self) -> None:
        from input.base import InputSource

        class _DummySource(InputSource, register_as="_test_source"):
            def acquire(self, config: dict):
                yield ("0001", np.zeros((10, 10, 3), dtype=np.uint8))

        cls = InputSource.get("_test_source")
        source = cls()
        results = list(source.acquire({}))
        assert len(results) == 1
        image_id, arr = results[0]
        assert image_id == "0001"
        assert arr.shape == (10, 10, 3)


# ---------------------------------------------------------------------------
# LLMProvider ABC
# ---------------------------------------------------------------------------

class TestLLMProviderABC:
    def test_cannot_instantiate_base_directly(self) -> None:
        from llm.base import LLMProvider
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_concrete_subclass_registers_and_works(self) -> None:
        from llm.base import LLMProvider

        class _EchoProvider(LLMProvider, register_as="_test_llm"):
            def complete(self, messages: list[dict], config: dict) -> str:
                return messages[-1]["content"]

            def is_available(self) -> bool:
                return True

        cls = LLMProvider.get("_test_llm")
        provider = cls()
        assert provider.is_available() is True
        result = provider.complete([{"role": "user", "content": "ping"}], {})
        assert result == "ping"
