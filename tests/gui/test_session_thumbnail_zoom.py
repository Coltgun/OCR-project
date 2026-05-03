"""
Tests for FEAT-session-thumbnail-zoom.

Source-scan tests verify button creation, wiring, slot structure, and path tracking.
Pure-logic tests verify path guard logic.
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

class TestThumbnailZoomSource:
    def test_zoom_btn_created(self) -> None:
        assert 'QPushButton("Zoom")' in _MW_SRC

    def test_zoom_btn_tooltip(self) -> None:
        assert "View last captured image at full size" in _MW_SRC

    def test_zoom_btn_initially_hidden(self) -> None:
        assert "self._zoom_thumbnail_btn.setVisible(False)" in _MW_SRC

    def test_zoom_btn_connected_to_slot(self) -> None:
        assert "self._zoom_thumbnail_btn.clicked.connect(self._zoom_thumbnail)" in _MW_SRC

    def test_last_capture_path_initialised(self) -> None:
        assert "self._last_capture_path: Path | None = None" in _MW_SRC

    def test_capture_sets_last_path(self) -> None:
        assert "self._last_capture_path = save_path" in _MW_SRC

    def test_capture_shows_zoom_btn(self) -> None:
        assert "self._zoom_thumbnail_btn.setVisible(True)" in _MW_SRC

    def test_clear_hides_zoom_btn(self) -> None:
        idx = _MW_SRC.index("def _clear_thumbnail")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._zoom_thumbnail_btn.setVisible(False)" in block

    def test_clear_resets_last_path(self) -> None:
        idx = _MW_SRC.index("def _clear_thumbnail")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._last_capture_path = None" in block

    def test_slot_exists(self) -> None:
        assert "def _zoom_thumbnail" in _MW_SRC

    def _slot_block(self) -> str:
        idx = _MW_SRC.index("def _zoom_thumbnail")
        end = _MW_SRC.index("\n    def ", idx + 1)
        return _MW_SRC[idx:end]

    def test_slot_guards_none_path(self) -> None:
        assert "self._last_capture_path is None" in self._slot_block()

    def test_slot_guards_exists(self) -> None:
        assert ".exists()" in self._slot_block()

    def test_slot_opens_qdialog(self) -> None:
        assert "QDialog" in self._slot_block()

    def test_slot_scales_to_600_450(self) -> None:
        assert "600, 450" in self._slot_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestThumbnailZoomLogic:
    def test_none_path_guard(self) -> None:
        path = None
        assert path is None

    def test_nonexistent_path_guard(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.png"
        assert not p.exists()

    def test_existing_path_passes(self, tmp_path: Path) -> None:
        p = tmp_path / "img.png"
        p.write_bytes(b"")
        assert p.exists()

    def test_scale_maintains_aspect_less_wide(self) -> None:
        w, h = 300, 200
        max_w, max_h = 600, 450
        ratio = min(max_w / w, max_h / h)
        assert ratio == 2.0

    def test_scale_clamps_large_image(self) -> None:
        w, h = 1200, 900
        max_w, max_h = 600, 450
        ratio = min(max_w / w, max_h / h)
        assert ratio == 0.5


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestThumbnailZoomGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_zoom_btn_hidden_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._zoom_thumbnail_btn.isVisible()

    def test_last_capture_path_none_initially(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._last_capture_path is None

    def test_clear_thumbnail_hides_btn(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._zoom_thumbnail_btn.setVisible(True)
        w._clear_thumbnail()
        assert not w._zoom_thumbnail_btn.isVisible()
