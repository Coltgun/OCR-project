"""
InputSource ABC — base class for all input source implementations.

Register a new source:
    class MySource(InputSource, register_as="mysource"):
        ...

Retrieve at runtime:
    source_cls = InputSource.get(config["input_source"])
    source = source_cls()
    for image_id, image_array in source.acquire(config):
        process(image_id, image_array)
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterator

import numpy as np

from core.registry import Registrable


class InputSource(Registrable):
    """Abstract base for input source implementations.

    An InputSource is an iterable that yields (image_id, image_array) tuples.
    The image_id is an opaque string that identifies the image within its
    folder/chapter context (typically the zero-padded filename stem, e.g. '0001').

    Implementations must yield images in the correct numeric order.
    Never yield in filesystem/lexicographic order without explicit numeric sort.
    """

    @abstractmethod
    def acquire(self, config: dict) -> Iterator[tuple[str, np.ndarray]]:
        """Yield (image_id, image_array) pairs from the configured source.

        Args:
            config: Full application config dict.

        Yields:
            Tuples of (image_id: str, image_array: np.ndarray).
            image_array is HxWxC uint8 in BGR colour order (OpenCV convention).
        """
