"""
FlatInputSource — InputSource for Single OCR Mode.

Registration key: "flat"

Accepts either:
  - A single image file path  (config["flat_input_paths"] = "/path/to/image.png")
  - A list of image file paths (config["flat_input_paths"] = ["/a.png", "/b.png"])

All images are treated as belonging to chapter 1.  There is no folder
organisation — the caller is responsible for providing the paths in the
desired order.  If the paths happen to have numeric stems, they are sorted
numerically (P0); otherwise they are yielded in the order provided.

Config keys consumed:
    flat_input_paths  (str | list[str])  one or more absolute image paths

image_id format: "1/{stem}"   e.g.  "1/0003"  or  "1/my_scan"
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

from input.base import InputSource

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
)


class FlatInputSource(InputSource, register_as="flat"):
    """Yields images from a flat list of paths, all assigned to chapter 1.

    If all provided path stems are parseable as integers they are sorted
    numerically (P0 correctness).  Otherwise the caller-supplied order is
    preserved.

    Args:
        paths: Override image paths.  When None, read from
               config["flat_input_paths"] at acquire() time.
    """

    def __init__(
        self, paths: list[Path | str] | Path | str | None = None
    ) -> None:
        if paths is None:
            self._paths_override: list[Path] | None = None
        elif isinstance(paths, (str, Path)):
            self._paths_override = [Path(paths)]
        else:
            self._paths_override = [Path(p) for p in paths]

    def acquire(self, config: dict) -> Iterator[tuple[str, np.ndarray]]:
        """Yield (image_id, image_array) pairs for every provided image path.

        Args:
            config: Full application config dict.

        Yields:
            Tuples of (image_id, BGR uint8 ndarray).
            image_id format: "1/<stem>"

        Raises:
            ValueError: If no paths are configured and none provided at init.
        """
        paths = self._resolve_paths(config)
        ordered = self._sort_paths(paths)

        for path in ordered:
            if not path.exists():
                logger.warning(
                    "FlatInputSource: path '%s' does not exist, skipping.", path
                )
                continue
            if path.suffix.lower() not in _IMAGE_SUFFIXES:
                logger.warning(
                    "FlatInputSource: '%s' is not a supported image type, skipping.",
                    path.name,
                )
                continue
            image_array = self._load_image(path)
            if image_array is None:
                continue
            image_id = f"1/{path.stem}"
            logger.debug(
                "FlatInputSource: yielding image_id='%s' from '%s'.",
                image_id, path,
            )
            yield image_id, image_array

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_paths(self, config: dict) -> list[Path]:
        """Return the list of paths from override or config."""
        if self._paths_override is not None:
            return self._paths_override

        raw = config.get("flat_input_paths")
        if not raw:
            raise ValueError(
                "FlatInputSource: 'flat_input_paths' not set in config "
                "and no paths were provided at init."
            )
        if isinstance(raw, (str, Path)):
            return [Path(str(raw))]
        return [Path(str(p)) for p in raw]

    @staticmethod
    def _sort_paths(paths: list[Path]) -> list[Path]:
        """Sort paths numerically by stem if all stems are integers; else preserve order.

        P0: when stems are numeric, sort by int(stem) not str(stem).
        """
        try:
            keyed = [(int(p.stem), p) for p in paths]
            keyed.sort(key=lambda t: t[0])
            return [p for _, p in keyed]
        except ValueError:
            return list(paths)

    @staticmethod
    def _load_image(path: Path) -> np.ndarray | None:
        """Load an image with cv2. Returns None on failure."""
        try:
            img = cv2.imread(str(path))
            if img is None:
                logger.warning(
                    "FlatInputSource: cv2.imread returned None for '%s'.", path
                )
            return img
        except Exception as exc:
            logger.error(
                "FlatInputSource: failed to load '%s': %s", path, exc
            )
            return None
