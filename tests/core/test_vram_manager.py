"""Tests for core/vram_manager.py — VRAMManager and make_vram_manager."""

from __future__ import annotations

import pytest

from core.vram_manager import VRAM_TIER_DEFAULTS, VRAMManager, make_vram_manager


def fresh(total_mb: int = 8192) -> VRAMManager:
    """Return a new VRAMManager with the given budget."""
    return VRAMManager(total_mb=total_mb)


# ---------------------------------------------------------------------------
# can_allocate
# ---------------------------------------------------------------------------

class TestCanAllocate:
    def test_empty_manager_can_allocate_within_budget(self) -> None:
        vm = fresh(8192)
        assert vm.can_allocate("ocr", 1500) is True

    def test_cannot_allocate_more_than_total(self) -> None:
        vm = fresh(1000)
        assert vm.can_allocate("big", 1001) is False

    def test_exactly_at_budget_is_allowed(self) -> None:
        vm = fresh(1000)
        assert vm.can_allocate("exact", 1000) is True

    def test_one_over_budget_rejected(self) -> None:
        vm = fresh(1000)
        assert vm.can_allocate("over", 1001) is False

    def test_partial_fill_then_remaining(self) -> None:
        vm = fresh(8000)
        vm.allocate("ocr", 1500)
        assert vm.can_allocate("bert", 6500) is True
        assert vm.can_allocate("bert", 6501) is False


# ---------------------------------------------------------------------------
# allocate
# ---------------------------------------------------------------------------

class TestAllocate:
    def test_allocate_within_budget_returns_true(self) -> None:
        vm = fresh(8192)
        assert vm.allocate("ocr", 1500) is True

    def test_allocate_over_budget_returns_false(self) -> None:
        vm = fresh(1000)
        assert vm.allocate("big", 2000) is False

    def test_allocate_over_budget_does_not_modify_state(self) -> None:
        vm = fresh(1000)
        vm.allocate("big", 2000)
        assert "big" not in vm.allocations

    def test_allocate_multiple_components(self) -> None:
        vm = fresh(8192)
        vm.allocate("ocr", 1500)
        vm.allocate("bert", 2000)
        assert vm.used_mb == 3500

    def test_second_allocation_fills_remaining_budget(self) -> None:
        vm = fresh(3000)
        vm.allocate("ocr", 1500)
        assert vm.allocate("bert", 1500) is True
        assert vm.used_mb == 3000

    def test_second_allocation_exceeds_remaining_budget(self) -> None:
        vm = fresh(3000)
        vm.allocate("ocr", 1500)
        assert vm.allocate("bert", 1501) is False

    def test_re_allocate_updates_existing_slot(self) -> None:
        vm = fresh(8192)
        vm.allocate("ocr", 1500)
        vm.allocate("ocr", 2000)
        assert vm.allocations["ocr"] == 2000
        assert vm.used_mb == 2000


# ---------------------------------------------------------------------------
# release
# ---------------------------------------------------------------------------

class TestRelease:
    def test_release_frees_slot(self) -> None:
        vm = fresh(8192)
        vm.allocate("ocr", 1500)
        vm.release("ocr")
        assert "ocr" not in vm.allocations

    def test_release_updates_used_mb(self) -> None:
        vm = fresh(8192)
        vm.allocate("ocr", 1500)
        vm.allocate("bert", 2000)
        vm.release("ocr")
        assert vm.used_mb == 2000

    def test_release_nonexistent_is_noop(self) -> None:
        vm = fresh(8192)
        vm.release("nonexistent")
        assert vm.used_mb == 0

    def test_release_then_reallocate(self) -> None:
        vm = fresh(2000)
        vm.allocate("ocr", 2000)
        vm.release("ocr")
        assert vm.allocate("bert", 2000) is True


# ---------------------------------------------------------------------------
# available_mb / used_mb
# ---------------------------------------------------------------------------

class TestProperties:
    def test_available_mb_full_when_empty(self) -> None:
        vm = fresh(8192)
        assert vm.available_mb == 8192

    def test_used_mb_zero_when_empty(self) -> None:
        vm = fresh(8192)
        assert vm.used_mb == 0

    def test_available_decreases_after_allocate(self) -> None:
        vm = fresh(8192)
        vm.allocate("ocr", 1500)
        assert vm.available_mb == 6692

    def test_used_increases_after_allocate(self) -> None:
        vm = fresh(8192)
        vm.allocate("ocr", 1500)
        assert vm.used_mb == 1500

    def test_available_restores_after_release(self) -> None:
        vm = fresh(8192)
        vm.allocate("ocr", 1500)
        vm.release("ocr")
        assert vm.available_mb == 8192

    def test_allocations_returns_copy(self) -> None:
        vm = fresh(8192)
        vm.allocate("ocr", 1500)
        snapshot = vm.allocations
        snapshot["hacked"] = 9999
        assert "hacked" not in vm._allocated


# ---------------------------------------------------------------------------
# make_vram_manager (factory)
# ---------------------------------------------------------------------------

class TestMakeVramManager:
    def test_8gb_tier_sets_correct_budget(self) -> None:
        vm = make_vram_manager({"vram_tier": "8gb"})
        assert vm.total_mb == VRAM_TIER_DEFAULTS["8gb"]

    def test_16gb_tier_sets_correct_budget(self) -> None:
        vm = make_vram_manager({"vram_tier": "16gb"})
        assert vm.total_mb == VRAM_TIER_DEFAULTS["16gb"]

    def test_unknown_tier_falls_back_to_8gb(self) -> None:
        vm = make_vram_manager({"vram_tier": "unknown"})
        assert vm.total_mb == VRAM_TIER_DEFAULTS["8gb"]

    def test_vram_budget_mb_overrides_tier_default(self) -> None:
        vm = make_vram_manager({"vram_tier": "8gb", "vram_budget_mb": 4096})
        assert vm.total_mb == 4096

    def test_missing_tier_defaults_to_8gb(self) -> None:
        vm = make_vram_manager({})
        assert vm.total_mb == VRAM_TIER_DEFAULTS["8gb"]

    def test_tier_defaults_match_documented_values(self) -> None:
        assert VRAM_TIER_DEFAULTS["8gb"] == 7680
        assert VRAM_TIER_DEFAULTS["16gb"] == 15360


# ---------------------------------------------------------------------------
# init_from_config (singleton wiring)
# ---------------------------------------------------------------------------

class TestInitFromConfig:
    def test_init_from_config_updates_singleton(self) -> None:
        import core.vram_manager as vm_module
        from core.vram_manager import init_from_config
        original_total = vm_module.vram_manager.total_mb
        try:
            init_from_config({"vram_tier": "16gb"})
            assert vm_module.vram_manager.total_mb == VRAM_TIER_DEFAULTS["16gb"]
        finally:
            init_from_config({"vram_tier": "8gb"})
            assert vm_module.vram_manager.total_mb == original_total

    def test_init_from_config_override_budget(self) -> None:
        import core.vram_manager as vm_module
        from core.vram_manager import init_from_config
        original_total = vm_module.vram_manager.total_mb
        try:
            init_from_config({"vram_tier": "8gb", "vram_budget_mb": 4096})
            assert vm_module.vram_manager.total_mb == 4096
        finally:
            init_from_config({"vram_tier": "8gb"})
