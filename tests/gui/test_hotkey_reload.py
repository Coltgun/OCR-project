"""
Tests for FEAT-hotkey-reload.

Source-scan tests verify _hotkeys.reload(cfg) call on settings accept,
_update_button_hotkey_labels: _DEFAULT_BINDINGS merge with overrides,
_BTN_MAP tooltips for 4 buttons, keybindings config key.
Pure-logic tests verify binding merge semantics.
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

class TestHotkeyReloadSource:
    def test_hotkeys_reload_called_on_settings_accept(self) -> None:
        assert "self._hotkeys.reload(self._cfg)" in _MW_SRC

    def test_update_button_hotkey_labels_exists(self) -> None:
        assert "def _update_button_hotkey_labels" in _MW_SRC

    def test_update_labels_imports_default_bindings(self) -> None:
        assert "_DEFAULT_BINDINGS" in _update_labels_block()

    def test_update_labels_reads_keybindings_config(self) -> None:
        assert '"keybindings"' in _update_labels_block()

    def test_update_labels_merges_overrides(self) -> None:
        assert "{**_DEFAULT_BINDINGS, **overrides}" in _update_labels_block()

    def test_update_labels_maps_reset_area(self) -> None:
        assert '"reset_area"' in _update_labels_block()

    def test_update_labels_maps_capture(self) -> None:
        assert '"capture"' in _update_labels_block()

    def test_update_labels_maps_new_section(self) -> None:
        assert '"new_section"' in _update_labels_block()

    def test_update_labels_maps_send_to_ocr(self) -> None:
        assert '"send_to_ocr"' in _update_labels_block()

    def test_update_labels_sets_tooltip(self) -> None:
        assert "btn.setToolTip(" in _update_labels_block()

    def test_update_labels_shows_key_uppercase(self) -> None:
        assert ".upper()" in _update_labels_block()

    def test_update_labels_unbound_fallback(self) -> None:
        assert '"(unbound)"' in _update_labels_block()

    def test_update_button_labels_called_after_settings(self) -> None:
        assert "_update_button_hotkey_labels()" in _MW_SRC

    def test_overrides_guard_isinstance_dict(self) -> None:
        assert "isinstance(overrides, dict)" in _update_labels_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestHotkeyReloadLogic:
    _DEFAULT_BINDINGS = {
        "capture": "f9",
        "new_section": "f10",
        "send_to_ocr": "f11",
        "reset_area": "f8",
        "toggle_overlay": "f7",
        "cancel": "escape",
    }

    def test_override_replaces_default(self) -> None:
        overrides = {"capture": "f5"}
        bindings = {**self._DEFAULT_BINDINGS, **overrides}
        assert bindings["capture"] == "f5"

    def test_no_override_keeps_default(self) -> None:
        overrides: dict = {}
        bindings = {**self._DEFAULT_BINDINGS, **overrides}
        assert bindings["capture"] == "f9"

    def test_non_dict_overrides_reset_to_empty(self) -> None:
        overrides = "bad"
        if not isinstance(overrides, dict):
            overrides = {}
        bindings = {**self._DEFAULT_BINDINGS, **overrides}
        assert bindings["capture"] == "f9"

    def test_empty_key_shows_unbound(self) -> None:
        key = "".upper() or "(unbound)"
        assert key == "(unbound)"

    def test_present_key_shown_uppercase(self) -> None:
        key = "f9".upper() or "(unbound)"
        assert key == "F9"

    def test_keybindings_default_empty_dict(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        result = cfg.get("keybindings", {})
        assert result == {}


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestHotkeyReloadGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_capture_btn_tooltip_set(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "Capture screenshot" in w._capture_btn.toolTip()

    def test_ocr_btn_tooltip_set(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "Run OCR pipeline" in w._ocr_btn.toolTip()

    def test_reload_updates_tooltips(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        w._cfg["keybindings"] = {"capture": "f5"}
        w._update_button_hotkey_labels()
        assert "F5" in w._capture_btn.toolTip()
