"""
VRAMManager — central VRAM budget tracker.

All model-loading components must call allocate() before loading a model
and release() after unloading. The singleton instance is initialised from
config at application startup.

Usage:
    from core.vram_manager import vram_manager

    if vram_manager.allocate("paddleocr", mb=1500):
        engine.load()
    else:
        raise RuntimeError("Not enough VRAM to load PaddleOCR")

    # ... use engine ...

    engine.unload()
    vram_manager.release("paddleocr")
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

VRAM_TIER_DEFAULTS: dict[str, int] = {
    "8gb": 7680,
    "16gb": 15360,
}


class VRAMManager:
    """Tracks VRAM allocations and enforces the per-tier budget.

    Args:
        total_mb: Total safe VRAM budget in megabytes.
    """

    def __init__(self, total_mb: int) -> None:
        self.total_mb = total_mb
        self._allocated: dict[str, int] = {}

    def can_allocate(self, name: str, mb: int) -> bool:
        """Return True if *mb* additional MB can be allocated without exceeding budget."""
        current = sum(self._allocated.values())
        return (current + mb) <= self.total_mb

    def allocate(self, name: str, mb: int) -> bool:
        """Reserve *mb* MB for component *name*.

        Returns True on success, False if the budget would be exceeded.
        If *name* is already allocated, the old allocation is replaced.
        """
        if name in self._allocated:
            logger.warning(
                "VRAMManager: '%s' re-allocated (was %d MB, now %d MB). "
                "Call release() before re-allocating.",
                name,
                self._allocated[name],
                mb,
            )
            self._allocated[name] = mb
            return True

        if not self.can_allocate(name, mb):
            logger.error(
                "VRAMManager: cannot allocate %d MB for '%s'. "
                "Available: %d MB, Budget: %d MB. Current: %s",
                mb,
                name,
                self.available_mb,
                self.total_mb,
                self._allocated,
            )
            return False

        self._allocated[name] = mb
        logger.debug(
            "VRAMManager: allocated %d MB for '%s'. Used: %d / %d MB.",
            mb,
            name,
            self.used_mb,
            self.total_mb,
        )
        return True

    def release(self, name: str) -> None:
        """Free the allocation for component *name*. No-op if not allocated."""
        released = self._allocated.pop(name, None)
        if released is not None:
            logger.debug(
                "VRAMManager: released %d MB from '%s'. Used: %d / %d MB.",
                released,
                name,
                self.used_mb,
                self.total_mb,
            )
        else:
            logger.warning("VRAMManager: release('%s') called but not allocated.", name)

    @property
    def available_mb(self) -> int:
        """MB remaining before the budget is exhausted."""
        return self.total_mb - self.used_mb

    @property
    def used_mb(self) -> int:
        """Total MB currently allocated."""
        return sum(self._allocated.values())

    @property
    def allocations(self) -> dict[str, int]:
        """Read-only snapshot of current allocations {name: mb}."""
        return dict(self._allocated)


def make_vram_manager(config: dict) -> VRAMManager:
    """Create a VRAMManager from a config dict.

    Reads 'vram_tier' to pick the default budget, then allows
    'vram_budget_mb' to override it explicitly.
    """
    tier = config.get("vram_tier", "8gb")
    default_budget = VRAM_TIER_DEFAULTS.get(tier, VRAM_TIER_DEFAULTS["8gb"])
    total_mb = int(config.get("vram_budget_mb", default_budget))
    logger.info("VRAMManager: initialised with %d MB budget (tier=%s).", total_mb, tier)
    return VRAMManager(total_mb=total_mb)


vram_manager: VRAMManager = VRAMManager(total_mb=VRAM_TIER_DEFAULTS["8gb"])


def init_from_config(config: dict) -> None:
    """Re-initialise the module-level singleton from the application config.

    Call this once in main.py after loading config, before any model loads.

    Args:
        config: Full application config dict (from ConfigManager.data).
    """
    global vram_manager
    vram_manager = make_vram_manager(config)
    logger.info(
        "VRAMManager singleton re-initialised: %d MB (tier=%s).",
        vram_manager.total_mb,
        config.get("vram_tier", "8gb"),
    )
