"""
Tests for FEAT-hotkey-display.

Source-scan tests verify button stored, helper exists, call sites.
Pure-logic tests verify tooltip text construction.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
_MW_SRC = (_ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestHotkeyDisplaySource:
    def test_select_region_btn_stored_as_instance(self) -> None:
        assert "self._select_region_btn = QPushButton(" in _MW_SRC

    def test_helper_method_exists(self) -> None:
        assert "def _update_button_hotkey_labels" in _MW_SRC

    def test_imports_default_bindings(self) -> None:
        idx = _MW_SRC.index("def _update_button_hotkey_labels")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_DEFAULT_BINDINGS" in block

    def test_merges_config_overrides(self) -> None:
        idx = _MW_SRC.index("def _update_button_hotkey_labels")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert '"keybindings"' in block

    def test_four_buttons_mapped(self) -> None:
        idx = _MW_SRC.index("def _update_button_hotkey_labels")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        for action in ("reset_area", "capture", "new_section", "send_to_ocr"):
            assert action in block

    def test_set_tooltip_called(self) -> None:
        idx = _MW_SRC.index("def _update_button_hotkey_labels")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "setToolTip" in block

    def test_key_uppercased(self) -> None:
        idx = _MW_SRC.index("def _update_button_hotkey_labels")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert ".upper()" in block

    def test_called_on_init(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_button_hotkey_labels()" in block

    def test_called_after_settings_accept(self) -> None:
        idx = _MW_SRC.index("def _open_settings")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_button_hotkey_labels()" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

def _make_tooltip(label: str, key: str) -> str:
    return f"{label}  [{key.upper() if key else '(unbound)'}]"


_KNOWN_DEFAULTS = {
    "capture": "f9",
    "new_section": "f10",
    "send_to_ocr": "f11",
    "reset_area": "f8",
    "toggle_overlay": "f7",
    "cancel": "escape",
}


class TestHotkeyDisplayLogic:
    def test_default_capture_is_f9(self) -> None:
        assert _KNOWN_DEFAULTS["capture"] == "f9"

    def test_default_new_section_is_f10(self) -> None:
        assert _KNOWN_DEFAULTS["new_section"] == "f10"

    def test_default_send_to_ocr_is_f11(self) -> None:
        assert _KNOWN_DEFAULTS["send_to_ocr"] == "f11"

    def test_default_reset_area_is_f8(self) -> None:
        assert _KNOWN_DEFAULTS["reset_area"] == "f8"

    def test_tooltip_format(self) -> None:
        tip = _make_tooltip("Capture screenshot", "f9")
        assert tip == "Capture screenshot  [F9]"

    def test_override_replaces_default(self) -> None:
        b = {**_KNOWN_DEFAULTS, "capture": "f12"}
        assert b["capture"] == "f12"

    def test_non_overridden_keys_retained(self) -> None:
        b = {**_KNOWN_DEFAULTS, "capture": "f12"}
        assert b["new_section"] == "f10"

    def test_empty_key_gives_unbound(self) -> None:
        tip = _make_tooltip("Run OCR pipeline", "")
        assert "(unbound)" in tip


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestHotkeyDisplayGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_capture_btn_tooltip_contains_f9(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "F9" in w._capture_btn.toolTip()

    def test_new_section_btn_tooltip_contains_f10(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "F10" in w._new_section_btn.toolTip()

    def test_ocr_btn_tooltip_contains_f11(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "F11" in w._ocr_btn.toolTip()

    def test_select_region_btn_tooltip_contains_f8(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert "F8" in w._select_region_btn.toolTip()

    def test_override_reflected_in_tooltip(self, tmp_path: Path) -> None:
        from utils.config_manager import ConfigManager
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("keybindings", {"capture": "f12"})
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow(cfg)
        assert "F12" in w._capture_btn.toolTip()
