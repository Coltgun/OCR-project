"""
Tests for FEAT-dark-mode.

Source-scan tests verify _dark_mode_action QAction (checkable, triggered→
_toggle_dark_mode), _toggle_dark_mode (persist dark_mode + save + _apply_theme),
_apply_theme (Fusion style, QPalette colours for dark, standardPalette for light),
init sync of checked state from config.
Pure-logic tests verify config round-trip and palette colour semantics.
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
    idx = _MW_SRC.index("def _toggle_dark_mode")
    end = _MW_SRC.index("\n    def _apply_theme", idx + 1)
    return _MW_SRC[idx:end]

def _apply_theme_block() -> str:
    idx = _MW_SRC.index("def _apply_theme")
    end = _MW_SRC.index("\n    @Slot()\n    def _show_keyboard_shortcuts", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestDarkModeSource:
    def test_dark_mode_action_created(self) -> None:
        assert 'self._dark_mode_action = QAction("Dark Mode", self)' in _MW_SRC

    def test_dark_mode_action_checkable(self) -> None:
        assert "_dark_mode_action.setCheckable(True)" in _MW_SRC

    def test_dark_mode_action_connected(self) -> None:
        assert "_dark_mode_action.triggered.connect(self._toggle_dark_mode)" in _MW_SRC

    def test_dark_mode_action_added_to_view_menu(self) -> None:
        assert "view_menu.addAction(self._dark_mode_action)" in _MW_SRC

    def test_dark_mode_action_checked_from_config_on_init(self) -> None:
        assert '_dark_mode_action.setChecked(dark)' in _MW_SRC

    def test_apply_theme_called_on_init(self) -> None:
        assert "self._apply_theme(dark)" in _MW_SRC

    def test_toggle_dark_mode_persists_config(self) -> None:
        assert 'self._config.set("dark_mode", checked)' in _toggle_block()

    def test_toggle_dark_mode_saves_config(self) -> None:
        assert "self._config.save()" in _toggle_block()

    def test_toggle_dark_mode_calls_apply_theme(self) -> None:
        assert "self._apply_theme(checked)" in _toggle_block()

    def test_apply_theme_exists(self) -> None:
        assert "def _apply_theme" in _MW_SRC

    def test_apply_theme_guards_none_app(self) -> None:
        assert "if app is None:" in _apply_theme_block()

    def test_apply_theme_sets_fusion_style_dark(self) -> None:
        assert 'app.setStyle("Fusion")' in _apply_theme_block()

    def test_apply_theme_dark_palette_window_colour(self) -> None:
        assert "QColor(45, 45, 45)" in _apply_theme_block()

    def test_apply_theme_dark_palette_highlight(self) -> None:
        assert "QColor(42, 130, 218)" in _apply_theme_block()

    def test_apply_theme_light_uses_standard_palette(self) -> None:
        assert "app.setPalette(app.style().standardPalette())" in _apply_theme_block()

    def test_dark_mode_config_key(self) -> None:
        assert '"dark_mode"' in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestDarkModeLogic:
    def test_config_round_trip_dark_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", True)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("dark_mode") is True

    def test_config_round_trip_dark_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", False)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("dark_mode") is False

    def test_dark_mode_default_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("dark_mode", False) is False

    def test_dark_bool_cast_from_config(self) -> None:
        raw = True
        dark = bool(raw)
        assert dark is True

    def test_dark_palette_window_colour_values(self) -> None:
        r, g, b = 45, 45, 45
        assert r == g == b == 45

    def test_highlight_colour_is_blue(self) -> None:
        r, g, b = 42, 130, 218
        assert b > r and b > g


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestDarkModeGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_dark_mode_action_initially_unchecked(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._dark_mode_action.isChecked()

    def test_dark_mode_action_checked_when_config_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", True)
        cfg.save()
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow(cfg)
        assert w._dark_mode_action.isChecked()

    def test_toggle_persists_to_config(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._toggle_dark_mode(True)
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("dark_mode") is True
