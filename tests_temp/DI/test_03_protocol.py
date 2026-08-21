"""
Test Protocol binding - dùng lower-level API (không cần scan thật):
  - Protocol → Implementation được resolve đúng
  - Instance trả về là implementation cụ thể
  - Singleton hoạt động qua Protocol binding
"""
from typing import Protocol

import pytest

from xime.core.container.graph import DependencyGraph
from xime.core.container.registry import DependencyRegistry
from xime.core.container.resolver import TypeHintResolver
from xime.core.container.validator import GraphValidator


# ---------------------------------------------------------------------------
# Khai báo sample classes (Protocol + impl + service dùng Protocol)
# ---------------------------------------------------------------------------

class IUserRepository(Protocol):
    def find_by_id(self, user_id: int) -> dict: ...
    def save(self, user: dict) -> None: ...


class JpaUserRepository:
    def find_by_id(self, user_id: int) -> dict:
        return {"id": user_id, "source": "jpa"}

    def save(self, user: dict) -> None:
        pass


class UserService:
    def __init__(self, repository: IUserRepository):
        self.repository = repository

    def get_user(self, user_id: int) -> dict:
        return self.repository.find_by_id(user_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_registry(
    classes: list[type],
    bindings: dict[type, type],
) -> DependencyRegistry:
    resolved = TypeHintResolver().resolve(classes, bindings)
    graph = DependencyGraph(resolved)
    GraphValidator().validate(resolved, graph, bindings, classes)
    registry = DependencyRegistry()
    registry.register(resolved, graph)
    return registry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_protocol_resolved_to_implementation():
    registry = _build_registry(
        classes=[JpaUserRepository, UserService],
        bindings={IUserRepository: JpaUserRepository},
    )
    service = registry.get(UserService)
    assert isinstance(service, UserService)
    assert isinstance(service.repository, JpaUserRepository)


def test_service_calls_through_correct_implementation():
    registry = _build_registry(
        classes=[JpaUserRepository, UserService],
        bindings={IUserRepository: JpaUserRepository},
    )
    result = registry.get(UserService).get_user(7)
    assert result == {"id": 7, "source": "jpa"}


def test_protocol_binding_singleton():
    registry = _build_registry(
        classes=[JpaUserRepository, UserService],
        bindings={IUserRepository: JpaUserRepository},
    )
    s1 = registry.get(UserService)
    s2 = registry.get(UserService)
    assert s1 is s2


def test_swap_implementation():
    """Đổi implementation khác → service dùng implementation mới."""

    class InMemoryUserRepository:
        def find_by_id(self, user_id: int) -> dict:
            return {"id": user_id, "source": "memory"}

        def save(self, user: dict) -> None:
            pass

    registry = _build_registry(
        classes=[InMemoryUserRepository, UserService],
        bindings={IUserRepository: InMemoryUserRepository},
    )
    result = registry.get(UserService).get_user(1)
    assert result["source"] == "memory"

