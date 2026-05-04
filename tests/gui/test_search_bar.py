"""
Tests for FEAT-search-bar.

Source-scan tests verify _search_bar QLineEdit (placeholder, setClearButtonEnabled,
textChanged->_on_search_changed, added to layout), _on_search_changed:
empty ocr_results guard, q=query.strip().lower(), non-empty filter (q in r.text.lower()),
empty q->full results, image_id grouping separator, setPlainText, filtered suffix
label (n/total), avg_conf computed over all results, blockSignals usage in
_clear_preview.
Pure-logic tests verify filter semantics, suffix string, avg conf over all results.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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

def _search_changed_block() -> str:
    idx = _MW_SRC.index("def _on_search_changed")
    end = _MW_SRC.index("\n    @Slot()\n    def _copy_section_to_clipboard", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestSearchBarSource:
    def test_search_bar_created(self) -> None:
        assert "self._search_bar = QLineEdit()" in _MW_SRC

    def test_search_bar_placeholder(self) -> None:
        assert '_search_bar.setPlaceholderText("Search results' in _MW_SRC

    def test_search_bar_clear_button_enabled(self) -> None:
        assert "_search_bar.setClearButtonEnabled(True)" in _MW_SRC

    def test_search_bar_connected(self) -> None:
        assert "_search_bar.textChanged.connect(self._on_search_changed)" in _MW_SRC

    def test_on_search_changed_exists(self) -> None:
        assert "def _on_search_changed" in _MW_SRC

    def test_guards_empty_ocr_results(self) -> None:
        assert "if not self._ocr_results:" in _search_changed_block()

    def test_query_stripped_lowered(self) -> None:
        assert "q = query.strip().lower()" in _search_changed_block()

    def test_filter_uses_text_lower(self) -> None:
        assert "q in r.text.lower()" in _search_changed_block()

    def test_empty_query_uses_all_results(self) -> None:
        assert "filtered = self._ocr_results" in _search_changed_block()

    def test_image_id_grouping_in_search(self) -> None:
        assert "r.image_id and r.image_id != current_id" in _search_changed_block()

    def test_sets_plain_text(self) -> None:
        assert "_preview_pane.setPlainText(" in _search_changed_block()

    def test_filtered_suffix_computed(self) -> None:
        assert "filtered: {n}/{total}" in _search_changed_block()

    def test_avg_conf_computed_over_all_results(self) -> None:
        assert "sum(r.confidence for r in self._ocr_results)" in _search_changed_block()

    def test_label_updated_with_count(self) -> None:
        assert "_preview_label.setText(" in _search_changed_block()

    def test_clear_preview_blocks_search_signals(self) -> None:
        assert "_search_bar.blockSignals(True)" in _MW_SRC

    def test_on_search_changed_slot_str_decorated(self) -> None:
        idx = _MW_SRC.index("def _on_search_changed")
        decorator_zone = _MW_SRC[max(0, idx - 30):idx]
        assert "@Slot(str)" in decorator_zone

    def test_query_stripped_and_lowered(self) -> None:
        assert "query.strip().lower()" in _search_changed_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestSearchBarLogic:
    def test_filter_case_insensitive_match(self) -> None:
        results = [
            SimpleNamespace(text="Hello World", confidence=0.9, image_id="1/0001"),
            SimpleNamespace(text="foo bar", confidence=0.8, image_id="1/0002"),
        ]
        q = "hello"
        filtered = [r for r in results if q in r.text.lower()]
        assert len(filtered) == 1
        assert filtered[0].text == "Hello World"

    def test_empty_query_returns_all(self) -> None:
        results = [
            SimpleNamespace(text="abc", confidence=0.9, image_id="1/0001"),
            SimpleNamespace(text="xyz", confidence=0.8, image_id="1/0002"),
        ]
        q = "".strip().lower()
        filtered = results if not q else [r for r in results if q in r.text.lower()]
        assert len(filtered) == 2

    def test_no_match_returns_empty(self) -> None:
        results = [SimpleNamespace(text="hello", confidence=0.9, image_id="1/0001")]
        q = "zzz"
        filtered = [r for r in results if q in r.text.lower()]
        assert filtered == []

    def test_filtered_suffix_when_query(self) -> None:
        q = "hello"
        n, total = 1, 3
        suffix = f" (filtered: {n}/{total})" if q else ""
        assert suffix == " (filtered: 1/3)"

    def test_no_suffix_when_empty_query(self) -> None:
        q = ""
        n, total = 3, 3
        suffix = f" (filtered: {n}/{total})" if q else ""
        assert suffix == ""

    def test_avg_conf_computed_over_all_not_filtered(self) -> None:
        all_results = [
            SimpleNamespace(confidence=0.8),
            SimpleNamespace(confidence=0.9),
            SimpleNamespace(confidence=1.0),
        ]
        total = len(all_results)
        avg = sum(r.confidence for r in all_results) / total if total > 0 else 0.0
        assert abs(avg - 0.9) < 1e-9

    def test_query_strip_and_lower(self) -> None:
        raw = "  Hello  "
        q = raw.strip().lower()
        assert q == "hello"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSearchBarGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_search_bar_initially_empty(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._search_bar.text() == ""

    def test_search_bar_clear_button_enabled(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._search_bar.isClearButtonEnabled()

    def test_empty_search_with_no_results_does_nothing(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._ocr_results = []
        w._on_search_changed("hello")
