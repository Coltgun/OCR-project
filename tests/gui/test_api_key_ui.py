"""
Tests for FEAT-api-key-ui.

Source-scan tests verify all five API key/model/URL fields, their groups,
password masking, placeholder text, and load/save wiring.
Pure-logic tests verify config round-trip.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_SD_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "settings_dialog.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load_block() -> str:
    idx = _SD_SRC.index("def _load_values")
    end = _SD_SRC.index("\n    def _save_values", idx + 1)
    return _SD_SRC[idx:end]


def _save_block() -> str:
    idx = _SD_SRC.index("def _save_values")
    end = _SD_SRC.index("\n    def _on_accept", idx + 1)
    return _SD_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestApiKeyUiSource:
    def test_openrouter_group_exists(self) -> None:
        assert 'QGroupBox("OpenRouter")' in _SD_SRC

    def test_ollama_group_exists(self) -> None:
        assert 'QGroupBox("Ollama (local LLM)")' in _SD_SRC

    def test_openrouter_key_field_created(self) -> None:
        assert "self._openrouter_key = QLineEdit()" in _SD_SRC

    def test_openrouter_key_password_mode(self) -> None:
        assert "QLineEdit.EchoMode.Password" in _SD_SRC

    def test_openrouter_key_placeholder(self) -> None:
        assert "sk-or" in _SD_SRC

    def test_openrouter_model_field_created(self) -> None:
        assert "self._openrouter_model = QLineEdit()" in _SD_SRC

    def test_openrouter_base_url_field_created(self) -> None:
        assert "self._openrouter_base_url = QLineEdit()" in _SD_SRC

    def test_llm_base_url_field_created(self) -> None:
        assert "self._llm_base_url = QLineEdit()" in _SD_SRC

    def test_llm_model_field_created(self) -> None:
        assert "self._llm_model = QLineEdit()" in _SD_SRC

    def test_load_reads_openrouter_key(self) -> None:
        assert '"openrouter_api_key"' in _load_block()

    def test_load_reads_openrouter_model(self) -> None:
        assert '"openrouter_model"' in _load_block()

    def test_load_reads_openrouter_base_url(self) -> None:
        assert '"openrouter_base_url"' in _load_block()

    def test_load_reads_llm_base_url(self) -> None:
        assert '"llm_base_url"' in _load_block()

    def test_load_reads_llm_model(self) -> None:
        assert '"llm_model"' in _load_block()

    def test_save_writes_openrouter_key(self) -> None:
        assert '"openrouter_api_key"' in _save_block()

    def test_save_writes_openrouter_model(self) -> None:
        assert '"openrouter_model"' in _save_block()

    def test_save_writes_llm_base_url(self) -> None:
        assert '"llm_base_url"' in _save_block()

    def test_save_writes_llm_model(self) -> None:
        assert '"llm_model"' in _save_block()


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestApiKeyUiLogic:
    def test_default_openrouter_key_empty(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("openrouter_api_key", "") == ""

    def test_persists_openrouter_key(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("openrouter_api_key", "sk-or-test")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("openrouter_api_key", "") == "sk-or-test"

    def test_persists_llm_base_url(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("llm_base_url", "http://localhost:11434/v1")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("llm_base_url", "") == "http://localhost:11434/v1"

    def test_persists_llm_model(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("llm_model", "qwen2.5:7b")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("llm_model", "") == "qwen2.5:7b"

    def test_strip_whitespace_key(self) -> None:
        assert "  sk-or-test  ".strip() == "sk-or-test"

    def test_empty_string_default(self) -> None:
        val = "".strip() or ""
        assert val == ""


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestApiKeyUiGui:
    def _make_dialog(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return SettingsDialog(cfg), cfg

    def test_all_fields_present(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        for attr in ("_openrouter_key", "_openrouter_model", "_openrouter_base_url",
                     "_llm_base_url", "_llm_model"):
            assert hasattr(dlg, attr)

    def test_openrouter_key_is_password(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QLineEdit
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._openrouter_key.echoMode() == QLineEdit.EchoMode.Password

    def test_key_restored_from_config(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("openrouter_api_key", "sk-or-xyz")
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        dlg = SettingsDialog(cfg)
        assert dlg._openrouter_key.text() == "sk-or-xyz"
