"""
ConfigManager — load, save, and access config.json via dotted-key API.

Usage:
    from utils.config_manager import config_manager

    mode = config_manager.get("ocr_pipeline_mode", default="HYBRID_TIERED")
    config_manager.set("capture_region.x", 100)

Dotted keys traverse nested dicts:
    config_manager.get("capture_region.x")   # config["capture_region"]["x"]
    config_manager.set("confidence_thresholds.high", 0.9)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


class ConfigManager:
    """Loads and persists config.json; exposes a dotted-key get/set API.

    Args:
        path: Path to the config JSON file. Defaults to project-root config.json.
    """

    def __init__(self, path: Path = _DEFAULT_CONFIG_PATH) -> None:
        self._path = path
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        """(Re)load config from disk. Missing file → empty config (no error)."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.debug("ConfigManager: loaded %s", self._path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("ConfigManager: failed to load %s: %s", self._path, exc)
                self._data = {}
        else:
            logger.debug("ConfigManager: %s not found, starting with empty config.", self._path)
            self._data = {}

    def save(self) -> None:
        """Persist current config to disk (atomic write via temp file)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            tmp_path.replace(self._path)
            logger.debug("ConfigManager: saved %s", self._path)
        except OSError as exc:
            logger.error("ConfigManager: failed to save %s: %s", self._path, exc)
            raise

    def get(self, key: str, default: object = None) -> object:
        """Return the value at *key* (dotted path), or *default* if not found.

        Args:
            key:     Dotted key string, e.g. "capture_region.x".
            default: Value returned when any segment of the path is missing.
        """
        parts = key.split(".")
        val: object = self._data
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part, default)
                if val is default:
                    return default
            else:
                return default
        return val

    def set(self, key: str, value: object) -> None:
        """Set the value at *key* (dotted path), creating intermediate dicts as needed.

        Does NOT auto-save — call save() explicitly after batch updates if persistence
        is needed immediately.

        Args:
            key:   Dotted key string, e.g. "capture_region.x".
            value: Value to store.
        """
        parts = key.split(".")
        d = self._data
        for part in parts[:-1]:
            if not isinstance(d.get(part), dict):
                d[part] = {}
            d = d[part]
        d[parts[-1]] = value

    def get_int(self, key: str, default: int = 0) -> int:
        """Convenience wrapper: get as int."""
        return int(self.get(key, default))  # type: ignore[arg-type]

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Convenience wrapper: get as bool."""
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")

    def get_str(self, key: str, default: str = "") -> str:
        """Convenience wrapper: get as str."""
        return str(self.get(key, default))

    @property
    def data(self) -> dict:
        """Read-only snapshot of the full config dict."""
        return dict(self._data)


config_manager: ConfigManager = ConfigManager()
