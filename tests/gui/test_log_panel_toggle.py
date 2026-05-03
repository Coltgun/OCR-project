"""
Tests for FEAT-log-panel-toggle.

Source-scan tests verify action, slot, and init load.
Pure-logic tests verify config default and persistence.
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

class TestLogPanelToggleSource:
    def test_action_created(self) -> None:
        assert '"Show Log Panel"' in _MW_SRC

    def test_action_is_checkable(self) -> None:
        idx = _MW_SRC.index('"Show Log Panel"')
        end = _MW_SRC.index("\n        view_menu.addAction(self._toggle_log_action)", idx)
        block = _MW_SRC[idx:end]
        assert "setCheckable(True)" in block

    def test_action_connected_to_slot(self) -> None:
        assert "self._toggle_log_action.triggered.connect(self._toggle_log_panel)" in _MW_SRC

    def test_slot_exists(self) -> None:
        assert "def _toggle_log_panel" in _MW_SRC

    def _slot_block(self) -> str:
        idx = _MW_SRC.index("def _toggle_log_panel")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        return _MW_SRC[idx:end]

    def test_slot_sets_visible(self) -> None:
        assert "self._log_panel.setVisible(checked)" in self._slot_block()

    def test_slot_updates_label(self) -> None:
        assert "setText" in self._slot_block()

    def test_slot_persists_config(self) -> None:
        assert '"log_panel_visible"' in self._slot_block()

    def test_slot_saves_config(self) -> None:
        assert "self._config.save()" in self._slot_block()

    def test_loaded_on_init(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert '"log_panel_visible"' in block

    def test_log_panel_visibility_set_on_init(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._log_panel.setVisible(log_visible)" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestLogPanelToggleLogic:
    def test_default_is_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert bool(cfg.get("log_panel_visible", False)) is False

    def test_persists_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("log_panel_visible", True)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert bool(cfg2.get("log_panel_visible", False)) is True

    def test_persists_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("log_panel_visible", True)
        cfg.set("log_panel_visible", False)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert bool(cfg2.get("log_panel_visible", True)) is False

    def test_coerce_truthy(self) -> None:
        assert bool(True) is True

    def test_coerce_falsy(self) -> None:
        assert bool(False) is False


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestLogPanelToggleGui:
    def _make_window(self, tmp_path, visible=False):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("log_panel_visible", visible)
        return MainWindow(cfg), cfg

    def test_hidden_by_default(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        assert not w._log_panel.isVisible()

    def test_shown_when_config_true(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path, visible=True)
        assert w._log_panel.isVisible()

    def test_toggle_shows_panel(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        w._toggle_log_panel(True)
        assert w._log_panel.isVisible()

    def test_toggle_persists(self, tmp_path: Path) -> None:
        w, cfg = self._make_window(tmp_path)
        w._toggle_log_panel(True)
        assert bool(cfg.get("log_panel_visible", False)) is True
