"""A constructor parameter with a default value is optional.

The container reads every annotation as a dependency, so before this rule an
ordinary signature could not be registered at all:

    class ModbusClient:
        def __init__(self, device: str = "default") -> None: ...

    dependency.register(ModbusClient)
    # -> UnregisteredDependencyException: Dependency: str

Nothing in a DI container ever supplies `str`, yet the developer had already
said the parameter was optional by giving it a default. Same intent as Spring's
@Autowired(required=false).

The line these tests defend: a parameter WITHOUT a default must still fail
loudly, because that is the overwhelming majority of real dependencies and
losing fail-fast there would hide genuine wiring mistakes.
"""
from typing import Protocol

import pytest

from xime.core.container import XimeContainer
from xime.core.exception import (
    MissingImplementationException,
    UnregisteredDependencyException,
)


class Helper:
    pass


class TestOptionalParametersUseTheirDefault:

    def test_builtin_type_with_default_is_left_alone(self):
        class Service:
            def __init__(self, device: str = "default") -> None:
                self.device = device

        service = XimeContainer().register(Service).build().get(Service)
        assert service.device == "default"

    def test_several_builtin_defaults(self):
        class Service:
            def __init__(
                self, name: str = "x", port: int = 502, ratio: float = 1.5, on: bool = True
            ) -> None:
                self.values = (name, port, ratio, on)

        service = XimeContainer().register(Service).build().get(Service)
        assert service.values == ("x", 502, 1.5, True)

    def test_a_registered_type_is_still_injected_even_with_a_default(self):
        # The rule must not become "defaults are never injected" — when the
        # container CAN supply the type, injection wins over the default.
        sentinel = Helper()

        class Service:
            def __init__(self, helper: Helper = sentinel) -> None:
                self.helper = helper

        container = XimeContainer().register(Helper, Service).build()
        assert container.get(Service).helper is container.get(Helper)
        assert container.get(Service).helper is not sentinel

    def test_mixed_required_and_optional(self):
        class Service:
            def __init__(self, helper: Helper, label: str = "none") -> None:
                self.helper = helper
                self.label = label

        container = XimeContainer().register(Helper, Service).build()
        service = container.get(Service)
        assert service.helper is container.get(Helper)
        assert service.label == "none"

    def test_factory_method_parameters_follow_the_same_rule(self):
        class Config:
            def build_service(self, region: str = "eu") -> Helper:
                helper = Helper()
                helper.region = region
                return helper

        container = XimeContainer().configure(Config).build()
        assert container.get(Helper).region == "eu"


class TestFailFastIsPreserved:

    def test_a_required_concrete_dependency_still_fails(self):
        class Service:
            def __init__(self, helper: Helper) -> None:
                self.helper = helper

        with pytest.raises(UnregisteredDependencyException):
            XimeContainer().register(Service).build()

    def test_a_required_builtin_annotation_still_fails(self):
        # No default means the developer really is asking the container for it.
        class Service:
            def __init__(self, device: str) -> None:
                self.device = device

        with pytest.raises(UnregisteredDependencyException):
            XimeContainer().register(Service).build()

    def test_a_required_protocol_without_implementation_still_fails(self):
        class Store(Protocol):
            def save(self) -> None: ...

        class Service:
            def __init__(self, store: Store) -> None:
                self.store = store

        with pytest.raises(MissingImplementationException):
            XimeContainer().register(Service).build()


class TestTheAcceptedTradeOff:

    def test_an_optional_protocol_without_binding_gets_its_default(self):
        # Documented and deliberate: a Protocol parameter that has a default and
        # nothing to satisfy it receives the default instead of failing. Chosen
        # so the rule is one sentence a reader can hold in their head, and to
        # match @Autowired(required=false).
        class Store(Protocol):
            def save(self) -> None: ...

        class Service:
            def __init__(self, store: Store | None = None) -> None:
                self.store = store

        assert XimeContainer().register(Service).build().get(Service).store is None
