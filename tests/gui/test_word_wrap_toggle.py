"""
Tests for FEAT-word-wrap-toggle.

Source-scan tests verify action creation, wiring, and apply helper.
Pure-logic tests verify config persistence semantics.
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
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestWordWrapToggleSource:
    def test_action_created(self) -> None:
        assert 'self._word_wrap_action = QAction("Word Wrap", self)' in _MW_SRC

    def test_action_checkable(self) -> None:
        assert "self._word_wrap_action.setCheckable(True)" in _MW_SRC

    def test_action_connected(self) -> None:
        assert "self._word_wrap_action.triggered.connect(self._toggle_word_wrap)" in _MW_SRC

    def test_action_added_to_view_menu(self) -> None:
        idx = _MW_SRC.index("def _build_menu")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "view_menu.addAction(self._word_wrap_action)" in block

    def test_toggle_slot_exists(self) -> None:
        assert "def _toggle_word_wrap" in _MW_SRC

    def test_apply_helper_exists(self) -> None:
        assert "def _apply_word_wrap" in _MW_SRC

    def test_toggle_persists_to_config(self) -> None:
        idx = _MW_SRC.index("def _toggle_word_wrap")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert 'self._config.set("preview_word_wrap", checked)' in block

    def test_toggle_calls_apply(self) -> None:
        idx = _MW_SRC.index("def _toggle_word_wrap")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._apply_word_wrap(checked)" in block

    def test_apply_uses_widget_width(self) -> None:
        idx = _MW_SRC.index("def _apply_word_wrap")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "WidgetWidth" in block

    def test_apply_uses_no_wrap(self) -> None:
        idx = _MW_SRC.index("def _apply_word_wrap")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "NoWrap" in block

    def test_apply_calls_set_line_wrap_mode(self) -> None:
        idx = _MW_SRC.index("def _apply_word_wrap")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "setLineWrapMode" in block

    def test_loaded_on_init(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # ---", idx + 1)
        block = _MW_SRC[idx:end]
        assert 'self._cfg.get("preview_word_wrap", True)' in block
        assert "_apply_word_wrap(wrap)" in block

    def test_default_is_true(self) -> None:
        assert 'self._cfg.get("preview_word_wrap", True)' in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestWordWrapToggleLogic:
    def test_config_default_absent(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        val = bool(cfg.get("preview_word_wrap", True))
        assert val is True

    def test_config_persists_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_word_wrap", False)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert bool(cfg2.get("preview_word_wrap", True)) is False

    def test_config_persists_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_word_wrap", True)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert bool(cfg2.get("preview_word_wrap", False)) is True


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestWordWrapToggleGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_action_exists(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert hasattr(w, "_word_wrap_action")

    def test_action_checked_by_default(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._word_wrap_action.isChecked()

    def test_toggle_off_changes_wrap_mode(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QTextEdit
        w = self._make_window(tmp_path)
        w._toggle_word_wrap(False)
        assert w._preview_pane.lineWrapMode() == QTextEdit.LineWrapMode.NoWrap

    def test_toggle_on_changes_wrap_mode(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QTextEdit
        w = self._make_window(tmp_path)
        w._toggle_word_wrap(True)
        assert w._preview_pane.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth
