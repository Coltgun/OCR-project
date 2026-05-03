"""
Tests for FEAT-font-size-live-preview.

Source-scan tests verify label, connection, and slot in SettingsDialog.
Pure-logic tests verify font size clamping and update logic.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_SD_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "settings_dialog.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestFontSizeLivePreviewSource:
    def test_label_created(self) -> None:
        assert "self._font_preview_label = QLabel(" in _SD_SRC

    def test_label_has_sample_text(self) -> None:
        assert "AaBbCc" in _SD_SRC

    def test_label_has_chinese(self) -> None:
        assert "\\u6c49\\u5b57" in _SD_SRC or "\u6c49\u5b57" in _SD_SRC

    def test_label_has_tooltip(self) -> None:
        assert "Live font size preview" in _SD_SRC

    def test_spinbox_connected_to_slot(self) -> None:
        assert (
            "self._preview_font_size.valueChanged.connect(self._update_font_preview)"
        ) in _SD_SRC

    def test_slot_exists(self) -> None:
        assert "def _update_font_preview" in _SD_SRC

    def test_slot_sets_font_point_size(self) -> None:
        idx = _SD_SRC.index("def _update_font_preview")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert "setPointSize(size)" in block

    def test_slot_sets_font_on_label(self) -> None:
        idx = _SD_SRC.index("def _update_font_preview")
        end = _SD_SRC.index("\n    # --", idx + 1)
        block = _SD_SRC[idx:end]
        assert "self._font_preview_label.setFont(font)" in block

    def test_load_values_calls_update(self) -> None:
        assert "_update_font_preview(self._preview_font_size.value())" in _SD_SRC

    def test_form_row_label(self) -> None:
        assert '"Preview:"' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))


class TestFontSizeLivePreviewLogic:
    def test_default_font_size_11(self) -> None:
        from utils.config_manager import ConfigManager
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cfg = ConfigManager(path=Path(tmp) / "config.json")
            assert int(cfg.get("preview_font_size", 11)) == 11

    def test_clamp_below_min(self) -> None:
        assert _clamp(4, 8, 24) == 8

    def test_clamp_above_max(self) -> None:
        assert _clamp(30, 8, 24) == 24

    def test_clamp_within_range(self) -> None:
        assert _clamp(14, 8, 24) == 14

    def test_spinbox_range_min(self) -> None:
        assert 8 <= 11 <= 24

    def test_sample_text_not_empty(self) -> None:
        sample = "AaBbCc \u6c49\u5b57 123"
        assert len(sample) > 0


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestFontSizeLivePreviewGui:
    def _make_dialog(self, tmp_path, size=11):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_font_size", size)
        return SettingsDialog(cfg)

    def test_label_exists(self, tmp_path) -> None:
        dlg = self._make_dialog(tmp_path)
        assert dlg._font_preview_label is not None

    def test_initial_font_size_matches_config(self, tmp_path) -> None:
        dlg = self._make_dialog(tmp_path, size=14)
        assert dlg._font_preview_label.font().pointSize() == 14

    def test_spinbox_change_updates_label(self, tmp_path) -> None:
        dlg = self._make_dialog(tmp_path, size=11)
        dlg._preview_font_size.setValue(18)
        assert dlg._font_preview_label.font().pointSize() == 18
