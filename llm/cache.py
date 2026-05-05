"""
LlmResultCache — in-memory (and optionally disk-backed) result cache for LLM
correction stages.

Cache key: sha1(stage_id + model + system_prompt + text) — unique per
(provider, model, prompt version, input text) tuple so any of those changing
automatically bypasses stale entries.

Only correction stages should use this cache.  Dedup stages must NOT cache
because their output is context-dependent (the duplicate assignments change
with the full batch).

Usage::

    cache = LlmResultCache.from_config(config, working_root)
    hit  = cache.get(stage_id, model, system_prompt, text)
    if hit is None:
        hit = call_llm(text)
    cache.put(stage_id, model, system_prompt, text, hit)
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ENTRIES = 50_000


class LlmResultCache:
    """Memoization cache for LLM correction results.

    Args:
        disk_path:   Optional path to a JSON file for persistence across
                     sessions.  ``None`` means in-memory only.
        max_entries: Maximum number of entries to keep.  When the limit is
                     exceeded the oldest 10 % of entries are evicted (FIFO).
    """

    def __init__(
        self,
        disk_path: Optional[Path] = None,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._disk_path = disk_path
        self._max_entries = max_entries
        self._store: dict[str, str] = {}
        self._order: list[str] = []
        if disk_path is not None:
            self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        stage_id: str,
        model: str,
        system_prompt: str,
        text: str,
    ) -> Optional[str]:
        """Return cached corrected text, or ``None`` on miss."""
        return self._store.get(self._key(stage_id, model, system_prompt, text))

    def put(
        self,
        stage_id: str,
        model: str,
        system_prompt: str,
        text: str,
        corrected: str,
    ) -> None:
        """Store a correction result."""
        key = self._key(stage_id, model, system_prompt, text)
        is_new = key not in self._store
        self._store[key] = corrected
        if is_new:
            self._order.append(key)
            self._evict_if_needed()

    def flush(self) -> None:
        """Persist cache to disk if a disk path was configured."""
        if self._disk_path is None:
            return
        try:
            self._disk_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._disk_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"entries": self._store}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._disk_path)
        except OSError as exc:
            logger.warning("LlmResultCache.flush: could not write %s: %s", self._disk_path, exc)

    def __len__(self) -> int:
        return len(self._store)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        config: dict,
        working_root: Optional[Path] = None,
    ) -> Optional["LlmResultCache"]:
        """Return a cache instance based on config, or ``None`` if disabled.

        Config keys:
            ``llm_result_cache``          "off" | "memory" | "disk"
            ``llm_result_cache_path``     path template (``{working_root_dir}`` replaced)
            ``llm_result_cache_max_entries``  int
        """
        mode = str(config.get("llm_result_cache", "off")).lower()
        if mode == "off":
            return None

        max_entries = int(config.get("llm_result_cache_max_entries", _DEFAULT_MAX_ENTRIES))

        if mode == "disk":
            raw_path: str = str(
                config.get("llm_result_cache_path", "{working_root_dir}/.llm_cache.json")
            )
            root_str = str(working_root) if working_root is not None else "."
            resolved = Path(raw_path.replace("{working_root_dir}", root_str))
            return cls(disk_path=resolved, max_entries=max_entries)

        return cls(disk_path=None, max_entries=max_entries)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _key(stage_id: str, model: str, system_prompt: str, text: str) -> str:
        """Compute cache key as hex SHA-1 of the concatenated inputs."""
        payload = f"{stage_id}\x00{model}\x00{system_prompt}\x00{text}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _evict_if_needed(self) -> None:
        """Evict the oldest 10 % of entries when max_entries is exceeded."""
        if len(self._store) <= self._max_entries:
            return
        evict_count = max(1, self._max_entries // 10)
        to_evict = self._order[:evict_count]
        self._order = self._order[evict_count:]
        for k in to_evict:
            self._store.pop(k, None)

    def _load(self) -> None:
        """Load entries from disk if the cache file exists."""
        if self._disk_path is None or not self._disk_path.exists():
            return
        try:
            data = json.loads(self._disk_path.read_text(encoding="utf-8"))
            entries: dict[str, str] = data.get("entries", {})
            self._store = dict(entries)
            self._order = list(entries.keys())
            if len(self._store) > self._max_entries:
                self._evict_if_needed()
            logger.debug(
                "LlmResultCache: loaded %d entries from %s",
                len(self._store), self._disk_path,
            )
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning(
                "LlmResultCache: could not load %s: %s — starting empty.",
                self._disk_path, exc,
            )
            self._store = {}
            self._order = []
