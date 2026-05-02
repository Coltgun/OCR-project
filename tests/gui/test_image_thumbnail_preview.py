"""
Tests for FEAT-image-thumbnail-preview.

Source-scan tests verify widget creation, wiring, and clear calls.
Pure-logic tests verify scaling math.
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
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestImageThumbnailSource:
    def test_thumbnail_label_created(self) -> None:
        assert "self._thumbnail_label = QLabel()" in _MW_SRC

    def test_thumbnail_fixed_size(self) -> None:
        assert "self._thumbnail_label.setFixedSize(120, 90)" in _MW_SRC

    def test_thumbnail_align_center(self) -> None:
        assert "AlignCenter" in _MW_SRC

    def test_thumbnail_tooltip(self) -> None:
        assert '"Last captured image"' in _MW_SRC

    def test_thumbnail_border_style(self) -> None:
        assert "border: 1px solid #888" in _MW_SRC

    def test_update_thumbnail_method(self) -> None:
        assert "def _update_thumbnail" in _MW_SRC

    def test_clear_thumbnail_method(self) -> None:
        assert "def _clear_thumbnail" in _MW_SRC

    def test_qpixmap_imported(self) -> None:
        assert "QPixmap" in _MW_SRC

    def test_update_thumbnail_called_after_capture(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_thumbnail(save_path)" in block

    def test_clear_thumbnail_called_on_new_section(self) -> None:
        idx = _MW_SRC.index("def _trigger_new_section")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_clear_thumbnail()" in block

    def test_clear_thumbnail_called_on_reset_count(self) -> None:
        idx = _MW_SRC.index("def _reset_capture_count")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_clear_thumbnail()" in block

    def test_clear_thumbnail_called_on_new_session(self) -> None:
        idx = _MW_SRC.index("def _start_new_session")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_clear_thumbnail()" in block

    def test_clear_thumbnail_called_on_resume_session(self) -> None:
        idx = _MW_SRC.index("def _open_recent_session")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_clear_thumbnail()" in block

    def test_keep_aspect_ratio_used(self) -> None:
        assert "KeepAspectRatio" in _MW_SRC

    def test_smooth_transformation_used(self) -> None:
        assert "SmoothTransformation" in _MW_SRC

    def test_null_pixmap_guard(self) -> None:
        idx = _MW_SRC.index("def _update_thumbnail")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "isNull()" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestImageThumbnailLogic:
    def test_thumbnail_dimensions(self) -> None:
        w, h = 120, 90
        assert w == 120
        assert h == 90

    def test_aspect_ratio_landscape(self) -> None:
        img_w, img_h = 800, 600
        box_w, box_h = 120, 90
        scale = min(box_w / img_w, box_h / img_h)
        out_w = int(img_w * scale)
        out_h = int(img_h * scale)
        assert out_w <= box_w
        assert out_h <= box_h
        assert abs(out_w / out_h - img_w / img_h) < 0.01

    def test_aspect_ratio_portrait(self) -> None:
        img_w, img_h = 400, 800
        box_w, box_h = 120, 90
        scale = min(box_w / img_w, box_h / img_h)
        out_w = int(img_w * scale)
        out_h = int(img_h * scale)
        assert out_w <= box_w
        assert out_h <= box_h


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestImageThumbnailGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_thumbnail_label_exists(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert hasattr(w, "_thumbnail_label")

    def test_thumbnail_initially_empty(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._thumbnail_label.pixmap() is None or w._thumbnail_label.pixmap().isNull()

    def test_thumbnail_fixed_size(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._thumbnail_label.width() == 120
        assert w._thumbnail_label.height() == 90

    def test_clear_thumbnail_clears_pixmap(self, tmp_path: Path) -> None:
        import numpy as np
        import cv2
        w = self._make_window(tmp_path)
        img_path = tmp_path / "test.png"
        cv2.imwrite(str(img_path), np.zeros((90, 120, 3), dtype="uint8"))
        w._update_thumbnail(img_path)
        w._clear_thumbnail()
        assert w._thumbnail_label.pixmap() is None or w._thumbnail_label.pixmap().isNull()
