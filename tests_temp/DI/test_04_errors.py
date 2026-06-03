"""
Test fail-fast error cases:
  - CircularDependencyException
  - MissingImplementationException
  - MissingBindingException
  - UnregisteredDependencyException
  - MultipleImplementationException
  - BindingValidationException
"""
from typing import Protocol

import pytest

from xime.core.container.graph import DependencyGraph
from xime.core.container.validator import GraphValidator
from xime.core.exception import (
    BindingValidationException,
    CircularDependencyException,
    MissingBindingException,
    MissingImplementationException,
    MultipleImplementationException,
    UnregisteredDependencyException,
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
    """1 candidate tồn tại nhưng không có binding tường minh → MissingBindingException."""

    class IRepo(Protocol):
        def find(self) -> None: ...

    class JpaRepo:
        def find(self) -> None: ...

    class Service:
        def __init__(self, repo: IRepo): ...

    with pytest.raises(MissingBindingException) as exc_info:
        _validate(
            resolved={Service: {"repo": IRepo}},
            all_classes=[Service, JpaRepo],  # JpaRepo là candidate nhưng không bind
        )

    error_msg = str(exc_info.value)
    assert "IRepo" in error_msg
    assert "JpaRepo" in error_msg


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


# ---------------------------------------------------------------------------
# MissingBindingException — chi tiết attributes và hint
# ---------------------------------------------------------------------------

def test_missing_binding_exception_attributes():
    """MissingBindingException lưu đúng interface_name và candidate_name."""

    class ICacheService(Protocol):
        def get(self, key: str) -> None: ...

    class RedisCacheService:
        def get(self, key: str) -> None: ...

    class UserService:
        def __init__(self, cache: ICacheService): ...

    with pytest.raises(MissingBindingException) as exc_info:
        _validate(
            resolved={UserService: {"cache": ICacheService}},
            all_classes=[UserService, RedisCacheService],
        )

    exc = exc_info.value
    assert exc.interface_name == "ICacheService"
    assert exc.candidate_name == "RedisCacheService"


def test_missing_binding_message_contains_bind_hint():
    """Message phải hướng dẫn dùng dependency.bind()."""

    class IMailer(Protocol):
        def send(self) -> None: ...

    class SmtpMailer:
        def send(self) -> None: ...

    class NotifyService:
        def __init__(self, mailer: IMailer): ...

    with pytest.raises(MissingBindingException) as exc_info:
        _validate(
            resolved={NotifyService: {"mailer": IMailer}},
            all_classes=[NotifyService, SmtpMailer],
        )

    error_msg = str(exc_info.value)
    assert "IMailer" in error_msg
    assert "SmtpMailer" in error_msg
    assert "bind" in error_msg


# ---------------------------------------------------------------------------
# UnregisteredDependencyException
# ---------------------------------------------------------------------------

def test_unregistered_concrete_dependency_raises():
    """Concrete dep không nằm trong scanned packages → UnregisteredDependencyException."""

    class EmailClient:
        pass

    class NotificationService:
        def __init__(self, client: EmailClient): ...

    with pytest.raises(UnregisteredDependencyException) as exc_info:
        _validate(
            resolved={NotificationService: {"client": EmailClient}},
            all_classes=[NotificationService],  # EmailClient không được scan
        )

    error_msg = str(exc_info.value)
    assert "NotificationService" in error_msg
    assert "EmailClient" in error_msg


def test_unregistered_dependency_exception_attributes():
    """Exception lưu đúng dependent_name và dependency_name."""

    class PaymentGateway:
        pass

    class OrderService:
        def __init__(self, gateway: PaymentGateway): ...

    with pytest.raises(UnregisteredDependencyException) as exc_info:
        _validate(
            resolved={OrderService: {"gateway": PaymentGateway}},
            all_classes=[OrderService],
        )

    exc = exc_info.value
    assert exc.dependent_name == "OrderService"
    assert exc.dependency_name == "PaymentGateway"


def test_unregistered_dependency_message_contains_scan_hint():
    """Message phải gợi ý thêm package vào dependency.scan()."""

    class SmsGateway:
        pass

    class AlertService:
        def __init__(self, gateway: SmsGateway): ...

    with pytest.raises(UnregisteredDependencyException) as exc_info:
        _validate(
            resolved={AlertService: {"gateway": SmsGateway}},
            all_classes=[AlertService],
        )

    assert "scan" in str(exc_info.value)


def test_unregistered_dependency_not_raised_when_registered():
    """Không raise khi concrete dep có trong all_classes."""

    class Repo:
        pass

    class Service:
        def __init__(self, repo: Repo): ...

    # Không raise — Repo được scan
    _validate(
        resolved={Service: {"repo": Repo}, Repo: {}},
        all_classes=[Service, Repo],
    )


def test_unregistered_dependency_multiple_missing_raises_on_first():
    """Nhiều dep bị thiếu → raise ngay dep đầu tiên tìm thấy."""

    class ClientA:
        pass

    class ClientB:
        pass

    class MyService:
        def __init__(self, a: ClientA, b: ClientB): ...

    with pytest.raises(UnregisteredDependencyException):
        _validate(
            resolved={MyService: {"a": ClientA, "b": ClientB}},
            all_classes=[MyService],  # cả ClientA và ClientB đều bị thiếu
        )
