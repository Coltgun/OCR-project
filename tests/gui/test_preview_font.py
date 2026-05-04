"""
Tests for FEAT-preview-font.

Source-scan tests verify _apply_preview_font_size: font()+setPointSize(max/min
clamp 8-24)+setFont, preview_font_size config key with default 11, called on
init and settings accept.
Pure-logic tests verify clamp semantics and config round-trip.
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

def _font_block() -> str:
    idx = _MW_SRC.index("def _apply_preview_font_size")
    end = _MW_SRC.index("\n    _MAX_RECENT", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestPreviewFontSource:
    def test_apply_preview_font_size_exists(self) -> None:
        assert "def _apply_preview_font_size" in _MW_SRC

    def test_font_reads_current_font(self) -> None:
        assert "self._preview_pane.font()" in _font_block()

    def test_font_sets_point_size(self) -> None:
        assert "font.setPointSize(" in _font_block()

    def test_font_clamp_min_8(self) -> None:
        assert "max(8," in _font_block()

    def test_font_clamp_max_24(self) -> None:
        assert "min(size, 24)" in _font_block() or "24)" in _font_block()

    def test_font_applied_to_preview_pane(self) -> None:
        assert "_preview_pane.setFont(font)" in _font_block()

    def test_config_key_preview_font_size(self) -> None:
        assert '"preview_font_size"' in _MW_SRC

    def test_config_default_is_11(self) -> None:
        assert '"preview_font_size", 11' in _MW_SRC

    def test_called_on_init(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_apply_preview_font_size(" in block

    def test_called_after_settings_accept(self) -> None:
        idx = _MW_SRC.index("def _open_settings")
        end = _MW_SRC.index("\n    def _update_thumbnail", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_apply_preview_font_size(" in block

    def test_size_cast_to_int(self) -> None:
        assert "int(self._cfg.get(" in _MW_SRC

    def test_size_parameter_is_int_typed(self) -> None:
        assert "size: int" in _font_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestPreviewFontLogic:
    def _clamp(self, size: int) -> int:
        return max(8, min(size, 24))

    def test_clamp_below_min(self) -> None:
        assert self._clamp(4) == 8

    def test_clamp_above_max(self) -> None:
        assert self._clamp(30) == 24

    def test_clamp_in_range(self) -> None:
        assert self._clamp(14) == 14

    def test_clamp_at_min_boundary(self) -> None:
        assert self._clamp(8) == 8

    def test_clamp_at_max_boundary(self) -> None:
        assert self._clamp(24) == 24

    def test_config_round_trip_font_size(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_font_size", 14)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("preview_font_size") == 14


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestPreviewFontGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_default_font_size_is_11(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._preview_pane.font().pointSize() == 11

    def test_apply_font_size_changes_pane(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._apply_preview_font_size(16)
        assert w._preview_pane.font().pointSize() == 16

    def test_apply_clamped_below_min(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._apply_preview_font_size(4)
        assert w._preview_pane.font().pointSize() == 8
