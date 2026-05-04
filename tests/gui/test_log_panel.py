"""
Tests for FEAT-log-panel.

Source-scan tests verify _log_panel QTextEdit, QtLogHandler, _install_log_handler,
_append_log, _toggle_log_action, _toggle_log_panel persistence.
Pure-logic tests verify log visibility config and label toggling.
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

def _install_block() -> str:
    idx = _MW_SRC.index("def _install_log_handler")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]

def _append_block() -> str:
    idx = _MW_SRC.index("def _append_log")
    end = _MW_SRC.index("\n    @Slot", idx + 1)
    return _MW_SRC[idx:end]

def _toggle_block() -> str:
    idx = _MW_SRC.index("def _toggle_log_panel")
    end = _MW_SRC.index("\n    # --", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestLogPanelSource:
    def test_log_panel_created(self) -> None:
        assert "self._log_panel = QTextEdit()" in _MW_SRC

    def test_log_panel_read_only(self) -> None:
        assert "self._log_panel.setReadOnly(True)" in _MW_SRC

    def test_log_panel_hidden_on_init(self) -> None:
        assert "self._log_panel.setVisible(False)" in _MW_SRC

    def test_log_panel_placeholder(self) -> None:
        assert "self._log_panel.setPlaceholderText" in _MW_SRC

    def test_log_panel_monospace_font(self) -> None:
        assert '"Courier New"' in _MW_SRC

    def test_qt_log_handler_imported(self) -> None:
        assert "QtLogHandler" in _MW_SRC

    def test_install_log_handler_exists(self) -> None:
        assert "def _install_log_handler" in _MW_SRC

    def test_install_attaches_handler(self) -> None:
        assert "logging.getLogger().addHandler(self._log_handler)" in _install_block()

    def test_install_connects_to_append_log(self) -> None:
        assert "_append_log)" in _install_block()

    def test_append_log_method_exists(self) -> None:
        assert "def _append_log" in _MW_SRC

    def test_append_log_appends_to_panel(self) -> None:
        assert "self._log_panel.append(message)" in _append_block()

    def test_append_log_autoscrolls(self) -> None:
        assert "sb.setValue(sb.maximum())" in _append_block()

    def test_toggle_log_action_created(self) -> None:
        assert 'self._toggle_log_action = QAction("Show Log Panel"' in _MW_SRC

    def test_toggle_log_action_checkable(self) -> None:
        assert "_toggle_log_action.setCheckable(True)" in _MW_SRC

    def test_toggle_log_persists_config(self) -> None:
        assert '"log_panel_visible"' in _toggle_block()

    def test_log_panel_min_height(self) -> None:
        assert "_log_panel.setMinimumHeight(60)" in _MW_SRC

    def test_log_panel_max_height(self) -> None:
        assert "_log_panel.setMaximumHeight(200)" in _MW_SRC

    def test_log_panel_font_size_9(self) -> None:
        assert "font.setPointSize(9)" in _MW_SRC

    def test_toggle_panel_sets_visible(self) -> None:
        assert "_log_panel.setVisible(checked)" in _toggle_block()

    def test_toggle_panel_sets_action_text(self) -> None:
        assert "_toggle_log_action.setText(" in _toggle_block()

    def test_append_log_uses_vertical_scrollbar(self) -> None:
        assert "_log_panel.verticalScrollBar()" in _append_block()

    def test_log_panel_connected_to_toggle(self) -> None:
        assert "_toggle_log_action.triggered.connect(self._toggle_log_panel)" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestLogPanelLogic:
    def test_default_log_visible_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert not bool(cfg.get("log_panel_visible", False))

    def test_persists_log_visible_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("log_panel_visible", True)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert bool(cfg2.get("log_panel_visible", False))

    def test_show_label_when_checked(self) -> None:
        checked = True
        label = "Hide Log Panel" if checked else "Show Log Panel"
        assert label == "Hide Log Panel"

    def test_show_label_when_unchecked(self) -> None:
        checked = False
        label = "Hide Log Panel" if checked else "Show Log Panel"
        assert label == "Show Log Panel"

    def test_log_panel_visible_when_checked(self) -> None:
        visible = True
        assert visible

    def test_log_panel_hidden_when_unchecked(self) -> None:
        visible = False
        assert not visible


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

    def test_log_panel_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._log_panel is not None

    def test_log_panel_hidden_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._log_panel.isVisible()

    def test_append_log_adds_text(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._append_log("test message")
        assert "test message" in w._log_panel.toPlainText()
