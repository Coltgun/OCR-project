"""
Tests for FEAT-theme-toggle.

Source-scan tests verify the action, slot, helper, and config wiring without
importing Qt. Config-logic tests verify persistence using ConfigManager
directly. GUI tests are @pytest.mark.gui + @pytest.mark.skip.
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

class TestThemeToggleSource:
    def test_qpalette_imported(self) -> None:
        assert "QPalette" in _MW_SRC

    def test_qcolor_imported(self) -> None:
        assert "QColor" in _MW_SRC

    def test_dark_mode_action_created(self) -> None:
        assert 'self._dark_mode_action = QAction("Dark Mode", self)' in _MW_SRC

    def test_dark_mode_action_checkable(self) -> None:
        assert "self._dark_mode_action.setCheckable(True)" in _MW_SRC

    def test_dark_mode_action_wired_to_slot(self) -> None:
        assert "self._dark_mode_action.triggered.connect(self._toggle_dark_mode)" in _MW_SRC

    def test_dark_mode_action_in_view_menu(self) -> None:
        idx = _MW_SRC.index('view_menu = menu_bar.addMenu("&View")')
        end = _MW_SRC.index('tools_menu = menu_bar.addMenu("&Tools")', idx)
        block = _MW_SRC[idx:end]
        assert "self._dark_mode_action" in block

    def test_preference_loaded_on_init(self) -> None:
        assert 'self._cfg.get("dark_mode", False)' in _MW_SRC

    def test_apply_theme_called_on_init(self) -> None:
        assert "self._apply_theme(dark)" in _MW_SRC

    def test_toggle_dark_mode_slot_exists(self) -> None:
        assert "def _toggle_dark_mode" in _MW_SRC

    def test_toggle_persists_to_config(self) -> None:
        assert 'self._config.set("dark_mode", checked)' in _MW_SRC

    def test_toggle_saves_config(self) -> None:
        idx = _MW_SRC.index("def _toggle_dark_mode")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._config.save()" in block

    def test_apply_theme_method_exists(self) -> None:
        assert "def _apply_theme" in _MW_SRC

    def test_apply_theme_uses_fusion_style(self) -> None:
        assert 'app.setStyle("Fusion")' in _MW_SRC

    def test_apply_theme_sets_dark_palette(self) -> None:
        assert "app.setPalette(palette)" in _MW_SRC

    def test_apply_theme_restores_standard_palette(self) -> None:
        assert "app.style().standardPalette()" in _MW_SRC

    def test_apply_theme_guards_none_app(self) -> None:
        assert "if app is None:" in _MW_SRC

    def test_dark_window_colour_set(self) -> None:
        assert "ColorRole.Window" in _MW_SRC

    def test_dark_text_colour_set(self) -> None:
        assert "ColorRole.Text" in _MW_SRC

    def test_dark_highlight_colour_set(self) -> None:
        assert "ColorRole.Highlight" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Config-logic tests (no Qt)
# ---------------------------------------------------------------------------

class TestThemePersistence:
    def test_dark_mode_false_by_default(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("dark_mode", False) is False

    def test_dark_mode_persisted_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", True)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("dark_mode", False) is True

    def test_dark_mode_persisted_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", True)
        cfg.save()
        cfg.set("dark_mode", False)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("dark_mode", True) is False


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestThemeToggleGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg), cfg

    def test_dark_mode_action_initially_unchecked(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        assert not w._dark_mode_action.isChecked()

    def test_dark_mode_action_checked_from_config(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", True)
        cfg.save()
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow(cfg)
        assert w._dark_mode_action.isChecked()

    def test_toggle_dark_persists_to_config(self, tmp_path: Path) -> None:
        w, cfg = self._make_window(tmp_path)
        w._toggle_dark_mode(True)
        assert cfg.get("dark_mode", False) is True

    def test_toggle_light_persists_to_config(self, tmp_path: Path) -> None:
        w, cfg = self._make_window(tmp_path)
        w._toggle_dark_mode(True)
        w._toggle_dark_mode(False)
        assert cfg.get("dark_mode", True) is False

    def test_apply_dark_sets_palette(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QColor
        w, _ = self._make_window(tmp_path)
        w._apply_theme(True)
        app = QApplication.instance()
        bg = app.palette().color(app.palette().ColorRole.Window)
        assert bg == QColor(45, 45, 45)

    def test_apply_light_restores_palette(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QApplication
        w, _ = self._make_window(tmp_path)
        w._apply_theme(True)
        w._apply_theme(False)
        app = QApplication.instance()
        expected = app.style().standardPalette().color(app.palette().ColorRole.Window)
        assert app.palette().color(app.palette().ColorRole.Window) == expected
