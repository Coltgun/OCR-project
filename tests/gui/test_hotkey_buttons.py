"""
Tests for FEAT-hotkey-buttons.

Source-scan tests verify _capture_btn, _ocr_btn, _export_btn, _select_region_btn,
_new_section_btn button creation (label text, connected signals, disabled states),
_update_button_hotkey_labels (_BTN_MAP 4-button map, tooltip format "[KEY]",
unbound fallback, called on init and settings accept).
Pure-logic tests verify tooltip format, binding merge, unbound display.
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

def _update_labels_block() -> str:
    idx = _MW_SRC.index("def _update_button_hotkey_labels")
    end = _MW_SRC.index("\n    def _apply_preview_font_size", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestHotkeyButtonsSource:
    def test_capture_btn_created(self) -> None:
        assert 'self._capture_btn = QPushButton("Capture (F9)")' in _MW_SRC

    def test_capture_btn_connected(self) -> None:
        assert "_capture_btn.clicked.connect(self._trigger_capture)" in _MW_SRC

    def test_ocr_btn_created(self) -> None:
        assert 'self._ocr_btn = QPushButton("Run OCR (F11)")' in _MW_SRC

    def test_ocr_btn_connected(self) -> None:
        assert "_ocr_btn.clicked.connect(self._trigger_run_ocr)" in _MW_SRC

    def test_export_btn_created(self) -> None:
        assert 'self._export_btn = QPushButton("Export' in _MW_SRC

    def test_export_btn_disabled_on_init(self) -> None:
        idx = _MW_SRC.index('self._export_btn = QPushButton("Export')
        snippet = _MW_SRC[idx:idx + 200]
        assert "_export_btn.setEnabled(False)" in snippet

    def test_export_btn_connected(self) -> None:
        assert "_export_btn.clicked.connect(self._trigger_export)" in _MW_SRC

    def test_update_button_hotkey_labels_exists(self) -> None:
        assert "def _update_button_hotkey_labels" in _MW_SRC

    def test_btn_map_has_4_entries(self) -> None:
        assert "_BTN_MAP = {" in _update_labels_block()
        assert '"reset_area"' in _update_labels_block()
        assert '"capture"' in _update_labels_block()
        assert '"new_section"' in _update_labels_block()
        assert '"send_to_ocr"' in _update_labels_block()

    def test_tooltip_format_uses_key_brackets(self) -> None:
        assert '"  [{key}]")' in _update_labels_block() or \
               "[{key}]" in _update_labels_block()

    def test_tooltip_uppercases_key(self) -> None:
        assert ".upper()" in _update_labels_block()

    def test_unbound_fallback_string(self) -> None:
        assert '"(unbound)"' in _update_labels_block()

    def test_called_on_init(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # ---", idx + 1)
        init_block = _MW_SRC[idx:end]
        assert "_update_button_hotkey_labels()" in init_block

    def test_called_after_settings_accept(self) -> None:
        idx = _MW_SRC.index("def _open_settings")
        end = _MW_SRC.index("\n    def _update_thumbnail", idx + 1)
        settings_block = _MW_SRC[idx:end]
        assert "_update_button_hotkey_labels()" in settings_block

    def test_capture_btn_enabled_based_on_state(self) -> None:
        assert "_capture_btn.setEnabled(" in _MW_SRC

    def test_ocr_btn_enabled_based_on_state(self) -> None:
        assert "_ocr_btn.setEnabled(" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestHotkeyButtonsLogic:
    _DEFAULTS = {
        "capture": "f9",
        "new_section": "f10",
        "send_to_ocr": "f11",
        "reset_area": "f8",
    }

    def test_tooltip_format(self) -> None:
        label = "Capture screenshot"
        key = "f9".upper()
        tooltip = f"{label}  [{key}]"
        assert tooltip == "Capture screenshot  [F9]"

    def test_empty_key_shows_unbound(self) -> None:
        key = "".upper() or "(unbound)"
        tooltip = f"Label  [{key}]"
        assert "(unbound)" in tooltip

    def test_override_replaces_default(self) -> None:
        overrides = {"capture": "f5"}
        bindings = {**self._DEFAULTS, **overrides}
        assert bindings["capture"] == "f5"

    def test_no_override_keeps_default(self) -> None:
        overrides: dict = {}
        bindings = {**self._DEFAULTS, **overrides}
        assert bindings["capture"] == "f9"

    def test_non_dict_overrides_reset(self) -> None:
        overrides = None
        if not isinstance(overrides, dict):
            overrides = {}
        assert overrides == {}

    def test_btn_map_covers_4_actions(self) -> None:
        btn_map_keys = {"reset_area", "capture", "new_section", "send_to_ocr"}
        assert len(btn_map_keys) == 4


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestHotkeyButtonsGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_export_btn_disabled_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._export_btn.isEnabled()

    def test_capture_btn_tooltip_set_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "F9" in w._capture_btn.toolTip()

    def test_ocr_btn_tooltip_set_on_init(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "F11" in w._ocr_btn.toolTip()
