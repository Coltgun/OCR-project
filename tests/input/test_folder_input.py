"""Tests for FolderInputSource."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from input.base import InputSource
from input.folder_input import FolderInputSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tree(root: Path, chapters: dict[int, list[str]]) -> None:
    """Create a folder tree under *root*.

    chapters: {chapter_number: [image_stem, ...]}
    """
    for chapter_num, stems in chapters.items():
        chapter_dir = root / str(chapter_num)
        chapter_dir.mkdir(parents=True, exist_ok=True)
        for stem in stems:
            (chapter_dir / f"{stem}.png").write_bytes(b"")  # placeholder


def fake_imread(path: str) -> np.ndarray:
    """Stub for cv2.imread that returns a 1x1 BGR image."""
    return np.zeros((1, 1, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_folder(self) -> None:
        assert InputSource.get("folder") is FolderInputSource

    def test_is_subclass_of_input_source(self) -> None:
        assert issubclass(FolderInputSource, InputSource)


# ---------------------------------------------------------------------------
# _resolve_root
# ---------------------------------------------------------------------------

class TestResolveRoot:
    def test_uses_override_root(self, tmp_path: Path) -> None:
        src = FolderInputSource(root=tmp_path)
        assert src._resolve_root({}) == tmp_path

    def test_uses_config_key(self, tmp_path: Path) -> None:
        src = FolderInputSource()
        assert src._resolve_root({"batch_input_dir": str(tmp_path)}) == tmp_path

    def test_missing_config_raises_value_error(self) -> None:
        src = FolderInputSource()
        with pytest.raises(ValueError, match="batch_input_dir"):
            src._resolve_root({})

    def test_nonexistent_path_raises_file_not_found(self, tmp_path: Path) -> None:
        src = FolderInputSource(root=tmp_path / "nonexistent")
        with pytest.raises(FileNotFoundError):
            src._resolve_root({})

    def test_file_instead_of_dir_raises_not_a_directory(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("data")
        src = FolderInputSource(root=f)
        with pytest.raises(NotADirectoryError):
            src._resolve_root({})


# ---------------------------------------------------------------------------
# _collect_chapter_dirs — P0 numeric ordering
# ---------------------------------------------------------------------------

class TestCollectChapterDirs:
    def test_numeric_order(self, tmp_path: Path) -> None:
        """P0: chapters sorted numerically, not lexicographically."""
        for n in [1, 2, 10, 11, 3]:
            (tmp_path / str(n)).mkdir()
        result = FolderInputSource._collect_chapter_dirs(tmp_path)
        numbers = [num for num, _ in result]
        assert numbers == sorted(numbers), f"Not in numeric order: {numbers}"
        assert numbers == [1, 2, 3, 10, 11]

    def test_not_lexicographic_order(self, tmp_path: Path) -> None:
        """Explicit check: [1,2,10,11] != lexicographic [1,10,11,2]."""
        for n in [1, 10, 11, 2]:
            (tmp_path / str(n)).mkdir()
        result = FolderInputSource._collect_chapter_dirs(tmp_path)
        numbers = [num for num, _ in result]
        assert numbers == [1, 2, 10, 11]
        assert numbers != [1, 10, 11, 2], "Lexicographic order detected — P0 violated"

    def test_non_numeric_dirs_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "1").mkdir()
        (tmp_path / "chapter2").mkdir()
        (tmp_path / "2").mkdir()
        result = FolderInputSource._collect_chapter_dirs(tmp_path)
        numbers = [num for num, _ in result]
        assert numbers == [1, 2]

    def test_files_at_root_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "1").mkdir()
        (tmp_path / "readme.txt").write_text("ignored")
        result = FolderInputSource._collect_chapter_dirs(tmp_path)
        assert len(result) == 1

    def test_empty_root_returns_empty(self, tmp_path: Path) -> None:
        assert FolderInputSource._collect_chapter_dirs(tmp_path) == []


# ---------------------------------------------------------------------------
# _collect_images — P0 numeric ordering
# ---------------------------------------------------------------------------

class TestCollectImages:
    def test_numeric_order(self, tmp_path: Path) -> None:
        """P0: images sorted numerically by stem."""
        for stem in ["0001", "0010", "0002", "0003"]:
            (tmp_path / f"{stem}.png").write_bytes(b"")
        result = FolderInputSource._collect_images(tmp_path)
        stems = [int(p.stem) for p in result]
        assert stems == [1, 2, 3, 10]

    def test_not_lexicographic(self, tmp_path: Path) -> None:
        for stem in ["1", "10", "2"]:
            (tmp_path / f"{stem}.png").write_bytes(b"")
        result = FolderInputSource._collect_images(tmp_path)
        stems = [int(p.stem) for p in result]
        assert stems == [1, 2, 10]
        assert stems != [1, 10, 2], "Lexicographic order detected — P0 violated"

    def test_non_numeric_stems_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "0001.png").write_bytes(b"")
        (tmp_path / "cover.png").write_bytes(b"")
        result = FolderInputSource._collect_images(tmp_path)
        assert len(result) == 1
        assert result[0].stem == "0001"

    def test_non_image_files_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "0001.png").write_bytes(b"")
        (tmp_path / "0002.txt").write_text("ignored")
        result = FolderInputSource._collect_images(tmp_path)
        assert len(result) == 1

    def test_multiple_extensions_accepted(self, tmp_path: Path) -> None:
        for name in ["0001.jpg", "0002.png", "0003.jpeg", "0004.bmp"]:
            (tmp_path / name).write_bytes(b"")
        result = FolderInputSource._collect_images(tmp_path)
        assert len(result) == 4

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        assert FolderInputSource._collect_images(tmp_path) == []


# ---------------------------------------------------------------------------
# acquire() — integration
# ---------------------------------------------------------------------------

class TestAcquire:
    def test_yields_correct_image_ids(self, tmp_path: Path) -> None:
        make_tree(tmp_path, {1: ["0001", "0002"], 2: ["0001"]})
        src = FolderInputSource(root=tmp_path)
        with patch("input.folder_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        ids = [r[0] for r in results]
        assert ids == ["1/0001", "1/0002", "2/0001"]

    def test_chapter_order_is_numeric(self, tmp_path: Path) -> None:
        """P0: chapters yielded in numeric order 1, 2, 10, 11."""
        make_tree(tmp_path, {1: ["0001"], 10: ["0001"], 2: ["0001"], 11: ["0001"]})
        src = FolderInputSource(root=tmp_path)
        with patch("input.folder_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        chapter_nums = [int(r[0].split("/")[0]) for r in results]
        assert chapter_nums == [1, 2, 10, 11]

    def test_image_arrays_are_ndarray(self, tmp_path: Path) -> None:
        make_tree(tmp_path, {1: ["0001"]})
        src = FolderInputSource(root=tmp_path)
        with patch("input.folder_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        assert isinstance(results[0][1], np.ndarray)

    def test_empty_root_yields_nothing(self, tmp_path: Path) -> None:
        src = FolderInputSource(root=tmp_path)
        assert list(src.acquire({})) == []

    def test_empty_chapter_skipped(self, tmp_path: Path) -> None:
        make_tree(tmp_path, {1: ["0001"], 2: [], 3: ["0001"]})
        src = FolderInputSource(root=tmp_path)
        with patch("input.folder_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        chapter_nums = [int(r[0].split("/")[0]) for r in results]
        assert chapter_nums == [1, 3]

    def test_imread_returning_none_skipped(self, tmp_path: Path) -> None:
        make_tree(tmp_path, {1: ["0001", "0002"]})
        src = FolderInputSource(root=tmp_path)
        call_count = [0]

        def imread_first_none(path: str) -> np.ndarray | None:
            call_count[0] += 1
            return None if call_count[0] == 1 else fake_imread(path)

        with patch("input.folder_input.cv2.imread", side_effect=imread_first_none):
            results = list(src.acquire({}))
        assert len(results) == 1
        assert results[0][0] == "1/0002"

    def test_uses_config_batch_input_dir(self, tmp_path: Path) -> None:
        make_tree(tmp_path, {1: ["0001"]})
        src = FolderInputSource()
        with patch("input.folder_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({"batch_input_dir": str(tmp_path)}))
        assert len(results) == 1

    def test_missing_config_raises(self) -> None:
        src = FolderInputSource()
        with pytest.raises(ValueError):
            list(src.acquire({}))

    def test_nonexistent_root_raises(self, tmp_path: Path) -> None:
        src = FolderInputSource(root=tmp_path / "missing")
        with pytest.raises(FileNotFoundError):
            list(src.acquire({}))


# ---------------------------------------------------------------------------
# P0 regression: numeric sort never lexicographic
# ---------------------------------------------------------------------------

class TestNumericSortRegressionP0:
    def test_chapters_1_to_11_never_lexicographic(self, tmp_path: Path) -> None:
        """Lexicographic sort of 1..11 gives 1,10,11,2,3,... — must never happen."""
        chapters = {n: ["0001"] for n in range(1, 12)}
        make_tree(tmp_path, chapters)
        src = FolderInputSource(root=tmp_path)
        with patch("input.folder_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        chapter_nums = [int(r[0].split("/")[0]) for r in results]
        assert chapter_nums == list(range(1, 12)), (
            f"P0 VIOLATION: chapters not in numeric order.\n"
            f"Got: {chapter_nums}\nExpected: {list(range(1, 12))}"
        )

    def test_images_1_to_11_never_lexicographic(self, tmp_path: Path) -> None:
        """Lexicographic sort of image stems 1..11 gives 1,10,11,2,... — must never happen."""
        chapter_dir = tmp_path / "1"
        chapter_dir.mkdir()
        for n in range(1, 12):
            (chapter_dir / f"{n}.png").write_bytes(b"")
        result = FolderInputSource._collect_images(chapter_dir)
        stems = [int(p.stem) for p in result]
        assert stems == list(range(1, 12)), (
            f"P0 VIOLATION: images not in numeric order.\n"
            f"Got: {stems}\nExpected: {list(range(1, 12))}"
        )
