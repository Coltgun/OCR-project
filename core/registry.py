"""
Registrable base class — self-registering plugin components via __init_subclass__.

Usage:
    class MyBase(Registrable):
        @abstractmethod
        def do_thing(self) -> None: ...

    class MyImpl(MyBase, register_as="my_impl"):
        def do_thing(self) -> None: ...

    # Auto-registered at import time:
    cls = MyBase.get("my_impl")   # returns MyImpl
    obj = cls()
"""

from __future__ import annotations

from abc import ABC
from typing import ClassVar, Dict, Type, TypeVar

T = TypeVar("T", bound="Registrable")


class Registrable(ABC):
    """Base class for all auto-registering plugin components.

    Subclasses declare a unique name via the class keyword argument:
        class Foo(SomeRegistrable, register_as="foo"): ...

    Abstract intermediate classes (no register_as kwarg) are not registered.
    """

    _registry: ClassVar[Dict[str, Type]] = {}
    registry_name: ClassVar[str]

    def __init_subclass__(cls, register_as: str | None = None, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if register_as is not None:
            if register_as in cls._registry:
                raise ValueError(
                    f"Duplicate registration: '{register_as}' is already registered as "
                    f"{cls._registry[register_as].__qualname__}. "
                    f"Each registered name must be unique."
                )
            cls.registry_name = register_as
            cls._registry[register_as] = cls

    @classmethod
    def get(cls: Type[T], name: str) -> Type[T]:
        """Return the registered subclass for the given name.

        Raises KeyError if no subclass is registered under that name.
        """
        if name not in cls._registry:
            raise KeyError(
                f"No {cls.__name__} registered as '{name}'. "
                f"Available: {list(cls._registry.keys())}"
            )
        return cls._registry[name]  # type: ignore[return-value]

    @classmethod
    def list_registered(cls) -> list[str]:
        """Return all names currently registered under this class."""
        return list(cls._registry.keys())
