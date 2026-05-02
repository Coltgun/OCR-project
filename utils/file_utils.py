"""
file_utils — numeric sort helpers, image discovery, and path validation.

P0 CORRECTNESS REQUIREMENT:
    All folder and image lists MUST use numeric sort, never lexicographic.
    Lexicographic sort produces: 1, 10, 11, 2, 3 — a fatal ordering bug.
    Always use sort_folders_numeric() and sort_images_numeric() from this module.
    Never call sorted() directly on folder names or image filenames.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
)


def sort_folders_numeric(folder_names: list[str]) -> list[str]:
    """Sort folder name strings in ascending numeric order.

    Args:
        folder_names: List of folder name strings that must be valid integers.

    Returns:
        New list sorted by integer value (1, 2, 3, 10, 11, 20 — NOT 1, 10, 2).

    Raises:
        ValueError: If any name cannot be converted to int.
    """
    return sorted(folder_names, key=lambda x: int(x))


def sort_images_numeric(image_names: list[str]) -> list[str]:
    """Sort image filename strings (with extension) in ascending numeric order.

    Filenames are expected to have zero-padded integer stems: '0001.png', '0010.jpg'.

    Args:
        image_names: List of filename strings, e.g. ['0010.png', '0002.png', '0001.png'].

    Returns:
        New list sorted by integer value of the stem.

    Raises:
        ValueError: If any stem cannot be converted to int.
    """
    return sorted(image_names, key=lambda x: int(Path(x).stem))


def sort_image_paths_numeric(image_paths: list[Path]) -> list[Path]:
    """Sort Path objects for images in ascending numeric order by stem.

    Args:
        image_paths: List of Path objects whose stems are integer strings.

    Returns:
        New list sorted by integer value of path.stem.
    """
    return sorted(image_paths, key=lambda p: int(p.stem))


def sort_folder_paths_numeric(folder_paths: list[Path]) -> list[Path]:
    """Sort Path objects for chapter folders in ascending numeric order by name.

    Args:
        folder_paths: List of Path objects whose names are integer strings.

    Returns:
        New list sorted by integer value of path.name.
    """
    return sorted(folder_paths, key=lambda p: int(p.name))


def discover_images(folder: Path) -> list[Path]:
    """Return all supported image files in *folder*, sorted numerically.

    Only searches the immediate folder (non-recursive). Filenames must have
    integer stems for numeric sort to work correctly.

    Args:
        folder: Directory to search for images.

    Returns:
        List of Path objects for image files, sorted numerically by stem.
        Empty list if folder doesn't exist or contains no matching files.
    """
    if not folder.is_dir():
        logger.warning("discover_images: '%s' is not a directory.", folder)
        return []

    image_paths = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    ]

    try:
        return sort_image_paths_numeric(image_paths)
    except ValueError as exc:
        logger.warning(
            "discover_images: non-integer filename stem in '%s': %s. "
            "Falling back to lexicographic sort (may produce wrong order).",
            folder,
            exc,
        )
        return sorted(image_paths)


def discover_chapter_folders(session_root: Path) -> list[Path]:
    """Return all numeric chapter subfolders in *session_root*, sorted numerically.

    Args:
        session_root: Root directory containing chapter subfolders.

    Returns:
        List of Path objects for subfolders with integer names, sorted numerically.
        Non-integer-named subfolders are skipped with a warning.
    """
    if not session_root.is_dir():
        logger.warning("discover_chapter_folders: '%s' is not a directory.", session_root)
        return []

    numeric_folders: list[Path] = []
    for item in session_root.iterdir():
        if item.is_dir():
            try:
                int(item.name)
                numeric_folders.append(item)
            except ValueError:
                logger.debug(
                    "discover_chapter_folders: skipping non-integer folder '%s'.", item.name
                )

    return sort_folder_paths_numeric(numeric_folders)


def next_image_path(folder: Path) -> Path:
    """Return the Path for the next image to be saved in *folder*.

    Scans existing images to find the highest counter, then increments.
    Creates the folder if it does not exist.

    Args:
        folder: Chapter folder to save into.

    Returns:
        Path for the next image (zero-padded 4-digit stem), e.g. folder/0007.png.
    """
    folder.mkdir(parents=True, exist_ok=True)
    existing = [p for p in folder.iterdir() if p.suffix.lower() == ".png"]
    if existing:
        try:
            max_counter = max(int(p.stem) for p in existing)
        except ValueError:
            max_counter = 0
    else:
        max_counter = 0
    next_counter = max_counter + 1
    return folder / f"{next_counter:04d}.png"
