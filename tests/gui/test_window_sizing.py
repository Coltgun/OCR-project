"""
Tests for FEAT-min-window-size.

Source-scan tests only (no Qt import needed):
  - Minimum window size bumped to 560x480.
  - Preview pane uses QSizePolicy.Expanding (both axes), no fixed max height.
  - Preview pane has a minimum height set.
  - Log panel retains a max height cap.
  - Log panel uses QSizePolicy.MinimumExpanding vertically.
  - Log panel has a minimum height set.
  - QSizePolicy is imported.

GUI tests — @pytest.mark.gui + @pytest.mark.skip.
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

class TestWindowSizingSource:
    def test_minimum_size_is_560_480(self) -> None:
        assert "setMinimumSize(560, 480)" in _MW_SRC

    def test_qsizepolicy_imported(self) -> None:
        assert "QSizePolicy" in _MW_SRC

    def test_preview_pane_expanding_horizontal(self) -> None:
        assert "QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding" in _MW_SRC

    def test_preview_pane_no_fixed_max_height(self) -> None:
        idx = _MW_SRC.index("self._preview_pane = QTextEdit()")
        end = _MW_SRC.index("self._log_panel = QTextEdit()", idx)
        block = _MW_SRC[idx:end]
        assert "setMaximumHeight" not in block

    def test_preview_pane_has_minimum_height(self) -> None:
        idx = _MW_SRC.index("self._preview_pane = QTextEdit()")
        end = _MW_SRC.index("self._log_panel = QTextEdit()", idx)
        block = _MW_SRC[idx:end]
        assert "setMinimumHeight" in block

    def test_log_panel_retains_max_height(self) -> None:
        idx = _MW_SRC.index("self._log_panel = QTextEdit()")
        end = _MW_SRC.index("self._log_panel.setVisible(False)", idx)
        block = _MW_SRC[idx:end]
        assert "setMaximumHeight" in block

    def test_log_panel_minimum_expanding_policy(self) -> None:
        assert "QSizePolicy.Policy.MinimumExpanding" in _MW_SRC

    def test_log_panel_has_minimum_height(self) -> None:
        idx = _MW_SRC.index("self._log_panel = QTextEdit()")
        end = _MW_SRC.index("self._log_panel.setVisible(False)", idx)
        block = _MW_SRC[idx:end]
        assert "setMinimumHeight" in block

    def test_old_minimum_size_not_present(self) -> None:
        assert "setMinimumSize(520, 380)" not in _MW_SRC


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestWindowSizingGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_minimum_width_at_least_560(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w.minimumWidth() >= 560

    def test_minimum_height_at_least_480(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w.minimumHeight() >= 480

    def test_preview_pane_size_policy_expanding(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QSizePolicy
        w = self._make_window(tmp_path)
        sp = w._preview_pane.sizePolicy()
        assert sp.horizontalPolicy() == QSizePolicy.Policy.Expanding
        assert sp.verticalPolicy() == QSizePolicy.Policy.Expanding

    def test_preview_pane_has_no_fixed_max_height(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._preview_pane.maximumHeight() > 200

    def test_log_panel_max_height_capped(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._log_panel.maximumHeight() <= 200

    def test_log_panel_size_policy_minimum_expanding(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QSizePolicy
        w = self._make_window(tmp_path)
        sp = w._log_panel.sizePolicy()
        assert sp.verticalPolicy() == QSizePolicy.Policy.MinimumExpanding
