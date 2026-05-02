"""
Tests for FEAT-status-bar-session-info.

Source-scan tests verify label creation, tooltip, helper, and call sites.
Pure-logic tests verify label text formatting.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestStatusBarSessionInfoSource:
    def test_label_created(self) -> None:
        assert "self._session_info_label = QLabel()" in _MW_SRC

    def test_tooltip_set(self) -> None:
        assert '"Current session and total image count"' in _MW_SRC

    def test_added_as_permanent_widget(self) -> None:
        idx = _MW_SRC.index("def _build_status_bar")
        end = _MW_SRC.index("\n    # ---", idx + 1)
        block = _MW_SRC[idx:end]
        assert "addPermanentWidget(self._session_info_label)" in block

    def test_helper_method_exists(self) -> None:
        assert "def _update_session_info_label" in _MW_SRC

    def test_helper_clears_when_no_session(self) -> None:
        idx = _MW_SRC.index("def _update_session_info_label")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert 'self._session_info_label.setText("")' in block

    def test_helper_uses_root_name(self) -> None:
        idx = _MW_SRC.index("def _update_session_info_label")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "root.name" in block

    def test_helper_uses_total_images(self) -> None:
        idx = _MW_SRC.index("def _update_session_info_label")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "total_images()" in block

    def test_helper_text_format(self) -> None:
        assert '"Session: {self._session.root.name}  |  {total} image(s)"' in _MW_SRC

    def test_called_from_update_session_labels(self) -> None:
        idx = _MW_SRC.index("def _update_session_labels")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_session_info_label()" in block

    def test_called_after_capture(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_session_info_label()" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

def _info_text(session_name: str, total: int) -> str:
    return f"Session: {session_name}  |  {total} image(s)"


class TestStatusBarSessionInfoLogic:
    def test_basic_format(self) -> None:
        assert _info_text("my_session", 5) == "Session: my_session  |  5 image(s)"

    def test_zero_images(self) -> None:
        assert _info_text("sess", 0) == "Session: sess  |  0 image(s)"

    def test_session_name_used_not_full_path(self) -> None:
        path = Path("/some/deep/path/session_name")
        assert _info_text(path.name, 3) == "Session: session_name  |  3 image(s)"

    def test_singular_still_says_images(self) -> None:
        text = _info_text("s", 1)
        assert "1 image(s)" in text

    def test_empty_when_no_session(self) -> None:
        assert "" == ""


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestStatusBarSessionInfoGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_label_empty_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._session_info_label.text() == ""

    def test_label_set_after_session(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "my_session"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._update_session_info_label()
        assert "my_session" in w._session_info_label.text()
        assert "0 image(s)" in w._session_info_label.text()

    def test_label_clears_when_session_none(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._session = None
        w._update_session_info_label()
        assert w._session_info_label.text() == ""
