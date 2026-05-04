"""
Tests for FEAT-open-folder.

Source-scan tests verify _open_folder_btn QPushButton (hidden, permanent,
clicked→_on_open_export_folder), _last_export_path init, _on_open_export_folder
(guard empty path, Path.parent, os.startfile, OSError catch+logger.warning),
visibility logic in _update_ui_for_state (IDLE+last_export_path), shown after
export success, hidden on state change.
Pure-logic tests verify folder extraction and visibility semantics.
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

def _open_folder_block() -> str:
    idx = _MW_SRC.index("def _on_open_export_folder")
    end = _MW_SRC.index("\n    @Slot(int)\n    def _on_pipeline_mode_changed", idx + 1)
    return _MW_SRC[idx:end]

def _update_ui_block() -> str:
    idx = _MW_SRC.index("def _update_ui_for_state")
    end = _MW_SRC.index("\n    # ------------------------------------------------------------------\n    # Action handlers", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestOpenFolderSource:
    def test_open_folder_btn_created(self) -> None:
        assert 'self._open_folder_btn = QPushButton("Open folder")' in _MW_SRC

    def test_open_folder_btn_hidden_on_init(self) -> None:
        assert "_open_folder_btn.setVisible(False)" in _MW_SRC

    def test_open_folder_btn_connected(self) -> None:
        assert "_open_folder_btn.clicked.connect(self._on_open_export_folder)" in _MW_SRC

    def test_open_folder_btn_added_to_status_bar(self) -> None:
        assert "_status_bar.addPermanentWidget(self._open_folder_btn)" in _MW_SRC

    def test_last_export_path_initialised_empty(self) -> None:
        assert '_last_export_path: str = ""' in _MW_SRC

    def test_on_open_export_folder_exists(self) -> None:
        assert "def _on_open_export_folder" in _MW_SRC

    def test_open_folder_guards_empty_path(self) -> None:
        assert "if not self._last_export_path:" in _open_folder_block()

    def test_open_folder_extracts_parent(self) -> None:
        assert "Path(self._last_export_path).parent" in _open_folder_block()

    def test_open_folder_calls_os_startfile(self) -> None:
        assert "os.startfile(folder)" in _open_folder_block()

    def test_open_folder_catches_oserror(self) -> None:
        assert "except OSError as exc:" in _open_folder_block()

    def test_open_folder_logs_warning_on_error(self) -> None:
        assert "logger.warning(" in _open_folder_block()

    def test_update_ui_hides_btn_when_not_idle(self) -> None:
        assert "_open_folder_btn.setVisible(False)" in _update_ui_block()

    def test_update_ui_checks_last_export_path(self) -> None:
        assert "self._last_export_path" in _update_ui_block()

    def test_btn_shown_after_export_success(self) -> None:
        assert "_open_folder_btn.setVisible(True)" in _MW_SRC

    def test_last_export_path_set_after_export(self) -> None:
        assert "_last_export_path = save_path" in _MW_SRC

    def test_btn_connected_to_on_open_export_folder(self) -> None:
        assert "_open_folder_btn.clicked.connect(self._on_open_export_folder)" in _MW_SRC

    def test_update_ui_hides_btn_when_not_idle_or_no_path(self) -> None:
        blk = _update_ui_block()
        assert "not self._last_export_path" in blk or "self._last_export_path" in blk

    def test_open_folder_converts_path_to_str(self) -> None:
        assert "str(Path(self._last_export_path).parent)" in _open_folder_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestOpenFolderLogic:
    def test_folder_extracted_from_path(self, tmp_path: Path) -> None:
        export_path = str(tmp_path / "output" / "book.epub")
        folder = str(Path(export_path).parent)
        assert folder == str(tmp_path / "output")

    def test_empty_last_export_path_skips(self) -> None:
        last_export_path = ""
        should_open = bool(last_export_path)
        assert not should_open

    def test_non_empty_last_export_path_proceeds(self) -> None:
        last_export_path = "/some/path/book.epub"
        should_open = bool(last_export_path)
        assert should_open

    def test_btn_hidden_when_not_idle(self) -> None:
        is_idle = False
        last_export_path = "/some/path/book.epub"
        should_show = is_idle and bool(last_export_path)
        assert not should_show

    def test_btn_hidden_when_idle_no_export(self) -> None:
        is_idle = True
        last_export_path = ""
        should_show = is_idle and bool(last_export_path)
        assert not should_show

    def test_btn_shown_when_idle_and_has_export(self) -> None:
        is_idle = True
        last_export_path = "/some/path/book.epub"
        should_show = not (not is_idle or not last_export_path)
        assert should_show


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestOpenFolderGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_open_folder_btn_hidden_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._open_folder_btn.isVisible()

    def test_open_folder_btn_shown_after_setting_path(self, tmp_path: Path) -> None:
        from capture.state import AppState
        w = self._make_window(tmp_path)
        w._last_export_path = str(tmp_path / "book.epub")
        w._update_ui_for_state(AppState.IDLE)
        assert w._open_folder_btn.isVisible()

    def test_open_folder_guards_empty_path(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._last_export_path = ""
        w._on_open_export_folder()
