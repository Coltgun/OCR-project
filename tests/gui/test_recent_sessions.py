"""
Tests for FEAT-recent-sessions.

Source-scan tests verify menu creation, wiring, and helper existence.
Pure-logic tests verify the list-management algorithm.
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

class TestRecentSessionsSource:
    def test_recent_menu_created(self) -> None:
        assert 'self._recent_menu = file_menu.addMenu("Recent Sessions")' in _MW_SRC

    def test_update_recent_menu_exists(self) -> None:
        assert "def _update_recent_menu" in _MW_SRC

    def test_record_recent_session_exists(self) -> None:
        assert "def _record_recent_session" in _MW_SRC

    def test_open_recent_session_exists(self) -> None:
        assert "def _open_recent_session" in _MW_SRC

    def test_record_called_on_new_session(self) -> None:
        idx = _MW_SRC.index("def _start_new_session")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_record_recent_session" in block

    def test_update_recent_called_on_init(self) -> None:
        assert "self._update_recent_menu()" in _MW_SRC

    def test_max_recent_constant_defined(self) -> None:
        assert "_MAX_RECENT = 5" in _MW_SRC

    def test_recent_sessions_config_key(self) -> None:
        assert '"recent_sessions"' in _MW_SRC

    def test_menu_cleared_on_rebuild(self) -> None:
        assert "self._recent_menu.clear()" in _MW_SRC

    def test_placeholder_when_empty(self) -> None:
        assert '"(no recent sessions)"' in _MW_SRC

    def test_placeholder_disabled(self) -> None:
        assert "placeholder.setEnabled(False)" in _MW_SRC

    def test_duplicate_removed_before_insert(self) -> None:
        assert "recent.remove(path)" in _MW_SRC

    def test_list_capped_at_max_recent(self) -> None:
        assert "recent[:cap]" in _MW_SRC

    def test_config_saved_after_record(self) -> None:
        idx = _MW_SRC.index("def _record_recent_session")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._config.save()" in block

    def test_open_recent_guards_nonexistent_path(self) -> None:
        assert "not session_root.exists()" in _MW_SRC

    def test_open_recent_shows_warning_for_missing(self) -> None:
        assert "QMessageBox.warning" in _MW_SRC

    def test_open_recent_resumes_session(self) -> None:
        idx = _MW_SRC.index("def _open_recent_session")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "resume=True" in block

    def test_open_recent_guards_not_idle(self) -> None:
        idx = _MW_SRC.index("def _open_recent_session")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._state_machine.is_idle" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests (no Qt)
# ---------------------------------------------------------------------------

def _apply_record(recent: list, path: str, max_recent: int = 5) -> list:
    """Mirrors the logic in _record_recent_session."""
    if not isinstance(recent, list):
        recent = []
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    return recent[:max_recent]


class TestRecentSessionsLogic:
    def test_new_path_prepended(self) -> None:
        result = _apply_record([], "path/a")
        assert result[0] == "path/a"

    def test_duplicate_moved_to_front(self) -> None:
        result = _apply_record(["path/a", "path/b"], "path/b")
        assert result == ["path/b", "path/a"]

    def test_capped_at_five(self) -> None:
        existing = [f"path/{i}" for i in range(5)]
        result = _apply_record(existing, "path/new")
        assert len(result) == 5
        assert result[0] == "path/new"

    def test_existing_five_drops_last(self) -> None:
        existing = ["a", "b", "c", "d", "e"]
        result = _apply_record(existing, "z")
        assert "e" not in result

    def test_non_list_treated_as_empty(self) -> None:
        result = _apply_record("not-a-list", "path/a")  # type: ignore[arg-type]
        assert result == ["path/a"]

    def test_order_preserved_for_three_unique(self) -> None:
        r = _apply_record([], "c")
        r = _apply_record(r, "b")
        r = _apply_record(r, "a")
        assert r == ["a", "b", "c"]

    def test_config_persistence(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        recent = _apply_record([], "session1")
        cfg.set("recent_sessions", recent)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        loaded = list(cfg2.get("recent_sessions", []))  # type: ignore[arg-type]
        assert loaded == ["session1"]


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestRecentSessionsGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg), cfg

    def test_recent_menu_initially_has_placeholder(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        actions = w._recent_menu.actions()
        assert len(actions) == 1
        assert not actions[0].isEnabled()

    def test_record_adds_action_to_menu(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        w._record_recent_session("fake/path")
        actions = w._recent_menu.actions()
        assert len(actions) == 1
        assert actions[0].text() == "fake/path"

    def test_record_deduplicates_in_menu(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        w._record_recent_session("fake/path")
        w._record_recent_session("fake/path")
        assert len(w._recent_menu.actions()) == 1

    def test_record_capped_at_five_in_menu(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        for i in range(7):
            w._record_recent_session(f"path/{i}")
        assert len(w._recent_menu.actions()) == 5

    def test_open_recent_missing_path_shows_warning(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        w, _ = self._make_window(tmp_path)
        with patch("gui.main_window.QMessageBox.warning") as mock_warn:
            w._open_recent_session("/nonexistent/path")
            mock_warn.assert_called_once()

    def test_open_recent_valid_path_starts_session(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "s1"
        session_root.mkdir()
        w, _ = self._make_window(tmp_path)
        w._open_recent_session(str(session_root))
        assert w._session is not None
        assert w._session.root == session_root
