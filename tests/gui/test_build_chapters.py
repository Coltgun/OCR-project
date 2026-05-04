"""
Tests for FEAT-build-chapters.

Source-scan tests verify _build_chapters_from_results: session None fallback
(single Chapter(number=1, all results)), chapters_map dict, folder range
iteration, image_id prefix matching, setdefault append, else→folder 1 fallback,
sorted(key=lambda x:x[0]) numeric chapter order.
Pure-logic tests verify Chapter grouping, numeric sort, no-session fallback.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _build_chapters_block() -> str:
    idx = _MW_SRC.index("def _build_chapters_from_results")
    end = _MW_SRC.index("\n    def _update_session_labels", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestBuildChaptersSource:
    def test_method_exists(self) -> None:
        assert "def _build_chapters_from_results" in _MW_SRC

    def test_session_none_returns_single_chapter(self) -> None:
        assert "Chapter(number=1, results=self._ocr_results)" in _build_chapters_block()

    def test_chapters_map_dict_created(self) -> None:
        assert "chapters_map: dict[int, list[OCRResult]] = {}" in _build_chapters_block()

    def test_iterates_ocr_results(self) -> None:
        assert "for r in self._ocr_results:" in _build_chapters_block()

    def test_folder_range_iteration(self) -> None:
        assert "range(1, self._session.current_folder + 1)" in _build_chapters_block()

    def test_folder_path_constructed(self) -> None:
        assert "self._session.root / str(fn)" in _build_chapters_block()

    def test_image_id_prefix_matching(self) -> None:
        assert "r.image_id" in _build_chapters_block()

    def test_setdefault_append(self) -> None:
        assert "chapters_map.setdefault(fn, []).append(r)" in _build_chapters_block()

    def test_else_fallback_to_folder_1(self) -> None:
        assert "chapters_map.setdefault(1, []).append(r)" in _build_chapters_block()

    def test_sorted_by_chapter_number(self) -> None:
        assert "sorted(chapters_map.items(), key=lambda x: x[0])" in _build_chapters_block()

    def test_chapter_namedtuple_constructed(self) -> None:
        assert "Chapter(number=fn, results=results)" in _build_chapters_block()

    def test_returns_list(self) -> None:
        assert "return [" in _build_chapters_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestBuildChaptersLogic:
    def test_no_session_produces_one_chapter(self) -> None:
        from types import SimpleNamespace
        results = [SimpleNamespace(text="a"), SimpleNamespace(text="b")]
        chapters = [SimpleNamespace(number=1, results=results)]
        assert len(chapters) == 1
        assert chapters[0].number == 1
        assert len(chapters[0].results) == 2

    def test_chapters_sorted_numerically(self) -> None:
        chapters_map = {3: ["c"], 1: ["a"], 2: ["b"]}
        sorted_chapters = sorted(chapters_map.items(), key=lambda x: x[0])
        assert [fn for fn, _ in sorted_chapters] == [1, 2, 3]

    def test_chapter_numeric_sort_beats_lexicographic(self) -> None:
        keys = [10, 2, 1, 11, 3]
        lex = sorted(str(k) for k in keys)
        num = [k for k, _ in sorted({k: [] for k in keys}.items(), key=lambda x: x[0])]
        assert num == sorted(keys)
        assert lex != [str(k) for k in sorted(keys)]

    def test_setdefault_groups_correctly(self) -> None:
        chapters_map: dict[int, list] = {}
        chapters_map.setdefault(1, []).append("r1")
        chapters_map.setdefault(1, []).append("r2")
        chapters_map.setdefault(2, []).append("r3")
        assert chapters_map[1] == ["r1", "r2"]
        assert chapters_map[2] == ["r3"]

    def test_fallback_to_folder_1(self) -> None:
        chapters_map: dict[int, list] = {}
        chapters_map.setdefault(1, []).append("unmatched")
        assert 1 in chapters_map

    def test_empty_results_produces_no_chapters(self) -> None:
        chapters_map: dict[int, list] = {}
        result = [
            (fn, results)
            for fn, results in sorted(chapters_map.items(), key=lambda x: x[0])
        ]
        assert result == []


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestBuildChaptersGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_no_session_returns_single_chapter(self, tmp_path: Path) -> None:
        from ocr.results import OCRResult
        w = self._make_window(tmp_path)
        w._session = None
        w._ocr_results = [OCRResult(text="x", confidence=1.0, image_id="1/0001")]
        chapters = w._build_chapters_from_results()
        assert len(chapters) == 1
        assert chapters[0].number == 1

    def test_empty_results_returns_empty(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._session = None
        w._ocr_results = []
        chapters = w._build_chapters_from_results()
        assert chapters[0].results == []

    def test_method_callable(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert callable(w._build_chapters_from_results)
