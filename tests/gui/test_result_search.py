"""
Tests for FEAT-result-search.

Source-scan tests verify widget creation, wiring, and slot logic.
Pure-logic tests verify filtering and label suffix.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestResultSearchSource:
    def test_search_bar_created(self) -> None:
        assert "self._search_bar = QLineEdit()" in _MW_SRC

    def test_placeholder_text(self) -> None:
        assert '"Search results\u2026"' in _MW_SRC

    def test_clear_button_enabled(self) -> None:
        assert "self._search_bar.setClearButtonEnabled(True)" in _MW_SRC

    def test_connected_to_slot(self) -> None:
        assert "self._search_bar.textChanged.connect(self._on_search_changed)" in _MW_SRC

    def test_slot_exists(self) -> None:
        assert "def _on_search_changed" in _MW_SRC

    def test_slot_case_insensitive(self) -> None:
        idx = _MW_SRC.index("def _on_search_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert ".lower()" in block

    def test_slot_restores_full_on_empty(self) -> None:
        idx = _MW_SRC.index("def _on_search_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "filtered = self._ocr_results" in block

    def test_slot_updates_pane(self) -> None:
        idx = _MW_SRC.index("def _on_search_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "setPlainText" in block

    def test_slot_updates_label_with_suffix(self) -> None:
        idx = _MW_SRC.index("def _on_search_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "filtered:" in block

    def test_clear_preview_clears_search_bar(self) -> None:
        idx = _MW_SRC.index("def _clear_preview")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._search_bar.clear()" in block

    def test_clear_preview_uses_block_signals(self) -> None:
        idx = _MW_SRC.index("def _clear_preview")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "blockSignals" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass
class _FakeResult:
    text: str
    image_id: str
    confidence: float = 0.9


def _filter(results, query: str):
    q = query.strip().lower()
    if q:
        return [r for r in results if q in r.text.lower()]
    return results


def _label_suffix(filtered, total, q: str) -> str:
    return f" (filtered: {len(filtered)}/{total})" if q else ""


class TestResultSearchLogic:
    def test_empty_query_returns_all(self) -> None:
        results = [_FakeResult("hello", "1"), _FakeResult("world", "2")]
        assert _filter(results, "") == results

    def test_matching_query_returns_subset(self) -> None:
        results = [_FakeResult("hello world", "1"), _FakeResult("goodbye", "2")]
        out = _filter(results, "hello")
        assert len(out) == 1
        assert out[0].text == "hello world"

    def test_case_insensitive(self) -> None:
        results = [_FakeResult("Hello", "1"), _FakeResult("WORLD", "2")]
        assert len(_filter(results, "hello")) == 1
        assert len(_filter(results, "world")) == 1

    def test_no_match_returns_empty(self) -> None:
        results = [_FakeResult("hello", "1")]
        assert _filter(results, "xyz") == []

    def test_label_suffix_present_when_query(self) -> None:
        suffix = _label_suffix([1], 5, "q")
        assert "filtered: 1/5" in suffix

    def test_label_suffix_absent_when_empty_query(self) -> None:
        suffix = _label_suffix([1, 2], 2, "")
        assert suffix == ""

    def test_whitespace_only_query_treated_as_empty(self) -> None:
        results = [_FakeResult("hello", "1")]
        assert _filter(results, "   ") == results


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestResultSearchGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_search_bar_exists(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert hasattr(w, "_search_bar")

    def test_clear_preview_clears_search_bar(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._search_bar.setText("test")
        w._clear_preview()
        assert w._search_bar.text() == ""

    def test_search_filters_pane(self, tmp_path: Path) -> None:
        from core.types import OCRResult
        w = self._make_window(tmp_path)
        w._ocr_results = [
            OCRResult(text="hello", image_id="1", confidence=0.9, bbox=(0,0,1,1)),
            OCRResult(text="world", image_id="2", confidence=0.9, bbox=(0,0,1,1)),
        ]
        w._search_bar.setText("hello")
        assert "world" not in w._preview_pane.toPlainText()

    def test_empty_query_restores_all(self, tmp_path: Path) -> None:
        from core.types import OCRResult
        w = self._make_window(tmp_path)
        w._ocr_results = [
            OCRResult(text="hello", image_id="1", confidence=0.9, bbox=(0,0,1,1)),
            OCRResult(text="world", image_id="2", confidence=0.9, bbox=(0,0,1,1)),
        ]
        w._search_bar.setText("hello")
        w._search_bar.clear()
        assert "world" in w._preview_pane.toPlainText()
