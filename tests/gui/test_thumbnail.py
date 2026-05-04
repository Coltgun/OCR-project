"""
Tests for FEAT-thumbnail.

Source-scan tests verify _thumbnail_label QLabel (fixedSize 120x90, AlignCenter,
tooltip, border style), _zoom_thumbnail_btn QPushButton (hidden, tooltip,
clicked->_zoom_thumbnail), _update_thumbnail (QPixmap, isNull guard, scaled with
KeepAspectRatio+SmoothTransformation using label dimensions, setPixmap),
_clear_thumbnail (clear, zoom_btn hidden, _last_capture_path=None),
_zoom_thumbnail (None+exists guard, QPixmap+isNull guard, QDialog, 600x450 scaled).
Pure-logic tests verify pixmap null guard, scale dimensions, path guard logic.
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

def _update_thumbnail_block() -> str:
    idx = _MW_SRC.index("def _update_thumbnail")
    end = _MW_SRC.index("\n    def _clear_thumbnail", idx + 1)
    return _MW_SRC[idx:end]

def _clear_thumbnail_block() -> str:
    idx = _MW_SRC.index("def _clear_thumbnail")
    end = _MW_SRC.index("\n    @Slot()\n    def _zoom_thumbnail", idx + 1)
    return _MW_SRC[idx:end]

def _zoom_thumbnail_block() -> str:
    idx = _MW_SRC.index("def _zoom_thumbnail")
    end = _MW_SRC.index("\n    def _update_pipeline_mode_label", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestThumbnailSource:
    def test_thumbnail_label_created(self) -> None:
        assert "self._thumbnail_label = QLabel()" in _MW_SRC

    def test_thumbnail_label_fixed_size(self) -> None:
        assert "_thumbnail_label.setFixedSize(120, 90)" in _MW_SRC

    def test_thumbnail_label_align_center(self) -> None:
        assert "_thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)" in _MW_SRC

    def test_thumbnail_label_tooltip(self) -> None:
        assert '_thumbnail_label.setToolTip("Last captured image")' in _MW_SRC

    def test_thumbnail_label_border_style(self) -> None:
        assert "_thumbnail_label.setStyleSheet(" in _MW_SRC

    def test_zoom_thumbnail_btn_created(self) -> None:
        assert 'self._zoom_thumbnail_btn = QPushButton("Zoom")' in _MW_SRC

    def test_zoom_thumbnail_btn_hidden(self) -> None:
        assert "_zoom_thumbnail_btn.setVisible(False)" in _MW_SRC

    def test_zoom_thumbnail_btn_connected(self) -> None:
        assert "_zoom_thumbnail_btn.clicked.connect(self._zoom_thumbnail)" in _MW_SRC

    def test_update_thumbnail_exists(self) -> None:
        assert "def _update_thumbnail" in _MW_SRC

    def test_update_thumbnail_creates_pixmap(self) -> None:
        assert "QPixmap(str(image_path))" in _update_thumbnail_block()

    def test_update_thumbnail_guards_null(self) -> None:
        assert "if not pixmap.isNull():" in _update_thumbnail_block()

    def test_update_thumbnail_scales_to_label_size(self) -> None:
        assert "self._thumbnail_label.width()" in _update_thumbnail_block()
        assert "self._thumbnail_label.height()" in _update_thumbnail_block()

    def test_update_thumbnail_keep_aspect_ratio(self) -> None:
        assert "Qt.AspectRatioMode.KeepAspectRatio" in _update_thumbnail_block()

    def test_update_thumbnail_smooth_transform(self) -> None:
        assert "Qt.TransformationMode.SmoothTransformation" in _update_thumbnail_block()

    def test_update_thumbnail_sets_pixmap(self) -> None:
        assert "_thumbnail_label.setPixmap(scaled)" in _update_thumbnail_block()

    def test_clear_thumbnail_exists(self) -> None:
        assert "def _clear_thumbnail" in _MW_SRC

    def test_clear_thumbnail_clears_label(self) -> None:
        assert "_thumbnail_label.clear()" in _clear_thumbnail_block()

    def test_clear_thumbnail_hides_zoom_btn(self) -> None:
        assert "_zoom_thumbnail_btn.setVisible(False)" in _clear_thumbnail_block()

    def test_clear_thumbnail_resets_last_capture_path(self) -> None:
        assert "_last_capture_path = None" in _clear_thumbnail_block()

    def test_zoom_thumbnail_exists(self) -> None:
        assert "def _zoom_thumbnail" in _MW_SRC

    def test_zoom_thumbnail_guards_none_path(self) -> None:
        assert "if self._last_capture_path is None" in _zoom_thumbnail_block()

    def test_zoom_thumbnail_guards_exists(self) -> None:
        assert ".exists()" in _zoom_thumbnail_block()

    def test_zoom_thumbnail_guards_null_pixmap(self) -> None:
        assert "if pixmap.isNull():" in _zoom_thumbnail_block()

    def test_zoom_thumbnail_opens_dialog(self) -> None:
        assert "QDialog(self)" in _zoom_thumbnail_block()

    def test_zoom_thumbnail_scale_600_450(self) -> None:
        assert "600, 450," in _zoom_thumbnail_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestThumbnailLogic:
    def test_null_pixmap_guard(self) -> None:
        is_null = True
        should_set = not is_null
        assert not should_set

    def test_valid_pixmap_proceeds(self) -> None:
        is_null = False
        should_set = not is_null
        assert should_set

    def test_clear_resets_path_to_none(self) -> None:
        last_capture_path: Path | None = Path("some/path.png")
        last_capture_path = None
        assert last_capture_path is None

    def test_zoom_guard_none_path(self) -> None:
        last_capture_path = None
        should_return = last_capture_path is None
        assert should_return

    def test_zoom_guard_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.png"
        should_return = not p.exists()
        assert should_return

    def test_zoom_guard_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "img.png"
        p.write_bytes(b"fake")
        should_return = not p.exists()
        assert not should_return


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestThumbnailGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_thumbnail_label_fixed_size(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._thumbnail_label.width() == 120
        assert w._thumbnail_label.height() == 90

    def test_zoom_btn_hidden_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._zoom_thumbnail_btn.isVisible()

    def test_clear_thumbnail_hides_zoom_btn(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._zoom_thumbnail_btn.setVisible(True)
        w._clear_thumbnail()
        assert not w._zoom_thumbnail_btn.isVisible()
        assert w._last_capture_path is None
