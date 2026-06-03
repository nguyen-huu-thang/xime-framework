"""
Test XimeContainer full pipeline — happy path:
  - scan → resolve → graph → validate → register → get
  - singleton guarantee
  - class không có dependency cũng được đăng ký
"""
import pytest
from xime.core.container import XimeContainer
from sample.service.user_service import UserService
from sample.service.config_service import ConfigService
from sample.repository.user_repository import UserRepository


@pytest.fixture
def container():
    return (
        XimeContainer()
        .scan("sample.service", "sample.repository")
        .build()
    )


def test_get_service_with_dependency(container):
    service = container.get(UserService)
    assert isinstance(service, UserService)


def test_get_service_without_dependency(container):
    config = container.get(ConfigService)
    assert isinstance(config, ConfigService)


def test_dependency_is_injected(container):
    service = container.get(UserService)
    # UserService phải có repository là UserRepository thật
    assert isinstance(service.repository, UserRepository)


def test_service_works_end_to_end(container):
    service = container.get(UserService)
    result = service.get_user(42)
    assert result == {"id": 42, "name": "Test User"}


def test_singleton_same_instance(container):
    s1 = container.get(UserService)
    s2 = container.get(UserService)
    assert s1 is s2, "Hai lần get() phải trả về cùng một instance (Singleton)"


def test_singleton_dependency_shared(container):
    # UserService.repository và instance UserRepository trực tiếp phải là cùng object
    service = container.get(UserService)
    repo = container.get(UserRepository)
    assert service.repository is repo


def test_get_before_build_raises():
    with pytest.raises(RuntimeError, match="not built"):
        XimeContainer().get(UserService)


def test_build_twice_raises():
    c = XimeContainer().scan("sample.service", "sample.repository").build()
    with pytest.raises(RuntimeError, match="already been called"):
        c.build()


def test_get_unregistered_class_raises():
    """get() với class không được scan → KeyError với tên class trong message."""
    class UnregisteredClass:
        pass

    c = XimeContainer().scan("sample.service", "sample.repository").build()
    with pytest.raises(KeyError, match="UnregisteredClass"):
        c.get(UnregisteredClass)


def test_scan_after_build_raises():
    c = XimeContainer().scan("sample.service", "sample.repository").build()
    with pytest.raises(RuntimeError, match="already built"):
        c.scan("sample.service")


def test_bind_after_build_raises():
    from typing import Protocol

    class IRepo(Protocol):
        def find(self) -> None: ...

    class ImplRepo:
        def find(self) -> None: ...

    c = XimeContainer().scan("sample.service", "sample.repository").build()
    with pytest.raises(RuntimeError, match="already built"):
        c.bind({IRepo: ImplRepo})

