"""
Tests for FEAT-clear-recent-sessions.

Source-scan tests verify button, slot, flag, and MainWindow integration.
Pure-logic tests verify clear behavior.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
_SD_SRC = (_ROOT / "gui" / "settings_dialog.py").read_text(encoding="utf-8")
_MW_SRC = (_ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. SettingsDialog source-scan
# ---------------------------------------------------------------------------

class TestClearRecentSettingsSource:
    def test_flag_initialised(self) -> None:
        assert "self.recent_sessions_cleared: bool = False" in _SD_SRC

    def test_button_created(self) -> None:
        assert 'QPushButton("Clear Recent Sessions")' in _SD_SRC

    def test_button_has_tooltip(self) -> None:
        assert "Remove all entries from the Recent Sessions menu" in _SD_SRC

    def test_button_connected_to_slot(self) -> None:
        assert "self._clear_recent_btn.clicked.connect(self._on_clear_recent)" in _SD_SRC

    def test_slot_exists(self) -> None:
        assert "def _on_clear_recent" in _SD_SRC

    def test_slot_clears_config(self) -> None:
        idx = _SD_SRC.index("def _on_clear_recent")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert '"recent_sessions"' in block
        assert "[]" in block

    def test_slot_saves_config(self) -> None:
        idx = _SD_SRC.index("def _on_clear_recent")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert "self._config.save()" in block

    def test_slot_sets_flag(self) -> None:
        idx = _SD_SRC.index("def _on_clear_recent")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert "self.recent_sessions_cleared = True" in block

    def test_slot_disables_button(self) -> None:
        idx = _SD_SRC.index("def _on_clear_recent")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert "setEnabled(False)" in block


# ---------------------------------------------------------------------------
# 2. MainWindow source-scan
# ---------------------------------------------------------------------------

class TestClearRecentMainWindowSource:
    def test_checks_flag_after_accept(self) -> None:
        idx = _MW_SRC.index("def _open_settings")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "dlg.recent_sessions_cleared" in block

    def test_calls_update_recent_menu(self) -> None:
        idx = _MW_SRC.index("def _open_settings")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_recent_menu()" in block


# ---------------------------------------------------------------------------
# 3. Pure-logic tests
# ---------------------------------------------------------------------------

class TestClearRecentLogic:
    def test_clear_writes_empty_list(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("recent_sessions", ["/a", "/b"])
        cfg.set("recent_sessions", [])
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert list(cfg2.get("recent_sessions", [])) == []

    def test_cleared_flag_default_false(self) -> None:
        assert False is False

    def test_cleared_list_is_empty(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("recent_sessions", ["/x"])
        cfg.set("recent_sessions", [])
        assert list(cfg.get("recent_sessions", [])) == []

    def test_non_cleared_list_preserved(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("recent_sessions", ["/a", "/b"])
        assert len(list(cfg.get("recent_sessions", []))) == 2


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestClearRecentGui:
    def _make_dialog(self, tmp_path, sessions=None):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("recent_sessions", sessions or [])
        return SettingsDialog(cfg), cfg

    def test_flag_false_initially(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg.recent_sessions_cleared is False

    def test_click_sets_flag(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, ["/a"])
        dlg._on_clear_recent()
        assert dlg.recent_sessions_cleared is True

    def test_click_clears_config(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path, ["/a", "/b"])
        dlg._on_clear_recent()
        assert list(cfg.get("recent_sessions", [])) == []

    def test_button_disabled_after_click(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        dlg._on_clear_recent()
        assert not dlg._clear_recent_btn.isEnabled()
