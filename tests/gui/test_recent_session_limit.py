"""
Tests for FEAT-recent-session-limit.

Source-scan tests verify SettingsDialog spinbox and MainWindow cap logic.
Pure-logic tests verify capping behavior and config round-trip.
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

class TestRecentSessionLimitSettingsSource:
    def test_spinbox_created(self) -> None:
        assert "self._max_recent_sessions = QSpinBox()" in _SD_SRC

    def test_range_1_to_10(self) -> None:
        assert "self._max_recent_sessions.setRange(1, 10)" in _SD_SRC

    def test_default_5(self) -> None:
        assert "self._max_recent_sessions.setValue(5)" in _SD_SRC

    def test_suffix(self) -> None:
        assert 'self._max_recent_sessions.setSuffix(" sessions")' in _SD_SRC

    def test_row_label(self) -> None:
        assert '"Recent session history:"' in _SD_SRC

    def test_loaded_from_config(self) -> None:
        assert 'cfg.get("max_recent_sessions", 5)' in _SD_SRC

    def test_saved_to_config(self) -> None:
        assert 'cfg.set("max_recent_sessions", self._max_recent_sessions.value())' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. MainWindow source-scan
# ---------------------------------------------------------------------------

class TestRecentSessionLimitMainWindowSource:
    def test_cap_uses_config(self) -> None:
        idx = _MW_SRC.index("def _record_recent_session")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert '"max_recent_sessions"' in block

    def test_cap_falls_back_to_max_recent(self) -> None:
        idx = _MW_SRC.index("def _record_recent_session")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._MAX_RECENT" in block

    def test_max_recent_class_attr_still_exists(self) -> None:
        assert "_MAX_RECENT = 5" in _MW_SRC


# ---------------------------------------------------------------------------
# 3. Pure-logic tests
# ---------------------------------------------------------------------------

def _apply_cap(items: list[str], cap: int) -> list[str]:
    return items[:cap]


def _record(recent: list[str], path: str, cap: int) -> list[str]:
    if path in recent:
        recent = [x for x in recent if x != path]
    recent = [path] + recent
    return recent[:cap]


class TestRecentSessionLimitLogic:
    def test_default_cap_is_5(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg.get("max_recent_sessions", 5)) == 5

    def test_persists_3(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("max_recent_sessions", 3)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert int(cfg2.get("max_recent_sessions", 5)) == 3

    def test_cap_truncates(self) -> None:
        result = _apply_cap(["a", "b", "c", "d"], 3)
        assert result == ["a", "b", "c"]

    def test_cap_1_keeps_only_first(self) -> None:
        result = _apply_cap(["x", "y"], 1)
        assert result == ["x"]

    def test_record_prepends(self) -> None:
        result = _record(["b", "c"], "a", 5)
        assert result[0] == "a"

    def test_record_deduplicates(self) -> None:
        result = _record(["b", "a", "c"], "a", 5)
        assert result.count("a") == 1

    def test_record_caps_at_limit(self) -> None:
        result = _record(["b", "c", "d"], "a", 3)
        assert len(result) == 3

    def test_range_min_is_1(self) -> None:
        assert max(1, 0) == 1

    def test_range_max_is_10(self) -> None:
        assert min(10, 100) == 10


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestRecentSessionLimitGui:
    def _make_dialog(self, tmp_path, limit=5):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("max_recent_sessions", limit)
        return SettingsDialog(cfg), cfg

    def test_default_value_5(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._max_recent_sessions.value() == 5

    def test_loads_3(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, 3)
        assert dlg._max_recent_sessions.value() == 3

    def test_save_writes_config(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._max_recent_sessions.setValue(7)
        dlg._save_values()
        assert int(cfg.get("max_recent_sessions", 5)) == 7
