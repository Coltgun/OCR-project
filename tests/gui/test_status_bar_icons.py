"""
Tests for FEAT-status-bar-icons.

Source-scan tests verify widget creation and colour-mapping logic without
importing Qt. GUI tests are @pytest.mark.gui + @pytest.mark.skip.
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
# Source-scan tests
# ---------------------------------------------------------------------------

class TestStatusDotSource:
    def test_state_dot_created(self) -> None:
        assert "self._state_dot = QLabel()" in _MW_SRC

    def test_state_dot_fixed_size(self) -> None:
        assert "self._state_dot.setFixedSize(12, 12)" in _MW_SRC

    def test_state_dot_has_tooltip(self) -> None:
        assert 'self._state_dot.setToolTip' in _MW_SRC

    def test_state_dot_added_as_permanent_widget(self) -> None:
        idx = _MW_SRC.index("self._state_dot = QLabel()")
        end = _MW_SRC.index("self._state_label = QLabel", idx)
        block = _MW_SRC[idx:end]
        assert "addPermanentWidget(self._state_dot)" in block

    def test_dot_colours_dict_defined(self) -> None:
        assert "_DOT_COLOURS" in _MW_SRC

    def test_dot_idle_is_green(self) -> None:
        assert "#4CAF50" in _MW_SRC

    def test_dot_busy_is_yellow(self) -> None:
        assert "#FFC107" in _MW_SRC

    def test_dot_error_is_red(self) -> None:
        assert "#F44336" in _MW_SRC

    def test_idle_state_maps_to_dot_idle(self) -> None:
        assert "AppState.IDLE: _DOT_IDLE" in _MW_SRC

    def test_ocr_running_maps_to_dot_busy(self) -> None:
        assert "AppState.OCR_RUNNING: _DOT_BUSY" in _MW_SRC

    def test_capturing_maps_to_dot_busy(self) -> None:
        assert "AppState.CAPTURING: _DOT_BUSY" in _MW_SRC

    def test_selecting_maps_to_dot_busy(self) -> None:
        assert "AppState.SELECTING: _DOT_BUSY" in _MW_SRC

    def test_exporting_maps_to_dot_busy(self) -> None:
        assert "AppState.EXPORTING: _DOT_BUSY" in _MW_SRC

    def test_dot_stylesheet_set_in_update_ui(self) -> None:
        idx = _MW_SRC.index("def _update_ui_for_state")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._state_dot.setStyleSheet" in block

    def test_dot_uses_colours_dict_lookup(self) -> None:
        assert "_DOT_COLOURS.get(state" in _MW_SRC

    def test_dot_uses_border_radius(self) -> None:
        assert "border-radius:6px" in _MW_SRC


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestStatusDotGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_dot_exists(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._state_dot is not None

    def test_dot_is_12x12(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._state_dot.width() == 12
        assert w._state_dot.height() == 12

    def test_idle_dot_is_green(self, tmp_path: Path) -> None:
        from capture.state import AppState
        w = self._make_window(tmp_path)
        w._update_ui_for_state(AppState.IDLE)
        assert "#4CAF50" in w._state_dot.styleSheet()

    def test_ocr_running_dot_is_yellow(self, tmp_path: Path) -> None:
        from capture.state import AppState
        w = self._make_window(tmp_path)
        w._update_ui_for_state(AppState.OCR_RUNNING)
        assert "#FFC107" in w._state_dot.styleSheet()

    def test_capturing_dot_is_yellow(self, tmp_path: Path) -> None:
        from capture.state import AppState
        w = self._make_window(tmp_path)
        w._update_ui_for_state(AppState.CAPTURING)
        assert "#FFC107" in w._state_dot.styleSheet()

    def test_exporting_dot_is_yellow(self, tmp_path: Path) -> None:
        from capture.state import AppState
        w = self._make_window(tmp_path)
        w._update_ui_for_state(AppState.EXPORTING)
        assert "#FFC107" in w._state_dot.styleSheet()
