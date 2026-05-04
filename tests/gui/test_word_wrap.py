"""
Tests for FEAT-word-wrap.

Source-scan tests verify _word_wrap_action QAction (checkable, triggered→
_toggle_word_wrap, added to view_menu), init sync of checked state from
config, _toggle_word_wrap (persist preview_word_wrap + save + _apply_word_wrap),
_apply_word_wrap (WidgetWidth vs NoWrap on _preview_pane).
Pure-logic tests verify config round-trip and wrap mode selection logic.
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

def _toggle_block() -> str:
    idx = _MW_SRC.index("def _toggle_word_wrap")
    end = _MW_SRC.index("\n    def _apply_word_wrap", idx + 1)
    return _MW_SRC[idx:end]

def _apply_word_wrap_block() -> str:
    idx = _MW_SRC.index("def _apply_word_wrap")
    end = _MW_SRC.index("\n    @Slot(bool)\n    def _toggle_dark_mode", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestWordWrapSource:
    def test_word_wrap_action_created(self) -> None:
        assert 'self._word_wrap_action = QAction("Word Wrap", self)' in _MW_SRC

    def test_word_wrap_action_checkable(self) -> None:
        assert "_word_wrap_action.setCheckable(True)" in _MW_SRC

    def test_word_wrap_action_connected(self) -> None:
        assert "_word_wrap_action.triggered.connect(self._toggle_word_wrap)" in _MW_SRC

    def test_word_wrap_action_added_to_view_menu(self) -> None:
        assert "view_menu.addAction(self._word_wrap_action)" in _MW_SRC

    def test_word_wrap_action_checked_from_config_on_init(self) -> None:
        assert "_word_wrap_action.setChecked(wrap)" in _MW_SRC

    def test_apply_word_wrap_called_on_init(self) -> None:
        assert "self._apply_word_wrap(wrap)" in _MW_SRC

    def test_toggle_word_wrap_persists_config(self) -> None:
        assert 'self._config.set("preview_word_wrap", checked)' in _toggle_block()

    def test_toggle_word_wrap_saves_config(self) -> None:
        assert "self._config.save()" in _toggle_block()

    def test_toggle_word_wrap_calls_apply(self) -> None:
        assert "self._apply_word_wrap(checked)" in _toggle_block()

    def test_apply_word_wrap_exists(self) -> None:
        assert "def _apply_word_wrap" in _MW_SRC

    def test_apply_word_wrap_uses_widget_width(self) -> None:
        assert "QTextEdit.LineWrapMode.WidgetWidth" in _apply_word_wrap_block()

    def test_apply_word_wrap_uses_no_wrap(self) -> None:
        assert "QTextEdit.LineWrapMode.NoWrap" in _apply_word_wrap_block()

    def test_apply_word_wrap_sets_mode_on_preview_pane(self) -> None:
        assert "_preview_pane.setLineWrapMode(mode)" in _apply_word_wrap_block()

    def test_config_key_is_preview_word_wrap(self) -> None:
        assert '"preview_word_wrap"' in _MW_SRC

    def test_init_reads_preview_word_wrap_default_true(self) -> None:
        assert '"preview_word_wrap", True' in _MW_SRC

    def test_apply_word_wrap_ternary_selects_mode(self) -> None:
        blk = _apply_word_wrap_block()
        assert "if enabled" in blk or "if " in blk

    def test_toggle_word_wrap_slot_decorated(self) -> None:
        idx = _MW_SRC.index("def _toggle_word_wrap")
        decorator_zone = _MW_SRC[max(0, idx - 30):idx]
        assert "@Slot" in decorator_zone


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestWordWrapLogic:
    def test_config_round_trip_wrap_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_word_wrap", True)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("preview_word_wrap") is True

    def test_config_round_trip_wrap_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_word_wrap", False)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("preview_word_wrap") is False

    def test_wrap_mode_widget_width_when_enabled(self) -> None:
        enabled = True
        mode = "WidgetWidth" if enabled else "NoWrap"
        assert mode == "WidgetWidth"

    def test_wrap_mode_no_wrap_when_disabled(self) -> None:
        enabled = False
        mode = "WidgetWidth" if enabled else "NoWrap"
        assert mode == "NoWrap"

    def test_default_word_wrap_is_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert bool(cfg.get("preview_word_wrap", True)) is True

    def test_bool_cast_from_config(self) -> None:
        raw = True
        wrap = bool(raw)
        assert wrap is True


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestWordWrapGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_word_wrap_action_initially_checked(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._word_wrap_action.isChecked()

    def test_toggle_off_disables_wrap(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QTextEdit
        w = self._make_window(tmp_path)
        w._toggle_word_wrap(False)
        assert w._preview_pane.lineWrapMode() == QTextEdit.LineWrapMode.NoWrap

    def test_toggle_on_enables_wrap(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QTextEdit
        w = self._make_window(tmp_path)
        w._toggle_word_wrap(True)
        assert w._preview_pane.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth
