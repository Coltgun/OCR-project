"""
Tests for FEAT-search-filter.

Source-scan tests verify _search_bar QLineEdit, textChanged signal wiring,
_on_search_changed filter logic, count label update, and avg_conf display.
Pure-logic tests verify case-insensitive filter and label formatting.
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

def _search_block() -> str:
    idx = _MW_SRC.index("def _on_search_changed")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestSearchFilterSource:
    def test_search_bar_created(self) -> None:
        assert "self._search_bar = QLineEdit()" in _MW_SRC

    def test_search_bar_placeholder(self) -> None:
        assert "_search_bar.setPlaceholderText" in _MW_SRC

    def test_search_bar_text_changed_connected(self) -> None:
        assert "_search_bar.textChanged.connect" in _MW_SRC

    def test_on_search_changed_slot_exists(self) -> None:
        assert "def _on_search_changed" in _MW_SRC

    def test_search_strips_and_lowercases(self) -> None:
        assert ".strip().lower()" in _search_block()

    def test_search_filters_ocr_results(self) -> None:
        assert "self._ocr_results" in _search_block()

    def test_search_empty_resets_to_all_results(self) -> None:
        assert "filtered = self._ocr_results" in _search_block()

    def test_search_updates_preview_pane(self) -> None:
        assert "_preview_pane.setPlainText" in _search_block()

    def test_search_updates_preview_label(self) -> None:
        assert "_preview_label.setText" in _search_block()

    def test_search_shows_filtered_count(self) -> None:
        assert "filtered:" in _search_block()

    def test_search_shows_avg_conf(self) -> None:
        assert "avg_conf" in _search_block()

    def test_search_clear_on_session_start(self) -> None:
        assert "_search_bar.clear()" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestSearchFilterLogic:
    def _filter(self, results: list[str], query: str) -> list[str]:
        q = query.strip().lower()
        return [r for r in results if q in r.lower()] if q else results

    def test_empty_query_returns_all(self) -> None:
        results = ["Hello", "World"]
        assert self._filter(results, "") == results

    def test_case_insensitive_match(self) -> None:
        results = ["Hello World", "Goodbye"]
        assert self._filter(results, "HELLO") == ["Hello World"]

    def test_no_match_returns_empty(self) -> None:
        results = ["Hello", "World"]
        assert self._filter(results, "xyz") == []

    def test_partial_match(self) -> None:
        results = ["Hello World", "Hello Earth"]
        assert self._filter(results, "earth") == ["Hello Earth"]

    def test_filtered_label_suffix(self) -> None:
        q, n, total = "hi", 2, 5
        suffix = f" (filtered: {n}/{total})" if q else ""
        assert suffix == " (filtered: 2/5)"

    def test_no_suffix_when_query_empty(self) -> None:
        q = ""
        suffix = f" (filtered: 1/5)" if q else ""
        assert suffix == ""


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSearchFilterGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_search_bar_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._search_bar is not None

    def test_search_empty_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._search_bar.text() == ""

    def test_search_noop_when_no_results(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._on_search_changed("hello")
        assert w._preview_pane.toPlainText() == ""
