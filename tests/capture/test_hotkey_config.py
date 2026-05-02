"""
Tests for FEAT-hotkey-config.

capture.hotkeys imports PySide6 at module level, which triggers a DLL conflict
when cv2 (conda-forge) is already loaded in the pytest process on Windows.
We therefore use two strategies:

1. Source-scan tests — read hotkeys.py / settings_dialog.py / main_window.py
   as text to verify the feature is wired correctly (no Qt import needed).

2. Config-logic tests — exercise ConfigManager keybindings roundtrip and the
   HotkeyListener key-build logic via ast.literal_eval-safe dicts, reading
   the _DEFAULT_BINDINGS / _PYNPUT_KEY_MAP values from source parsing.

GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source file paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
_HOTKEYS_SRC = (_ROOT / "capture" / "hotkeys.py").read_text(encoding="utf-8")
_SETTINGS_SRC = (_ROOT / "gui" / "settings_dialog.py").read_text(encoding="utf-8")
_MW_SRC = (_ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers — extract plain dicts from source without importing Qt
# ---------------------------------------------------------------------------

def _extract_dict_literal(source: str, var_name: str) -> dict:
    """Extract a top-level dict literal assigned to var_name in source."""
    pattern = rf"^{re.escape(var_name)}\s*:\s*dict\[.*?\]\s*=\s*({{.*?}})"
    m = re.search(pattern, source, re.DOTALL | re.MULTILINE)
    if m is None:
        # Try without type annotation
        pattern = rf"^{re.escape(var_name)}\s*=\s*({{.*?}})"
        m = re.search(pattern, source, re.DOTALL | re.MULTILINE)
    assert m is not None, f"Could not find '{var_name}' dict in source"
    return ast.literal_eval(m.group(1))


_DEFAULT_BINDINGS = _extract_dict_literal(_HOTKEYS_SRC, "_DEFAULT_BINDINGS")

# Extract _PYNPUT_KEY_MAP keys only (values are keyboard.Key objects, not literals)
_PYNPUT_KEYS: set[str] = set(
    re.findall(r'"([^"]+)"\s*:\s*keyboard\.Key\.', _HOTKEYS_SRC)
)


# ---------------------------------------------------------------------------
# 1. hotkeys.py source-scan
# ---------------------------------------------------------------------------

class TestHotkeySourceWiring:
    _EXPECTED_ACTIONS = {
        "capture", "new_section", "send_to_ocr",
        "reset_area", "toggle_overlay", "cancel",
    }

    def test_all_expected_actions_in_default_bindings(self) -> None:
        assert self._EXPECTED_ACTIONS == set(_DEFAULT_BINDINGS.keys())

    def test_all_default_keys_in_pynput_map(self) -> None:
        for action, key_str in _DEFAULT_BINDINGS.items():
            assert key_str.lower() in _PYNPUT_KEYS, (
                f"Default key '{key_str}' for '{action}' not in _PYNPUT_KEY_MAP"
            )

    def test_pynput_map_covers_f1_through_f12(self) -> None:
        for n in range(1, 13):
            assert f"f{n}" in _PYNPUT_KEYS

    def test_pynput_map_covers_escape_aliases(self) -> None:
        assert "escape" in _PYNPUT_KEYS
        assert "esc" in _PYNPUT_KEYS

    def test_reload_method_present(self) -> None:
        assert "def reload(self, config: dict)" in _HOTKEYS_SRC

    def test_reload_calls_build_key_map(self) -> None:
        idx = _HOTKEYS_SRC.index("def reload(")
        reload_block = _HOTKEYS_SRC[idx: _HOTKEYS_SRC.index("\n    def ", idx + 1)]
        assert "_build_key_map(config)" in reload_block

    def test_build_key_map_reads_keybindings_key(self) -> None:
        assert 'config.get("keybindings"' in _HOTKEYS_SRC

    def test_default_bindings_merged_with_config(self) -> None:
        assert "_DEFAULT_BINDINGS, **bindings_cfg" in _HOTKEYS_SRC


# ---------------------------------------------------------------------------
# 2. SettingsDialog source-scan
# ---------------------------------------------------------------------------

class TestSettingsDialogHotkeyTab:
    def test_hotkeys_tab_added_to_tabs(self) -> None:
        assert 'tabs.addTab(self._build_hotkeys_tab(), "Hotkeys")' in _SETTINGS_SRC

    def test_build_hotkeys_tab_method_exists(self) -> None:
        assert "def _build_hotkeys_tab" in _SETTINGS_SRC

    def test_default_bindings_imported(self) -> None:
        assert "_DEFAULT_BINDINGS" in _SETTINGS_SRC

    def test_pynput_key_map_imported(self) -> None:
        assert "_PYNPUT_KEY_MAP" in _SETTINGS_SRC

    def test_hotkey_edits_dict_present(self) -> None:
        assert "self._hotkey_edits" in _SETTINGS_SRC

    def test_keybindings_written_on_save(self) -> None:
        assert 'cfg.set("keybindings", bindings)' in _SETTINGS_SRC

    def test_keybindings_loaded_from_config(self) -> None:
        assert 'cfg.get("keybindings"' in _SETTINGS_SRC

    def test_blank_value_excluded_from_bindings(self) -> None:
        assert "if val:" in _SETTINGS_SRC

    def test_all_six_actions_in_action_labels(self) -> None:
        for action in _DEFAULT_BINDINGS:
            assert f'"{action}"' in _SETTINGS_SRC

    def test_valid_keys_hint_shown_to_user(self) -> None:
        assert "Valid keys" in _SETTINGS_SRC


# ---------------------------------------------------------------------------
# 3. MainWindow source-scan
# ---------------------------------------------------------------------------

class TestMainWindowHotkeyReload:
    def test_hotkeys_reload_called_after_accept(self) -> None:
        assert "self._hotkeys.reload(self._cfg)" in _MW_SRC

    def test_reload_called_inside_open_settings(self) -> None:
        idx = _MW_SRC.index("def _open_settings")
        # Find next method boundary (either @Slot or # --- section divider)
        next_slot = _MW_SRC.find("\n    @Slot", idx + 1)
        next_section = _MW_SRC.find("\n    # ---", idx + 1)
        candidates = [p for p in (next_slot, next_section) if p != -1]
        end = min(candidates) if candidates else len(_MW_SRC)
        block = _MW_SRC[idx:end]
        assert "self._hotkeys.reload(self._cfg)" in block


# ---------------------------------------------------------------------------
# 4. Config roundtrip (pure Python, no Qt)
# ---------------------------------------------------------------------------

class TestKeybindingsConfigRoundtrip:
    def test_keybindings_saved_and_reloaded(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        bindings = {"capture": "f1", "cancel": "f2"}
        cfg.set("keybindings", bindings)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        loaded = cfg2.get("keybindings", {})
        assert loaded == bindings

    def test_missing_keybindings_returns_empty_dict(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("keybindings", {}) == {}

    def test_partial_override_only_stores_provided_keys(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("keybindings", {"capture": "f1"})
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        bindings = cfg2.get("keybindings", {})
        assert bindings.get("capture") == "f1"
        assert "new_section" not in bindings

    def test_empty_bindings_dict_saved_and_loaded(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("keybindings", {})
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("keybindings", {}) == {}

    def test_all_six_actions_roundtrip(self, tmp_path: Path) -> None:
        bindings = {action: f"f{i+1}" for i, action in enumerate(_DEFAULT_BINDINGS)}
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("keybindings", bindings)
        cfg.save()
        loaded = ConfigManager(path=tmp_path / "config.json").get("keybindings", {})
        assert loaded == bindings


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestHotkeyConfigGui:
    def _make_dialog(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return SettingsDialog(cfg), cfg

    def test_hotkeys_tab_has_six_edits(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert len(dlg._hotkey_edits) == 6

    def test_placeholder_shows_default_for_capture(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._hotkey_edits["capture"].placeholderText() == "f9"

    def test_saved_bindings_loaded_into_edits(self, tmp_path: Path) -> None:
        from gui.settings_dialog import SettingsDialog
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("keybindings", {"capture": "f1"})
        dlg = SettingsDialog(cfg)
        assert dlg._hotkey_edits["capture"].text() == "f1"

    def test_save_writes_keybindings(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._hotkey_edits["capture"].setText("f2")
        dlg._save_values()
        assert cfg.get("keybindings", {}).get("capture") == "f2"

    def test_blank_edit_excluded_from_saved_bindings(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._hotkey_edits["capture"].setText("")
        dlg._save_values()
        assert "capture" not in cfg.get("keybindings", {})
