"""
Test đơn vị cho DependencyRegistry (backend tự viết, thay dependency-injector).

Soi trực tiếp lớp registry: singleton, inject theo plan, instance dựng sẵn (kể cả
None), factory method, KeyError khi thiếu, không ghi đè override, guard đệ quy, và
an toàn khi nhiều thread cùng dựng lạnh (double-checked locking).
"""
import threading
import time

import pytest

from xime.core.container.config_loader import FactoryEntry
from xime.core.container.graph import DependencyGraph
from xime.core.container.registry import DependencyRegistry


def _registry(resolved, instances=None, factory_entries=None):
    """Helper: dựng registry đã register sẵn từ một resolved map thủ công."""
    reg = DependencyRegistry()
    reg.register(
        resolved,
        DependencyGraph(resolved),
        instances=instances,
        factory_entries=factory_entries,
    )
    return reg


# ===========================================================================
# Sample classes
# ===========================================================================

class Leaf:
    pass


class Branch:
    def __init__(self, leaf: Leaf):
        self.leaf = leaf


class Thing:
    pass


class TokenService:
    def __init__(self, key: str):
        self.key = key


class Unknown:
    pass


# ===========================================================================
# Singleton & injection
# ===========================================================================

class TestSingletonAndInjection:

    def test_singleton_same_instance(self):
        reg = _registry({Leaf: {}})
        assert reg.get(Leaf) is reg.get(Leaf)

    def test_injects_dependency_from_plan(self):
        reg = _registry({Leaf: {}, Branch: {"leaf": Leaf}})
        branch = reg.get(Branch)
        assert isinstance(branch.leaf, Leaf)

    def test_dependency_is_shared_singleton(self):
        reg = _registry({Leaf: {}, Branch: {"leaf": Leaf}})
        branch = reg.get(Branch)
        assert reg.get(Leaf) is branch.leaf


# ===========================================================================
# Pre-built instances (providers.Object equivalent)
# ===========================================================================

class TestPrebuiltInstances:

    def test_returns_prebuilt_instance_as_is(self):
        real = Leaf()
        reg = _registry({Leaf: {}}, instances={Leaf: real})
        assert reg.get(Leaf) is real

    def test_prebuilt_instance_not_shadowed_by_scanned_singleton(self):
        """Instance dựng sẵn không bị Singleton từ scan ghi đè (override thắng)."""
        override = Leaf()
        # Leaf vừa nằm trong resolved (scan) vừa có instance dựng sẵn.
        reg = _registry({Leaf: {}}, instances={Leaf: override})
        assert reg.get(Leaf) is override

    def test_caches_none_value(self):
        """Sentinel _MISSING phân biệt 'chưa cache' với giá trị None hợp lệ."""
        reg = _registry({}, instances={Thing: None})
        assert reg.get(Thing) is None


# ===========================================================================
# Factory method (configure())
# ===========================================================================

class TestFactoryEntries:

    def test_factory_without_dep(self):
        marker = Thing()
        entry = FactoryEntry(provided_type=Thing, factory_fn=lambda: marker)
        reg = _registry({Thing: {}}, factory_entries=[entry])
        assert reg.get(Thing) is marker

    def test_factory_with_injected_dep(self):
        entry = FactoryEntry(
            provided_type=TokenService,
            factory_fn=lambda key: TokenService(key),
            dependencies={"key": str},
        )
        reg = _registry(
            {TokenService: {"key": str}},
            instances={str: "secret"},
            factory_entries=[entry],
        )
        token = reg.get(TokenService)
        assert isinstance(token, TokenService)
        assert token.key == "secret"


# ===========================================================================
# Error paths
# ===========================================================================

class TestErrorPaths:

    def test_get_unregistered_raises_keyerror(self):
        reg = _registry({})
        with pytest.raises(KeyError):
            reg.get(Unknown)

    def test_circular_dependency_guard(self):
        """Phòng vệ: plan tự trỏ vào chính nó → RuntimeError, không treo vô hạn."""
        class SelfRef:
            def __init__(self, other):
                self.other = other

        # Craft thủ công một plan đệ quy (validator thật đã chặn cycle từ trước).
        reg = _registry({SelfRef: {"other": SelfRef}})
        with pytest.raises(RuntimeError, match="Circular"):
            reg.get(SelfRef)


# ===========================================================================
# Thread safety — double-checked locking
# ===========================================================================

class TestConcurrency:

    def test_concurrent_cold_get_builds_once(self):
        """Nhiều thread cùng get() một class chưa warm → chỉ dựng đúng 1 lần."""
        build_count = {"n": 0}
        lock = threading.Lock()

        def slow_factory() -> Thing:
            time.sleep(0.02)            # nới cửa sổ đua để lộ lỗi nếu thiếu khóa
            with lock:
                build_count["n"] += 1
            return Thing()

        entry = FactoryEntry(provided_type=Thing, factory_fn=slow_factory)
        reg = _registry({Thing: {}}, factory_entries=[entry])

        n = 16
        barrier = threading.Barrier(n)
        results: list[object] = []
        results_lock = threading.Lock()

        def worker():
            barrier.wait()              # bắt mọi thread khởi chạy cùng lúc
            obj = reg.get(Thing)
            with results_lock:
                results.append(obj)

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert build_count["n"] == 1
        assert len(results) == n
        assert all(r is results[0] for r in results)
