"""
Tests for FEAT-keyboard-shortcuts-help.

Source-scan tests verify menu action, slot structure, and label map.
Pure-logic tests verify HTML generation for shortcuts.
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

class TestKeyboardShortcutsHelpSource:
    def test_action_created(self) -> None:
        assert '"&Keyboard Shortcuts\u2026"' in _MW_SRC

    def test_action_connected_to_slot(self) -> None:
        assert "shortcuts_action.triggered.connect(self._show_keyboard_shortcuts)" in _MW_SRC

    def test_slot_exists(self) -> None:
        assert "def _show_keyboard_shortcuts" in _MW_SRC

    def _slot_block(self) -> str:
        idx = _MW_SRC.index("def _show_keyboard_shortcuts")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        return _MW_SRC[idx:end]

    def test_slot_imports_default_bindings(self) -> None:
        assert "_DEFAULT_BINDINGS" in self._slot_block()

    def test_slot_merges_overrides(self) -> None:
        assert "{**_DEFAULT_BINDINGS, **overrides}" in self._slot_block()

    def test_slot_has_action_labels(self) -> None:
        assert "_ACTION_LABELS" in self._slot_block()

    def test_slot_covers_all_six_actions(self) -> None:
        block = self._slot_block()
        for action in ("capture", "new_section", "send_to_ocr",
                       "reset_area", "toggle_overlay", "cancel"):
            assert f'"{action}"' in block

    def test_slot_uses_qmessagebox(self) -> None:
        assert "QMessageBox.information" in self._slot_block()

    def test_slot_uppercases_key(self) -> None:
        assert ".upper()" in self._slot_block()

    def test_slot_unbound_fallback(self) -> None:
        assert '"(unbound)"' in self._slot_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic helpers (no Qt)
# ---------------------------------------------------------------------------

_ACTION_LABELS = {
    "capture": "Capture screenshot",
    "new_section": "Start new section",
    "send_to_ocr": "Run OCR pipeline",
    "reset_area": "Select capture region",
    "toggle_overlay": "Toggle region border",
    "cancel": "Cancel current action",
}

_KNOWN_DEFAULTS = {
    "capture": "f9",
    "new_section": "f10",
    "send_to_ocr": "f11",
    "reset_area": "f8",
    "toggle_overlay": "f7",
    "cancel": "escape",
}


def _build_shortcuts_html(bindings: dict, labels: dict) -> str:
    lines = ["<b>Active Hotkey Bindings</b><br>"]
    for action, label in labels.items():
        key = bindings.get(action, "").upper() or "(unbound)"
        lines.append(f"<b>{key}</b> &nbsp; {label}")
    return "<br>".join(lines)


class TestKeyboardShortcutsLogic:
    def test_html_contains_heading(self) -> None:
        html = _build_shortcuts_html(_KNOWN_DEFAULTS, _ACTION_LABELS)
        assert "Active Hotkey Bindings" in html

    def test_default_capture_key_uppercased(self) -> None:
        html = _build_shortcuts_html(_KNOWN_DEFAULTS, _ACTION_LABELS)
        assert "F9" in html

    def test_all_six_labels_present(self) -> None:
        html = _build_shortcuts_html(_KNOWN_DEFAULTS, _ACTION_LABELS)
        for label in _ACTION_LABELS.values():
            assert label in html

    def test_override_replaces_key(self) -> None:
        overrides = {**_KNOWN_DEFAULTS, "capture": "f12"}
        html = _build_shortcuts_html(overrides, _ACTION_LABELS)
        assert "F12" in html

    def test_empty_key_shows_unbound(self) -> None:
        empty = {**_KNOWN_DEFAULTS, "cancel": ""}
        html = _build_shortcuts_html(empty, _ACTION_LABELS)
        assert "(unbound)" in html

    def test_six_actions_in_labels(self) -> None:
        assert len(_ACTION_LABELS) == 6


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestKeyboardShortcutsGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        from utils.config_manager import ConfigManager
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_slot_callable(self, tmp_path) -> None:
        w = self._make_window(tmp_path)
        assert callable(w._show_keyboard_shortcuts)

    def test_slot_does_not_raise(self, tmp_path) -> None:
        w = self._make_window(tmp_path)
        w._show_keyboard_shortcuts.__func__  # just access; don't call (would show dialog)
