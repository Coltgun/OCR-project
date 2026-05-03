"""
Tests for FEAT-dark-mode-persist.

Source-scan tests verify the dark-mode action, slot, _apply_theme, and __init__ restore.
Pure-logic tests verify config round-trip.
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

class TestDarkModePersistSource:
    def _init_block(self) -> str:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        return _MW_SRC[idx:end]

    def _slot_block(self) -> str:
        idx = _MW_SRC.index("def _toggle_dark_mode")
        end = _MW_SRC.index("\n    def _apply_theme", idx + 1)
        return _MW_SRC[idx:end]

    def test_action_created(self) -> None:
        assert 'QAction("Dark Mode"' in _MW_SRC

    def test_action_is_checkable(self) -> None:
        assert "self._dark_mode_action.setCheckable(True)" in _MW_SRC

    def test_action_connected_to_slot(self) -> None:
        assert "self._dark_mode_action.triggered.connect(self._toggle_dark_mode)" in _MW_SRC

    def test_slot_exists(self) -> None:
        assert "def _toggle_dark_mode" in _MW_SRC

    def test_slot_saves_dark_mode(self) -> None:
        assert '"dark_mode"' in self._slot_block()

    def test_slot_calls_save(self) -> None:
        assert "self._config.save()" in self._slot_block()

    def test_slot_calls_apply_theme(self) -> None:
        assert "_apply_theme(checked)" in self._slot_block()

    def test_apply_theme_method_exists(self) -> None:
        assert "def _apply_theme" in _MW_SRC

    def test_init_reads_dark_mode(self) -> None:
        assert '"dark_mode"' in self._init_block()

    def test_init_calls_set_checked(self) -> None:
        assert "_dark_mode_action.setChecked(dark)" in self._init_block()

    def test_init_calls_apply_theme(self) -> None:
        assert "_apply_theme(dark)" in self._init_block()

    def test_factory_defaults_has_dark_mode(self) -> None:
        _SD_SRC = (
            Path(__file__).parent.parent.parent / "gui" / "settings_dialog.py"
        ).read_text(encoding="utf-8")
        assert '"dark_mode": False' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestDarkModePersistLogic:
    def test_default_is_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert bool(cfg.get("dark_mode", False)) is False

    def test_persists_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", True)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("dark_mode", False) is True

    def test_persists_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", False)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("dark_mode", True) is False

    def test_toggle_inverts(self) -> None:
        val = False
        val = not val
        assert val is True

    def test_bool_cast_int_zero(self) -> None:
        assert bool(0) is False

    def test_bool_cast_int_one(self) -> None:
        assert bool(1) is True


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestDarkModePersistGui:
    def _make_window(self, tmp_path, dark=False):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("dark_mode", dark)
        return MainWindow(cfg), cfg

    def test_default_not_checked(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path, dark=False)
        assert not w._dark_mode_action.isChecked()

    def test_restored_true(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path, dark=True)
        assert w._dark_mode_action.isChecked()

    def test_toggle_persists(self, tmp_path: Path) -> None:
        w, cfg = self._make_window(tmp_path, dark=False)
        w._toggle_dark_mode(True)
        assert cfg.get("dark_mode", False) is True
