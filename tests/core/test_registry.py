"""Tests for core/registry.py — Registrable base class."""

from __future__ import annotations

import pytest

from core.registry import Registrable


# ---------------------------------------------------------------------------
# Helpers: fresh isolated registries per test
# ---------------------------------------------------------------------------

def make_base() -> type:
    """Return a brand-new Registrable subclass with its own empty registry."""

    class _Base(Registrable):
        pass

    _Base._registry = {}
    return _Base


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_concrete_subclass_is_registered(self) -> None:
        Base = make_base()

        class Impl(Base, register_as="impl_a"):
            pass

        assert "impl_a" in Base._registry
        assert Base._registry["impl_a"] is Impl

    def test_abstract_intermediate_not_registered(self) -> None:
        Base = make_base()

        class Middle(Base):
            pass

        assert "Middle" not in Base._registry
        assert len(Base._registry) == 0

    def test_registry_name_attr_set_on_class(self) -> None:
        Base = make_base()

        class Impl(Base, register_as="named_one"):
            pass

        assert Impl.registry_name == "named_one"

    def test_multiple_subclasses_registered_independently(self) -> None:
        Base = make_base()

        class ImplX(Base, register_as="x"):
            pass

        class ImplY(Base, register_as="y"):
            pass

        assert set(Base._registry.keys()) == {"x", "y"}

    def test_duplicate_name_raises_value_error(self) -> None:
        Base = make_base()

        class ImplA(Base, register_as="dup"):
            pass

        with pytest.raises(ValueError, match="dup"):
            class ImplB(Base, register_as="dup"):
                pass


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_returns_correct_class(self) -> None:
        Base = make_base()

        class Impl(Base, register_as="get_test"):
            pass

        assert Base.get("get_test") is Impl

    def test_get_unknown_name_raises_key_error(self) -> None:
        Base = make_base()

        with pytest.raises(KeyError, match="nonexistent"):
            Base.get("nonexistent")

    def test_get_error_message_lists_available(self) -> None:
        Base = make_base()

        class Impl(Base, register_as="available_one"):
            pass

        with pytest.raises(KeyError, match="available_one"):
            Base.get("missing")

    def test_get_returns_instantiable_class(self) -> None:
        Base = make_base()

        class Impl(Base, register_as="instantiable"):
            def value(self) -> int:
                return 42

        cls = Base.get("instantiable")
        assert cls().value() == 42


# ---------------------------------------------------------------------------
# list_registered()
# ---------------------------------------------------------------------------

class TestListRegistered:
    def test_empty_registry_returns_empty_list(self) -> None:
        Base = make_base()
        assert Base.list_registered() == []

    def test_lists_all_registered_names(self) -> None:
        Base = make_base()

        class A(Base, register_as="alpha"):
            pass

        class B(Base, register_as="beta"):
            pass

        result = Base.list_registered()
        assert sorted(result) == ["alpha", "beta"]

    def test_list_registered_returns_copy(self) -> None:
        Base = make_base()

        class A(Base, register_as="solo"):
            pass

        lst = Base.list_registered()
        lst.append("hacked")
        assert "hacked" not in Base._registry


# ---------------------------------------------------------------------------
# Registry isolation between different Registrable subclasses
# ---------------------------------------------------------------------------

class TestRegistryIsolation:
    def test_separate_bases_have_separate_registries(self) -> None:
        Base1 = make_base()
        Base2 = make_base()

        class Impl1(Base1, register_as="shared_name"):
            pass

        class Impl2(Base2, register_as="shared_name"):
            pass

        assert Base1.get("shared_name") is Impl1
        assert Base2.get("shared_name") is Impl2
        assert Base1._registry is not Base2._registry
