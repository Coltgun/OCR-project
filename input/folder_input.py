"""
FolderInputSource — InputSource that reads an existing folder tree.

Registration key: "folder"

Expected folder structure (Batch OCR Mode):
    <root>/
        1/          ← chapter folders: plain integers, numeric order
            0001.png
            0002.png
            ...
        2/
            0001.png
            ...

P0 CORRECTNESS: Both chapter folders AND image files within each folder MUST
be sorted numerically, never lexicographically.
    CORRECT:   sorted(items, key=lambda p: int(p.stem))
    FORBIDDEN: sorted(items)  or  os.listdir()

Config keys consumed:
    batch_input_dir  (str)  path to the root folder tree  [required]

Yields (image_id, image_array) where image_id encodes chapter and filename:
    f"{chapter_number}/{image_stem}"   e.g.  "3/0007"

This encoding lets downstream stages (EpubFormatter chapter grouping) recover
the chapter number without any extra metadata.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

from input.base import InputSource

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"})


class FolderInputSource(InputSource, register_as="folder"):
    """Yields images from a chapter-organised folder tree in numeric order.

    Each subfolder of the root is treated as a chapter (plain integer name).
    Images inside each chapter folder must have numeric stems (zero-padded or
    not — both are handled by explicit int() sort).

    Args:
        root: Override root path.  When None, read from config["batch_input_dir"].
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self._root_override: Path | None = Path(root) if root is not None else None

    def acquire(self, config: dict) -> Iterator[tuple[str, np.ndarray]]:
        """Yield (image_id, image_array) pairs in strict numeric chapter + image order.

        Args:
            config: Full application config dict.

        Yields:
            Tuples of (image_id, BGR uint8 ndarray).
            image_id format: "<chapter_number>/<image_stem>"  e.g. "2/0003".

        Raises:
            ValueError: If root is not configured and not provided at init.
            FileNotFoundError: If the root directory does not exist.
        """
        root = self._resolve_root(config)
        chapter_dirs = self._collect_chapter_dirs(root)

        if not chapter_dirs:
            logger.warning("FolderInputSource: no chapter folders found in '%s'.", root)
            return

        for chapter_num, chapter_dir in chapter_dirs:
            image_paths = self._collect_images(chapter_dir)
            if not image_paths:
                logger.debug(
                    "FolderInputSource: chapter %d is empty, skipping.", chapter_num
                )
                continue
            for image_path in image_paths:
                image_array = self._load_image(image_path)
                if image_array is None:
                    continue
                image_id = f"{chapter_num}/{image_path.stem}"
                logger.debug(
                    "FolderInputSource: yielding image_id='%s' from '%s'.",
                    image_id, image_path,
                )
                yield image_id, image_array

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_root(self, config: dict) -> Path:
        """Return the root path from override or config."""
        if self._root_override is not None:
            root = self._root_override
        else:
            raw = config.get("batch_input_dir")
            if not raw:
                raise ValueError(
                    "FolderInputSource: 'batch_input_dir' not set in config "
                    "and no root was provided at init."
                )
            root = Path(str(raw))

        if not root.exists():
            raise FileNotFoundError(
                f"FolderInputSource: root directory '{root}' does not exist."
            )
        if not root.is_dir():
            raise NotADirectoryError(
                f"FolderInputSource: '{root}' is not a directory."
            )
        return root

    @staticmethod
    def _collect_chapter_dirs(root: Path) -> list[tuple[int, Path]]:
        """Return (chapter_number, path) pairs for all numeric subdirs, sorted numerically.

        P0: sorted by int(name), never lexicographically.
        Non-numeric names are skipped with a warning.
        """
        result: list[tuple[int, Path]] = []
        for child in root.iterdir():
            if not child.is_dir():
                continue
            try:
                chapter_num = int(child.name)
            except ValueError:
                logger.warning(
                    "FolderInputSource: skipping non-numeric folder '%s'.", child.name
                )
                continue
            result.append((chapter_num, child))
        # P0: numeric sort
        result.sort(key=lambda t: t[0])
        return result

    @staticmethod
    def _collect_images(chapter_dir: Path) -> list[Path]:
        """Return image paths from *chapter_dir* sorted numerically by stem.

        P0: sorted by int(stem), never lexicographically.
        Files whose stems cannot be parsed as int are skipped with a warning.
        """
        valid: list[tuple[int, Path]] = []
        for p in chapter_dir.iterdir():
            if p.suffix.lower() not in _IMAGE_SUFFIXES:
                continue
            try:
                stem_int = int(p.stem)
            except ValueError:
                logger.warning(
                    "FolderInputSource: skipping non-numeric image '%s'.", p.name
                )
                continue
            valid.append((stem_int, p))
        valid.sort(key=lambda t: t[0])
        return [p for _, p in valid]

    @staticmethod
    def _load_image(path: Path) -> np.ndarray | None:
        """Load an image with cv2. Returns None on failure."""
        try:
            img = cv2.imread(str(path))
            if img is None:
                logger.warning(
                    "FolderInputSource: cv2.imread returned None for '%s'.", path
                )
            return img
        except Exception as exc:
            logger.error(
                "FolderInputSource: failed to load '%s': %s", path, exc
            )
            return None
