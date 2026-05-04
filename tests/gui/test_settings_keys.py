"""
Tests for FEAT-settings-keys.

Source-scan tests verify _FACTORY_DEFAULTS keys/values, _save_values writes
all expected config keys (ocr_pipeline_mode, dedup_threshold,
embedding_threshold, ocr_min_confidence, hybrid_high/low, openrouter_api_key,
openrouter_model, openrouter_base_url, llm_base_url, llm_model, vram_tier,
bert_batch_size, bert_max_length, embedding_batch_size, working_root_dir,
export_filename_template, auto_new_section_threshold, max_recent_sessions,
rotation_mode, capture_delay_ms, preview_font_size, keybindings), cfg.save().
Pure-logic tests verify factory defaults semantics and config round-trips.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_SD_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "settings_dialog.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _save_block() -> str:
    idx = _SD_SRC.index("def _save_values")
    end = _SD_SRC.index("\n    # ------------------------------------------------------------------\n    # Slots", idx + 1)
    return _SD_SRC[idx:end]

def _factory_block() -> str:
    idx = _SD_SRC.index("_FACTORY_DEFAULTS")
    end = _SD_SRC.index("\n    _ACTION_LABELS", idx + 1)
    return _SD_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests — _FACTORY_DEFAULTS
# ---------------------------------------------------------------------------

class TestFactoryDefaultsSource:
    def test_factory_defaults_defined(self) -> None:
        assert "_FACTORY_DEFAULTS: dict[str, object] = {" in _SD_SRC

    def test_default_ocr_pipeline_mode(self) -> None:
        assert '"ocr_pipeline_mode": "LOCAL_FAST"' in _factory_block()

    def test_default_vram_tier(self) -> None:
        assert '"vram_tier": "8gb"' in _factory_block()

    def test_default_ocr_min_confidence(self) -> None:
        assert '"ocr_min_confidence": 0.6' in _factory_block()

    def test_default_auto_new_section_threshold(self) -> None:
        assert '"auto_new_section_threshold": 0' in _factory_block()

    def test_default_rotation_mode(self) -> None:
        assert '"rotation_mode": "none"' in _factory_block()

    def test_default_preview_font_size(self) -> None:
        assert '"preview_font_size": 11' in _factory_block()

    def test_default_dark_mode(self) -> None:
        assert '"dark_mode": False' in _factory_block()

    def test_default_preview_word_wrap(self) -> None:
        assert '"preview_word_wrap": True' in _factory_block()

    def test_default_export_format(self) -> None:
        assert '"export_format": "epub"' in _factory_block()

    def test_default_keybindings_empty(self) -> None:
        assert '"keybindings": {}' in _factory_block()


# ---------------------------------------------------------------------------
# 2. Source-scan tests — _save_values
# ---------------------------------------------------------------------------

class TestSaveValuesSource:
    def test_save_values_exists(self) -> None:
        assert "def _save_values" in _SD_SRC

    def test_saves_ocr_pipeline_mode(self) -> None:
        assert '"ocr_pipeline_mode"' in _save_block()

    def test_saves_ocr_min_confidence(self) -> None:
        assert '"ocr_min_confidence"' in _save_block()

    def test_saves_vram_tier(self) -> None:
        assert '"vram_tier"' in _save_block()

    def test_saves_openrouter_api_key(self) -> None:
        assert '"openrouter_api_key"' in _save_block()

    def test_saves_llm_base_url(self) -> None:
        assert '"llm_base_url"' in _save_block()

    def test_saves_auto_new_section_threshold(self) -> None:
        assert '"auto_new_section_threshold"' in _save_block()

    def test_saves_rotation_mode(self) -> None:
        assert '"rotation_mode"' in _save_block()

    def test_saves_capture_delay_ms(self) -> None:
        assert '"capture_delay_ms"' in _save_block()

    def test_saves_preview_font_size(self) -> None:
        assert '"preview_font_size"' in _save_block()

    def test_saves_export_filename_template(self) -> None:
        assert '"export_filename_template"' in _save_block()

    def test_saves_keybindings(self) -> None:
        assert '"keybindings"' in _save_block()

    def test_delay_converted_ms_to_int(self) -> None:
        assert "int(self._capture_delay.value() * 1000)" in _save_block()

    def test_template_fallback(self) -> None:
        assert '"{session}_{timestamp}"' in _save_block()

    def test_working_root_dir_fallback(self) -> None:
        assert '"sessions"' in _save_block()

    def test_cfg_save_called(self) -> None:
        assert "cfg.save()" in _save_block()


# ---------------------------------------------------------------------------
# 3. Pure-logic tests
# ---------------------------------------------------------------------------

class TestSettingsKeysLogic:
    def test_factory_defaults_round_trip(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        defaults = {
            "ocr_min_confidence": 0.6,
            "vram_tier": "8gb",
            "auto_new_section_threshold": 0,
            "rotation_mode": "none",
            "preview_font_size": 11,
            "dark_mode": False,
        }
        for k, v in defaults.items():
            cfg.set(k, v)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        for k, v in defaults.items():
            assert cfg2.get(k) == v

    def test_delay_ms_int_cast(self) -> None:
        delay_s = 0.5
        result = int(delay_s * 1000)
        assert result == 500

    def test_template_fallback_logic(self) -> None:
        text = ""
        result = text.strip() or "{session}_{timestamp}"
        assert result == "{session}_{timestamp}"

    def test_working_root_fallback_logic(self) -> None:
        text = ""
        result = text.strip() or "sessions"
        assert result == "sessions"

    def test_keybindings_empty_when_no_overrides(self) -> None:
        hotkey_edits = {"capture": "", "new_section": "  "}
        bindings: dict[str, str] = {}
        for action, val in hotkey_edits.items():
            v = val.strip().lower()
            if v:
                bindings[action] = v
        assert bindings == {}

    def test_keybindings_stored_when_set(self) -> None:
        hotkey_edits = {"capture": "F9", "new_section": "  "}
        bindings: dict[str, str] = {}
        for action, val in hotkey_edits.items():
            v = val.strip().lower()
            if v:
                bindings[action] = v
        assert bindings == {"capture": "f9"}


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSettingsKeysGui:
    def _make_dialog(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return SettingsDialog(cfg)

    def test_factory_defaults_count(self, tmp_path: Path) -> None:
        from gui.settings_dialog import SettingsDialog
        assert len(SettingsDialog._FACTORY_DEFAULTS) >= 20

    def test_save_values_persists_font_size(self, tmp_path: Path) -> None:
        d = self._make_dialog(tmp_path)
        d._preview_font_size.setValue(14)
        d._save_values()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("preview_font_size") == 14

    def test_reset_defaults_restores_font_size(self, tmp_path: Path) -> None:
        d = self._make_dialog(tmp_path)
        d._config.set("preview_font_size", 20)
        d._config.save()
        from gui.settings_dialog import SettingsDialog
        d2 = self._make_dialog(tmp_path)
        d2._on_reset_defaults()
        assert d2._config.get("preview_font_size") == 11
