"""
Tests for utils/file_utils.py

P0 CORRECTNESS: The numeric sort tests are mandatory and must never be
deleted or weakened. They guard against the silent lexicographic-order
bug that would produce wrong EPUB chapter order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.file_utils import (
    discover_chapter_folders,
    discover_images,
    next_image_path,
    sort_folder_paths_numeric,
    sort_folders_numeric,
    sort_image_paths_numeric,
    sort_images_numeric,
)


# ---------------------------------------------------------------------------
# P0: Numeric sort — MUST NEVER be deleted or weakened
# ---------------------------------------------------------------------------

class TestNumericSortNeverLexicographic:
    """P0 correctness tests. The name test_numeric_sort_never_lexicographic
    is the canonical name required by app_guidelines.md Section 10.6."""

    def test_numeric_sort_never_lexicographic(self) -> None:
        """Verifies that folder sort never produces 1, 10, 2 order."""
        folders = ["10", "2", "1", "20", "11", "3"]
        result = sort_folders_numeric(folders)
        assert result == ["1", "2", "3", "10", "11", "20"], (
            f"Got {result} — lexicographic sort detected, this is a fatal bug"
        )

    def test_image_sort_numeric(self) -> None:
        """Verifies image filename sort is numeric, not lexicographic."""
        images = ["0010.png", "0002.png", "0001.png", "0100.png"]
        result = sort_images_numeric(images)
        assert result == ["0001.png", "0002.png", "0010.png", "0100.png"]

    def test_folder_sort_single_digit(self) -> None:
        folders = ["3", "1", "2"]
        assert sort_folders_numeric(folders) == ["1", "2", "3"]

    def test_folder_sort_crosses_ten_boundary(self) -> None:
        """Specifically tests the 9→10 boundary where lex sort breaks."""
        folders = ["9", "10", "11", "8"]
        result = sort_folders_numeric(folders)
        assert result == ["8", "9", "10", "11"]

    def test_folder_sort_large_numbers(self) -> None:
        folders = ["100", "20", "3", "1000", "50"]
        result = sort_folders_numeric(folders)
        assert result == ["3", "20", "50", "100", "1000"]

    def test_image_sort_zero_padded_crosses_ten_boundary(self) -> None:
        images = ["0009.png", "0010.png", "0011.png", "0008.jpg"]
        result = sort_images_numeric(images)
        assert result == ["0008.jpg", "0009.png", "0010.png", "0011.png"]


# ---------------------------------------------------------------------------
# sort_folders_numeric
# ---------------------------------------------------------------------------

class TestSortFoldersNumeric:
    def test_already_sorted_unchanged(self) -> None:
        folders = ["1", "2", "3"]
        assert sort_folders_numeric(folders) == ["1", "2", "3"]

    def test_reverse_sorted(self) -> None:
        folders = ["3", "2", "1"]
        assert sort_folders_numeric(folders) == ["1", "2", "3"]

    def test_empty_list(self) -> None:
        assert sort_folders_numeric([]) == []

    def test_single_element(self) -> None:
        assert sort_folders_numeric(["7"]) == ["7"]

    def test_returns_new_list(self) -> None:
        original = ["2", "1"]
        result = sort_folders_numeric(original)
        result.append("mutated")
        assert original == ["2", "1"]

    def test_non_integer_raises(self) -> None:
        with pytest.raises(ValueError):
            sort_folders_numeric(["1", "chapter2", "3"])


# ---------------------------------------------------------------------------
# sort_images_numeric
# ---------------------------------------------------------------------------

class TestSortImagesNumeric:
    def test_mixed_extensions(self) -> None:
        images = ["0003.jpg", "0001.png", "0002.jpeg"]
        result = sort_images_numeric(images)
        assert result == ["0001.png", "0002.jpeg", "0003.jpg"]

    def test_non_padded_stems_sort_by_value(self) -> None:
        images = ["10.png", "2.png", "1.png"]
        result = sort_images_numeric(images)
        assert result == ["1.png", "2.png", "10.png"]

    def test_empty_list(self) -> None:
        assert sort_images_numeric([]) == []

    def test_non_integer_stem_raises(self) -> None:
        with pytest.raises(ValueError):
            sort_images_numeric(["0001.png", "page2.png"])


# ---------------------------------------------------------------------------
# sort_image_paths_numeric / sort_folder_paths_numeric
# ---------------------------------------------------------------------------

class TestSortPaths:
    def test_image_paths_sorted_numerically(self) -> None:
        paths = [Path("folder/0010.png"), Path("folder/0002.png"), Path("folder/0001.png")]
        result = sort_image_paths_numeric(paths)
        assert [p.name for p in result] == ["0001.png", "0002.png", "0010.png"]

    def test_folder_paths_sorted_numerically(self) -> None:
        paths = [Path("root/10"), Path("root/2"), Path("root/1")]
        result = sort_folder_paths_numeric(paths)
        assert [p.name for p in result] == ["1", "2", "10"]


# ---------------------------------------------------------------------------
# discover_images
# ---------------------------------------------------------------------------

class TestDiscoverImages:
    def test_returns_images_in_numeric_order(self, tmp_path: Path) -> None:
        for name in ["0010.png", "0002.png", "0001.png"]:
            (tmp_path / name).write_bytes(b"")
        result = discover_images(tmp_path)
        assert [p.name for p in result] == ["0001.png", "0002.png", "0010.png"]

    def test_filters_non_image_files(self, tmp_path: Path) -> None:
        (tmp_path / "0001.png").write_bytes(b"")
        (tmp_path / "notes.txt").write_bytes(b"")
        (tmp_path / "0002.jpg").write_bytes(b"")
        result = discover_images(tmp_path)
        assert {p.name for p in result} == {"0001.png", "0002.jpg"}

    def test_empty_folder_returns_empty(self, tmp_path: Path) -> None:
        assert discover_images(tmp_path) == []

    def test_nonexistent_folder_returns_empty(self, tmp_path: Path) -> None:
        assert discover_images(tmp_path / "ghost") == []

    def test_supported_extensions_recognised(self, tmp_path: Path) -> None:
        extensions = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"]
        for i, ext in enumerate(extensions, start=1):
            (tmp_path / f"{i:04d}{ext}").write_bytes(b"")
        result = discover_images(tmp_path)
        assert len(result) == len(extensions)


# ---------------------------------------------------------------------------
# discover_chapter_folders
# ---------------------------------------------------------------------------

class TestDiscoverChapterFolders:
    def test_returns_numeric_folders_in_order(self, tmp_path: Path) -> None:
        for name in ["10", "2", "1"]:
            (tmp_path / name).mkdir()
        result = discover_chapter_folders(tmp_path)
        assert [p.name for p in result] == ["1", "2", "10"]

    def test_skips_non_integer_folders(self, tmp_path: Path) -> None:
        (tmp_path / "1").mkdir()
        (tmp_path / "notes").mkdir()
        (tmp_path / "2").mkdir()
        result = discover_chapter_folders(tmp_path)
        assert [p.name for p in result] == ["1", "2"]

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert discover_chapter_folders(tmp_path) == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        assert discover_chapter_folders(tmp_path / "ghost") == []


# ---------------------------------------------------------------------------
# next_image_path
# ---------------------------------------------------------------------------

class TestNextImagePath:
    def test_first_image_in_empty_folder(self, tmp_path: Path) -> None:
        folder = tmp_path / "1"
        result = next_image_path(folder)
        assert result.name == "0001.png"
        assert result.parent == folder

    def test_increments_from_existing_images(self, tmp_path: Path) -> None:
        folder = tmp_path / "1"
        folder.mkdir()
        for name in ["0001.png", "0002.png", "0003.png"]:
            (folder / name).write_bytes(b"")
        result = next_image_path(folder)
        assert result.name == "0004.png"

    def test_creates_folder_if_missing(self, tmp_path: Path) -> None:
        folder = tmp_path / "5"
        assert not folder.exists()
        next_image_path(folder)
        assert folder.exists()

    def test_handles_gaps_in_sequence(self, tmp_path: Path) -> None:
        folder = tmp_path / "1"
        folder.mkdir()
        (folder / "0001.png").write_bytes(b"")
        (folder / "0005.png").write_bytes(b"")
        result = next_image_path(folder)
        assert result.name == "0006.png"
