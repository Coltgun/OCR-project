"""
Tests for FEAT-recent-sessions-menu.

Source-scan tests verify _recent_menu, _record_recent_session, _update_recent_menu,
and _open_recent_session structure.
Pure-logic tests verify dedup, cap, and prepend logic.
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

class TestRecentSessionsMenuSource:
    def _record_block(self) -> str:
        idx = _MW_SRC.index("def _record_recent_session")
        end = _MW_SRC.index("\n    def _update_recent_menu", idx + 1)
        return _MW_SRC[idx:end]

    def _update_block(self) -> str:
        idx = _MW_SRC.index("def _update_recent_menu")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        return _MW_SRC[idx:end]

    def _open_block(self) -> str:
        idx = _MW_SRC.index("def _open_recent_session")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        return _MW_SRC[idx:end]

    def test_record_method_exists(self) -> None:
        assert "def _record_recent_session" in _MW_SRC

    def test_record_reads_recent_sessions(self) -> None:
        assert '"recent_sessions"' in self._record_block()

    def test_record_deduplicates(self) -> None:
        assert "recent.remove(path)" in self._record_block()

    def test_record_prepends(self) -> None:
        assert "recent.insert(0, path)" in self._record_block()

    def test_record_caps_at_max(self) -> None:
        assert "recent[:cap]" in self._record_block()

    def test_record_persists(self) -> None:
        assert "self._config.save()" in self._record_block()

    def test_update_menu_method_exists(self) -> None:
        assert "def _update_recent_menu" in _MW_SRC

    def test_update_menu_clears_first(self) -> None:
        assert "self._recent_menu.clear()" in self._update_block()

    def test_update_menu_shows_placeholder_when_empty(self) -> None:
        assert '"(no recent sessions)"' in self._update_block()

    def test_open_recent_session_exists(self) -> None:
        assert "def _open_recent_session" in _MW_SRC

    def test_open_checks_path_exists(self) -> None:
        assert "session_root.exists()" in self._open_block()

    def test_open_warns_if_missing(self) -> None:
        assert "Session not found" in self._open_block()

    def test_max_recent_constant_exists(self) -> None:
        assert "_MAX_RECENT" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestRecentSessionsMenuLogic:
    def _record(self, recent: list, path: str, cap: int) -> list:
        if not isinstance(recent, list):
            recent = []
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        return recent[:cap]

    def test_prepend_new_item(self) -> None:
        result = self._record([], "a", 5)
        assert result[0] == "a"

    def test_dedup_moves_to_front(self) -> None:
        result = self._record(["b", "a"], "a", 5)
        assert result == ["a", "b"]

    def test_cap_enforced(self) -> None:
        recent = ["a", "b", "c"]
        result = self._record(recent, "d", 3)
        assert len(result) == 3
        assert result[0] == "d"

    def test_empty_list_default(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        val = cfg.get("recent_sessions", [])
        assert val == []

    def test_persists_recent_sessions(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("recent_sessions", ["/path/a", "/path/b"])
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("recent_sessions", []) == ["/path/a", "/path/b"]

    def test_max_recent_sessions_default(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg.get("max_recent_sessions", 5)) == 5


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestRecentSessionsMenuGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_recent_menu_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._recent_menu is not None

    def test_empty_recent_shows_placeholder(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        actions = w._recent_menu.actions()
        assert len(actions) == 1
        assert not actions[0].isEnabled()

    def test_record_updates_menu(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._record_recent_session(str(tmp_path))
        actions = w._recent_menu.actions()
        assert any(str(tmp_path) in a.text() for a in actions)
