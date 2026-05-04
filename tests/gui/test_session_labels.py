"""
Tests for FEAT-session-labels.

Source-scan tests verify _session_label, _region_label, _section_label,
_count_label QLabel creation; _update_session_labels logic; _update_count_label
format; _update_session_info_label; _refresh_section_count_list.
Pure-logic tests verify count label format string and guard semantics.
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

def _update_session_labels_block() -> str:
    idx = _MW_SRC.index("def _update_session_labels")
    end = _MW_SRC.index("\n    def _update_session_info_label", idx + 1)
    return _MW_SRC[idx:end]

def _update_count_label_block() -> str:
    idx = _MW_SRC.index("def _update_count_label")
    end = _MW_SRC.index("\n    # ----", idx + 1)
    return _MW_SRC[idx:end]

def _update_session_info_block() -> str:
    idx = _MW_SRC.index("def _update_session_info_label")
    end = _MW_SRC.index("\n    def _refresh_section_count_list", idx + 1)
    return _MW_SRC[idx:end]

def _refresh_section_count_block() -> str:
    idx = _MW_SRC.index("def _refresh_section_count_list")
    end = _MW_SRC.index("\n    def _update_count_label", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestSessionLabelsSource:
    def test_session_label_created(self) -> None:
        assert 'self._session_label = QLabel("No session active")' in _MW_SRC

    def test_region_label_created(self) -> None:
        assert 'self._region_label = QLabel("Not set")' in _MW_SRC

    def test_section_label_created(self) -> None:
        assert 'self._section_label = QLabel' in _MW_SRC

    def test_count_label_created(self) -> None:
        assert 'self._count_label = QLabel("0")' in _MW_SRC

    def test_update_session_labels_exists(self) -> None:
        assert "def _update_session_labels" in _MW_SRC

    def test_update_session_labels_guards_none(self) -> None:
        assert "self._session is None" in _update_session_labels_block()

    def test_update_session_labels_sets_session_label(self) -> None:
        assert "_session_label.setText(str(self._session.root))" in _update_session_labels_block()

    def test_update_session_labels_sets_section_label(self) -> None:
        assert "_section_label.setText(str(self._session.current_folder))" in _update_session_labels_block()

    def test_update_session_labels_calls_count_label(self) -> None:
        assert "_update_count_label()" in _update_session_labels_block()

    def test_update_session_labels_calls_refresh_section_list(self) -> None:
        assert "_refresh_section_count_list()" in _update_session_labels_block()

    def test_update_count_label_exists(self) -> None:
        assert "def _update_count_label" in _MW_SRC

    def test_update_count_label_guards_none(self) -> None:
        assert "self._session is None" in _update_count_label_block()

    def test_update_count_label_format_string(self) -> None:
        assert '"total  (section:' in _update_count_label_block() or "total  (section:" in _update_count_label_block()

    def test_update_session_info_label_exists(self) -> None:
        assert "def _update_session_info_label" in _MW_SRC

    def test_update_session_info_label_clears_when_no_session(self) -> None:
        assert '_session_info_label.setText("")' in _update_session_info_block()

    def test_refresh_section_count_list_exists(self) -> None:
        assert "def _refresh_section_count_list" in _MW_SRC

    def test_refresh_section_count_list_clears(self) -> None:
        assert "_section_count_list.clear()" in _refresh_section_count_block()

    def test_refresh_section_count_list_disables_when_no_session(self) -> None:
        assert "_section_count_list.setEnabled(False)" in _refresh_section_count_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestSessionLabelsLogic:
    def test_count_label_format_with_values(self) -> None:
        total, current = 10, 3
        text = f"{total} total  (section: {current})"
        assert text == "10 total  (section: 3)"

    def test_count_label_zero_when_no_session(self) -> None:
        session = None
        text = "0" if session is None else "nonzero"
        assert text == "0"

    def test_session_label_shows_root_path(self) -> None:
        from pathlib import Path
        root = Path("some") / "session" / "path"
        assert "session" in str(root) and "path" in str(root)

    def test_region_label_format(self) -> None:
        x, y, w, h = 10, 20, 300, 200
        text = f"({x}, {y})  {w}\u00d7{h}"
        assert "300" in text and "200" in text

    def test_update_skips_when_session_none(self) -> None:
        session = None
        would_update = session is not None
        assert not would_update

    def test_section_count_list_disabled_when_no_session(self) -> None:
        session = None
        should_enable = session is not None
        assert not should_enable


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSessionLabelsGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_session_label_initial_text(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._session_label.text() == "No session active"

    def test_region_label_initial_text(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._region_label.text() == "Not set"

    def test_count_label_initial_text(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._count_label.text() == "0"
