"""
Test fail-fast error cases:
  - CircularDependencyException
  - MissingImplementationException
  - MultipleImplementationException
  - BindingValidationException
"""
from typing import Protocol

import pytest

from core.container.graph import DependencyGraph
from core.container.validator import GraphValidator
from core.exception import (
    BindingValidationException,
    CircularDependencyException,
    MissingImplementationException,
    MultipleImplementationException,
)


def _validate(resolved, bindings=None, all_classes=None):
    """Shorthand: build graph và validate."""
    bindings = bindings or {}
    all_classes = all_classes or list(resolved.keys())
    graph = DependencyGraph(resolved)
    GraphValidator().validate(resolved, graph, bindings, all_classes)


# ---------------------------------------------------------------------------
# Circular dependency
# ---------------------------------------------------------------------------

def test_circular_dependency_two_nodes():
    class A: pass
    class B: pass

    with pytest.raises(CircularDependencyException) as exc_info:
        _validate({A: {"b": B}, B: {"a": A}})

    assert "A" in str(exc_info.value)
    assert "B" in str(exc_info.value)


def test_circular_dependency_three_nodes():
    class X: pass
    class Y: pass
    class Z: pass

    with pytest.raises(CircularDependencyException):
        _validate({X: {"y": Y}, Y: {"z": Z}, Z: {"x": X}})


def test_self_dependency():
    class Loopy: pass

    with pytest.raises(CircularDependencyException):
        _validate({Loopy: {"self_dep": Loopy}})


# ---------------------------------------------------------------------------
# Missing implementation
# ---------------------------------------------------------------------------

def test_missing_implementation_no_candidates():
    class IRepo(Protocol):
        def find(self) -> None: ...

    class Service:
        def __init__(self, repo: IRepo): ...

    with pytest.raises(MissingImplementationException) as exc_info:
        _validate(
            resolved={Service: {"repo": IRepo}},
            all_classes=[Service],  # không có impl nào
        )

    assert "IRepo" in str(exc_info.value)


def test_missing_implementation_one_candidate_no_binding():
    """1 candidate tồn tại nhưng không có binding tường minh → cũng fail."""

    class IRepo(Protocol):
        def find(self) -> None: ...

    class JpaRepo:
        def find(self) -> None: ...

    class Service:
        def __init__(self, repo: IRepo): ...

    with pytest.raises(MissingImplementationException):
        _validate(
            resolved={Service: {"repo": IRepo}},
            all_classes=[Service, JpaRepo],  # JpaRepo là candidate nhưng không bind
        )


# ---------------------------------------------------------------------------
# Multiple implementations
# ---------------------------------------------------------------------------

def test_multiple_implementations_no_binding():
    class IRepo(Protocol):
        def find(self) -> None: ...

    class ImplA:
        def find(self) -> None: ...

    class ImplB:
        def find(self) -> None: ...

    class Service:
        def __init__(self, repo: IRepo): ...

    with pytest.raises(MultipleImplementationException) as exc_info:
        _validate(
            resolved={Service: {"repo": IRepo}},
            all_classes=[Service, ImplA, ImplB],
        )

    error_msg = str(exc_info.value)
    assert "IRepo" in error_msg
    assert "ImplA" in error_msg
    assert "ImplB" in error_msg


# ---------------------------------------------------------------------------
# Binding validation
# ---------------------------------------------------------------------------

def test_binding_impl_missing_method():
    class IRepo(Protocol):
        def find(self) -> None: ...
        def save(self) -> None: ...

    class IncompleteImpl:
        def find(self) -> None: ...
        # thiếu save()

    class Service:
        def __init__(self, repo: IRepo): ...

    with pytest.raises(BindingValidationException) as exc_info:
        _validate(
            resolved={Service: {"repo": IncompleteImpl}},
            bindings={IRepo: IncompleteImpl},
            all_classes=[Service, IncompleteImpl],
        )

    error_msg = str(exc_info.value)
    assert "IRepo" in error_msg
    assert "IncompleteImpl" in error_msg
    assert "save" in error_msg


def test_binding_with_complete_impl_passes():
    class IRepo(Protocol):
        def find(self) -> None: ...
        def save(self) -> None: ...

    class CompleteImpl:
        def find(self) -> None: ...
        def save(self) -> None: ...

    class Service:
        def __init__(self, repo: IRepo): ...

    # Không raise exception
    _validate(
        resolved={Service: {"repo": CompleteImpl}},
        bindings={IRepo: CompleteImpl},
        all_classes=[Service, CompleteImpl],
    )
