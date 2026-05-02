"""
Tests for FEAT-ocr-log-panel.

gui.qt_log_handler and gui.main_window both import PySide6 at module level.
We use two strategies:

1. QtLogHandler unit tests — the handler itself can be tested without a full
   QApplication by checking its structure and that emit() calls the signal.
   These use source-scan to stay safe.

2. Source-scan tests — verify main_window.py has the correct wiring without
   importing Qt into the test process.

3. GUI tests — @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
_HANDLER_SRC = (_ROOT / "gui" / "qt_log_handler.py").read_text(encoding="utf-8")
_MW_SRC = (_ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. qt_log_handler.py source-scan
# ---------------------------------------------------------------------------

class TestQtLogHandlerSource:
    def test_class_inherits_logging_handler(self) -> None:
        assert "class QtLogHandler(logging.Handler)" in _HANDLER_SRC

    def test_emitter_attribute_present(self) -> None:
        assert "self.emitter = _LogEmitter()" in _HANDLER_SRC

    def test_log_emitter_has_signal(self) -> None:
        assert "message_logged = Signal(str)" in _HANDLER_SRC

    def test_emit_calls_format(self) -> None:
        assert "self.format(record)" in _HANDLER_SRC

    def test_emit_calls_signal_emit(self) -> None:
        assert "message_logged.emit(msg)" in _HANDLER_SRC

    def test_handleError_called_on_exception(self) -> None:
        assert "self.handleError(record)" in _HANDLER_SRC

    def test_level_parameter_in_init(self) -> None:
        assert "def __init__(self, level: int" in _HANDLER_SRC


# ---------------------------------------------------------------------------
# 2. main_window.py source-scan
# ---------------------------------------------------------------------------

class TestMainWindowLogPanelSource:
    def test_qt_log_handler_imported(self) -> None:
        assert "from gui.qt_log_handler import QtLogHandler" in _MW_SRC

    def test_qtextedit_imported(self) -> None:
        assert "QTextEdit" in _MW_SRC

    def test_log_panel_widget_created(self) -> None:
        assert "self._log_panel = QTextEdit()" in _MW_SRC

    def test_log_panel_initially_hidden(self) -> None:
        assert "self._log_panel.setVisible(False)" in _MW_SRC

    def test_log_panel_readonly(self) -> None:
        assert "self._log_panel.setReadOnly(True)" in _MW_SRC

    def test_log_panel_max_height_set(self) -> None:
        assert "self._log_panel.setMaximumHeight" in _MW_SRC

    def test_toggle_log_action_in_view_menu(self) -> None:
        assert '"Show Log Panel"' in _MW_SRC
        assert "self._toggle_log_action" in _MW_SRC

    def test_toggle_log_action_is_checkable(self) -> None:
        assert "self._toggle_log_action.setCheckable(True)" in _MW_SRC

    def test_install_log_handler_called_on_init(self) -> None:
        assert "self._install_log_handler()" in _MW_SRC

    def test_install_log_handler_method_exists(self) -> None:
        assert "def _install_log_handler" in _MW_SRC

    def test_handler_added_to_root_logger(self) -> None:
        assert "logging.getLogger().addHandler(self._log_handler)" in _MW_SRC

    def test_handler_removed_on_close(self) -> None:
        assert "logging.getLogger().removeHandler(self._log_handler)" in _MW_SRC

    def test_toggle_log_panel_slot_exists(self) -> None:
        assert "def _toggle_log_panel" in _MW_SRC

    def test_append_log_slot_exists(self) -> None:
        assert "def _append_log" in _MW_SRC

    def test_append_log_auto_scrolls(self) -> None:
        assert "sb.setValue(sb.maximum())" in _MW_SRC

    def test_message_logged_connected_to_append_log(self) -> None:
        assert "message_logged.connect(self._append_log)" in _MW_SRC

    def test_toggle_label_updates_on_check(self) -> None:
        assert '"Hide Log Panel"' in _MW_SRC

    def test_log_panel_placeholder_text_set(self) -> None:
        assert "setPlaceholderText" in _MW_SRC

    def test_log_panel_uses_monospace_font(self) -> None:
        assert "Courier New" in _MW_SRC


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestLogPanelGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_log_panel_initially_hidden(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._log_panel.isVisible()

    def test_toggle_shows_panel(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._toggle_log_panel(True)
        assert w._log_panel.isVisible()

    def test_toggle_hides_panel(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._toggle_log_panel(True)
        w._toggle_log_panel(False)
        assert not w._log_panel.isVisible()

    def test_toggle_updates_action_label_show(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._toggle_log_panel(True)
        assert w._toggle_log_action.text() == "Hide Log Panel"

    def test_toggle_updates_action_label_hide(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._toggle_log_panel(True)
        w._toggle_log_panel(False)
        assert w._toggle_log_action.text() == "Show Log Panel"

    def test_append_log_adds_text(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._append_log("test message")
        assert "test message" in w._log_panel.toPlainText()

    def test_log_handler_installed_on_root(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        root_handlers = logging.getLogger().handlers
        assert w._log_handler in root_handlers

    def test_log_handler_removed_on_close(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w.close()
        assert w._log_handler not in logging.getLogger().handlers

    def test_real_log_message_appears_in_panel(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._toggle_log_panel(True)
        test_logger = logging.getLogger("test.log.panel")
        test_logger.info("hello from test")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        assert "hello from test" in w._log_panel.toPlainText()
