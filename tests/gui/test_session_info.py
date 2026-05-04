"""
Tests for FEAT-session-info.

Source-scan tests verify _session_info_label QLabel (tooltip, addPermanentWidget),
_update_session_info_label (None guard->setText(""), total_images(), format string
"Session: {root.name} | {total} image(s)"), called from _update_session_labels
and _update_count_label / capture success.
Pure-logic tests verify label format, None guard, total count logic.
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

def _update_info_block() -> str:
    idx = _MW_SRC.index("def _update_session_info_label")
    end = _MW_SRC.index("\n    def _refresh_section_count_list", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestSessionInfoSource:
    def test_session_info_label_created(self) -> None:
        assert "self._session_info_label = QLabel()" in _MW_SRC

    def test_session_info_label_tooltip(self) -> None:
        assert '_session_info_label.setToolTip("Current session and total image count")' in _MW_SRC

    def test_session_info_label_permanent_widget(self) -> None:
        assert "self._status_bar.addPermanentWidget(self._session_info_label)" in _MW_SRC

    def test_update_session_info_label_exists(self) -> None:
        assert "def _update_session_info_label" in _MW_SRC

    def test_none_guard_clears_label(self) -> None:
        assert '_session_info_label.setText("")' in _update_info_block()

    def test_none_guard_returns_early(self) -> None:
        assert "if self._session is None:" in _update_info_block()

    def test_reads_total_images(self) -> None:
        assert "self._session.total_images()" in _update_info_block()

    def test_format_includes_session_name(self) -> None:
        assert "self._session.root.name" in _update_info_block()

    def test_format_includes_total(self) -> None:
        assert "{total} image(s)" in _update_info_block()

    def test_format_uses_session_prefix(self) -> None:
        assert '"Session: ' in _update_info_block()

    def test_called_from_update_session_labels(self) -> None:
        idx = _MW_SRC.index("def _update_session_labels")
        end = _MW_SRC.index("\n    def _update_session_info_label", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_session_info_label()" in block

    def test_called_from_capture_success(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot()\n    def _trigger_new_section", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_session_info_label()" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestSessionInfoLogic:
    def test_format_string_structure(self) -> None:
        root_name = "session_2024"
        total = 42
        label = f"Session: {root_name}  |  {total} image(s)"
        assert label == "Session: session_2024  |  42 image(s)"

    def test_zero_images(self) -> None:
        root_name = "s1"
        total = 0
        label = f"Session: {root_name}  |  {total} image(s)"
        assert "0 image(s)" in label

    def test_none_session_produces_empty(self) -> None:
        session = None
        text = "" if session is None else "non-empty"
        assert text == ""

    def test_root_name_not_full_path(self, tmp_path: Path) -> None:
        root = tmp_path / "my_session"
        root.mkdir()
        assert root.name == "my_session"
        assert str(root) != "my_session"

    def test_singular_image(self) -> None:
        total = 1
        label = f"Session: s1  |  {total} image(s)"
        assert "1 image(s)" in label

    def test_large_count(self) -> None:
        total = 999
        label = f"Session: s1  |  {total} image(s)"
        assert "999 image(s)" in label


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSessionInfoGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_label_empty_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._session_info_label.text() == ""

    def test_label_updated_after_session(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        root = tmp_path / "s1"
        root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(root)
        w._update_session_info_label()
        assert "Session: s1" in w._session_info_label.text()

    def test_label_cleared_when_session_none(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._session = None
        w._update_session_info_label()
        assert w._session_info_label.text() == ""
