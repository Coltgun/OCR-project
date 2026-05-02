"""Tests for FlatInputSource."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from input.base import InputSource
from input.flat_input import FlatInputSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fake_imread(path: str) -> np.ndarray:
    return np.zeros((1, 1, 3), dtype=np.uint8)


def make_images(root: Path, stems: list[str], suffix: str = ".png") -> list[Path]:
    paths = []
    for stem in stems:
        p = root / f"{stem}{suffix}"
        p.write_bytes(b"")
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registered_as_flat(self) -> None:
        assert InputSource.get("flat") is FlatInputSource

    def test_is_subclass_of_input_source(self) -> None:
        assert issubclass(FlatInputSource, InputSource)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_no_args(self) -> None:
        src = FlatInputSource()
        assert src._paths_override is None

    def test_single_string_path(self, tmp_path: Path) -> None:
        p = tmp_path / "a.png"
        src = FlatInputSource(paths=str(p))
        assert src._paths_override == [p]

    def test_single_path_object(self, tmp_path: Path) -> None:
        p = tmp_path / "a.png"
        src = FlatInputSource(paths=p)
        assert src._paths_override == [p]

    def test_list_of_strings(self, tmp_path: Path) -> None:
        paths = [str(tmp_path / f"{i}.png") for i in range(3)]
        src = FlatInputSource(paths=paths)
        assert len(src._paths_override) == 3

    def test_list_of_path_objects(self, tmp_path: Path) -> None:
        paths = [tmp_path / f"{i}.png" for i in range(3)]
        src = FlatInputSource(paths=paths)
        assert src._paths_override == paths


# ---------------------------------------------------------------------------
# _resolve_paths
# ---------------------------------------------------------------------------

class TestResolvePaths:
    def test_uses_override(self, tmp_path: Path) -> None:
        p = tmp_path / "a.png"
        src = FlatInputSource(paths=p)
        assert src._resolve_paths({}) == [p]

    def test_uses_config_string(self, tmp_path: Path) -> None:
        p = tmp_path / "a.png"
        src = FlatInputSource()
        result = src._resolve_paths({"flat_input_paths": str(p)})
        assert result == [p]

    def test_uses_config_list(self, tmp_path: Path) -> None:
        paths = [tmp_path / f"{i}.png" for i in range(2)]
        src = FlatInputSource()
        result = src._resolve_paths({"flat_input_paths": [str(p) for p in paths]})
        assert result == paths

    def test_missing_config_raises_value_error(self) -> None:
        src = FlatInputSource()
        with pytest.raises(ValueError, match="flat_input_paths"):
            src._resolve_paths({})

    def test_empty_list_in_config_raises(self) -> None:
        src = FlatInputSource()
        with pytest.raises(ValueError):
            src._resolve_paths({"flat_input_paths": []})


# ---------------------------------------------------------------------------
# _sort_paths — P0 numeric sort
# ---------------------------------------------------------------------------

class TestSortPaths:
    def test_numeric_stems_sorted_numerically(self, tmp_path: Path) -> None:
        paths = [tmp_path / f"{n}.png" for n in [10, 1, 2, 11]]
        result = FlatInputSource._sort_paths(paths)
        stems = [int(p.stem) for p in result]
        assert stems == [1, 2, 10, 11]

    def test_not_lexicographic(self, tmp_path: Path) -> None:
        """1,10,11,2 is lexicographic order — must not happen."""
        paths = [tmp_path / f"{n}.png" for n in [1, 10, 2, 11]]
        result = FlatInputSource._sort_paths(paths)
        stems = [int(p.stem) for p in result]
        assert stems == [1, 2, 10, 11]
        assert stems != [1, 10, 11, 2]

    def test_non_numeric_stems_preserve_order(self, tmp_path: Path) -> None:
        paths = [tmp_path / f"{n}.png" for n in ["alpha", "beta", "gamma"]]
        result = FlatInputSource._sort_paths(paths)
        assert result == paths

    def test_mixed_numeric_and_non_numeric_preserves_order(
        self, tmp_path: Path
    ) -> None:
        paths = [tmp_path / "1.png", tmp_path / "cover.png", tmp_path / "2.png"]
        result = FlatInputSource._sort_paths(paths)
        assert result == paths


# ---------------------------------------------------------------------------
# acquire()
# ---------------------------------------------------------------------------

class TestAcquire:
    def test_yields_correct_image_ids(self, tmp_path: Path) -> None:
        make_images(tmp_path, ["0001", "0002", "0003"])
        src = FlatInputSource(paths=[tmp_path / f"{s}.png" for s in ["0001", "0002", "0003"]])
        with patch("input.flat_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        ids = [r[0] for r in results]
        assert ids == ["1/0001", "1/0002", "1/0003"]

    def test_all_images_in_chapter_1(self, tmp_path: Path) -> None:
        make_images(tmp_path, ["0001", "0002"])
        src = FlatInputSource(paths=[tmp_path / f"{s}.png" for s in ["0001", "0002"]])
        with patch("input.flat_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        chapters = {r[0].split("/")[0] for r in results}
        assert chapters == {"1"}

    def test_numeric_stems_sorted(self, tmp_path: Path) -> None:
        paths = make_images(tmp_path, ["10", "1", "2"])
        src = FlatInputSource(paths=paths)
        with patch("input.flat_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        stems = [r[0].split("/")[1] for r in results]
        assert [int(s) for s in stems] == [1, 2, 10]

    def test_image_arrays_are_ndarray(self, tmp_path: Path) -> None:
        make_images(tmp_path, ["0001"])
        src = FlatInputSource(paths=[tmp_path / "0001.png"])
        with patch("input.flat_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        assert isinstance(results[0][1], np.ndarray)

    def test_single_path_string_in_config(self, tmp_path: Path) -> None:
        make_images(tmp_path, ["0001"])
        src = FlatInputSource()
        with patch("input.flat_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({"flat_input_paths": str(tmp_path / "0001.png")}))
        assert len(results) == 1
        assert results[0][0] == "1/0001"

    def test_nonexistent_path_skipped(self, tmp_path: Path) -> None:
        real = tmp_path / "0001.png"
        real.write_bytes(b"")
        missing = tmp_path / "9999.png"
        src = FlatInputSource(paths=[missing, real])
        with patch("input.flat_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        assert len(results) == 1
        assert results[0][0] == "1/0001"

    def test_unsupported_extension_skipped(self, tmp_path: Path) -> None:
        txt = tmp_path / "1.txt"
        txt.write_text("not an image")
        png = tmp_path / "2.png"
        png.write_bytes(b"")
        src = FlatInputSource(paths=[txt, png])
        with patch("input.flat_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        assert len(results) == 1
        assert results[0][0] == "1/2"

    def test_imread_none_skipped(self, tmp_path: Path) -> None:
        paths = make_images(tmp_path, ["0001", "0002"])
        src = FlatInputSource(paths=paths)
        call_count = [0]

        def imread_first_none(path: str) -> np.ndarray | None:
            call_count[0] += 1
            return None if call_count[0] == 1 else fake_imread(path)

        with patch("input.flat_input.cv2.imread", side_effect=imread_first_none):
            results = list(src.acquire({}))
        assert len(results) == 1
        assert results[0][0] == "1/0002"

    def test_empty_paths_raises(self) -> None:
        src = FlatInputSource()
        with pytest.raises(ValueError):
            list(src.acquire({}))

    def test_empty_list_in_config_raises(self) -> None:
        src = FlatInputSource()
        with pytest.raises(ValueError):
            list(src.acquire({"flat_input_paths": []}))


# ---------------------------------------------------------------------------
# P0 regression: numeric sort never lexicographic
# ---------------------------------------------------------------------------

class TestNumericSortRegressionP0:
    def test_images_1_to_11_numeric_order(self, tmp_path: Path) -> None:
        """Lexicographic sort of 1..11 gives 1,10,11,2,3 — must never happen."""
        paths = make_images(tmp_path, [str(n) for n in range(1, 12)])
        src = FlatInputSource(paths=paths)
        with patch("input.flat_input.cv2.imread", side_effect=fake_imread):
            results = list(src.acquire({}))
        stems = [int(r[0].split("/")[1]) for r in results]
        assert stems == list(range(1, 12)), (
            f"P0 VIOLATION: images not in numeric order.\n"
            f"Got: {stems}\nExpected: {list(range(1, 12))}"
        )
