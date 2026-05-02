"""Tests for utils/config_manager.py — ConfigManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


def make_config(tmp_path: Path, data: dict | None = None) -> ConfigManager:
    """Create a ConfigManager backed by a temp file, optionally pre-populated."""
    path = tmp_path / "config.json"
    if data is not None:
        path.write_text(json.dumps(data), encoding="utf-8")
    return ConfigManager(path=path)


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

class TestLoad:
    def test_loads_existing_file(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"key": "value"})
        assert cfg.get("key") == "value"

    def test_missing_file_gives_empty_config(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "nonexistent.json")
        assert cfg.get("anything") is None

    def test_malformed_json_gives_empty_config(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text("{bad json", encoding="utf-8")
        cfg = ConfigManager(path=path)
        assert cfg.get("key") is None


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestGet:
    def test_simple_key(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"mode": "LOCAL_FAST"})
        assert cfg.get("mode") == "LOCAL_FAST"

    def test_dotted_key(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"capture_region": {"x": 42, "y": 10}})
        assert cfg.get("capture_region.x") == 42
        assert cfg.get("capture_region.y") == 10

    def test_deeply_nested_key(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"a": {"b": {"c": 99}}})
        assert cfg.get("a.b.c") == 99

    def test_missing_key_returns_default(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {})
        assert cfg.get("missing") is None
        assert cfg.get("missing", "fallback") == "fallback"

    def test_missing_nested_key_returns_default(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"capture_region": {"x": 0}})
        assert cfg.get("capture_region.z", -1) == -1

    def test_intermediate_non_dict_returns_default(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"key": "string_not_dict"})
        assert cfg.get("key.nested") is None


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------

class TestSet:
    def test_simple_set(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path)
        cfg.set("mode", "API_FULL")
        assert cfg.get("mode") == "API_FULL"

    def test_dotted_set_creates_nested(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path)
        cfg.set("capture_region.x", 100)
        assert cfg.get("capture_region.x") == 100

    def test_dotted_set_preserves_siblings(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"capture_region": {"x": 0, "y": 0}})
        cfg.set("capture_region.x", 200)
        assert cfg.get("capture_region.y") == 0
        assert cfg.get("capture_region.x") == 200

    def test_set_overwrites_existing(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"key": "old"})
        cfg.set("key", "new")
        assert cfg.get("key") == "new"

    def test_deeply_nested_set(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path)
        cfg.set("a.b.c", 42)
        assert cfg.get("a.b.c") == 42


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------

class TestSaveLoadRoundtrip:
    def test_config_save_load_roundtrip(self, tmp_path: Path) -> None:
        """Canonical round-trip test from app_guidelines.md Section 10.6."""
        cfg = ConfigManager(tmp_path / "config.json")
        cfg.set("capture_region.x", 42)
        cfg.set("ocr_pipeline_mode", "LOCAL_FAST")
        cfg.save()

        cfg2 = ConfigManager(tmp_path / "config.json")
        assert cfg2.get("capture_region.x") == 42
        assert cfg2.get("ocr_pipeline_mode") == "LOCAL_FAST"

    def test_save_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "new_config.json"
        cfg = ConfigManager(path=path)
        cfg.set("key", "val")
        cfg.save()
        assert path.exists()

    def test_save_writes_valid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        cfg = ConfigManager(path=path)
        cfg.set("x", 1)
        cfg.save()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["x"] == 1

    def test_unicode_preserved(self, tmp_path: Path) -> None:
        cfg = ConfigManager(tmp_path / "config.json")
        cfg.set("title", "测试标题")
        cfg.save()
        cfg2 = ConfigManager(tmp_path / "config.json")
        assert cfg2.get("title") == "测试标题"


# ---------------------------------------------------------------------------
# convenience wrappers
# ---------------------------------------------------------------------------

class TestConvenienceWrappers:
    def test_get_int(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"vram_budget_mb": 7680})
        assert cfg.get_int("vram_budget_mb") == 7680
        assert isinstance(cfg.get_int("vram_budget_mb"), int)

    def test_get_bool_true(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"paddleocr_use_gpu": True})
        assert cfg.get_bool("paddleocr_use_gpu") is True

    def test_get_bool_false(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"dedup_embedding_enabled": False})
        assert cfg.get_bool("dedup_embedding_enabled") is False

    def test_get_str(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"vram_tier": "8gb"})
        assert cfg.get_str("vram_tier") == "8gb"

    def test_get_int_default(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path)
        assert cfg.get_int("missing", 42) == 42

    def test_get_bool_string_true(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"flag": "true"})
        assert cfg.get_bool("flag") is True


# ---------------------------------------------------------------------------
# data property
# ---------------------------------------------------------------------------

class TestDataProperty:
    def test_data_returns_copy(self, tmp_path: Path) -> None:
        cfg = make_config(tmp_path, {"key": "val"})
        snapshot = cfg.data
        snapshot["injected"] = True
        assert cfg.get("injected") is None
