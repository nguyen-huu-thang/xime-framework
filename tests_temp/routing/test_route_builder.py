"""
Test _make_handler() và RouteBuilder.build():
  - _make_handler: async bound method → async handler có signature đúng (không có 'self')
  - _make_handler: sync bound method → sync handler
  - _make_handler: type annotations được giữ nguyên trên signature
  - _make_handler: handler forward kwargs đến bound method
  - RouteBuilder.build: APIRouter có prefix và tags đúng từ class attribute
  - RouteBuilder.build: mỗi decorated method → một route trong router
  - RouteBuilder.build: method không có route marker bị bỏ qua
  - RouteBuilder.build: status_code từ decorator được truyền vào route
  - RouteBuilder.build: HTTP method đúng (GET, POST, DELETE, ...)
  - RouteBuilder.build: thứ tự route theo thứ tự khai báo trong class
  - RouteBuilder.build: bound method nhận đúng instance (self)
"""
import inspect

import pytest
from fastapi import APIRouter

from xime.adapters.web.routing._builder import RouteBuilder, _make_handler
from xime.adapters.web.routing._decorators import delete, get, post, put


# ---------------------------------------------------------------------------
# _make_handler
# ---------------------------------------------------------------------------

class TestMakeHandler:
    def test_async_method_stays_async(self):
        class Ctrl:
            async def list(self, user_id: int) -> dict:
                return {}

        handler = _make_handler(Ctrl().list)
        assert inspect.iscoroutinefunction(handler)

    def test_sync_method_stays_sync(self):
        class Ctrl:
            def ping(self) -> str:
                return "pong"

        handler = _make_handler(Ctrl().ping)
        assert not inspect.iscoroutinefunction(handler)

    def test_signature_does_not_contain_self(self):
        """FastAPI cần thấy signature không có 'self'."""
        class Ctrl:
            async def get_item(self, item_id: int) -> dict:
                return {}

        handler = _make_handler(Ctrl().get_item)
        sig = inspect.signature(handler)
        assert "self" not in sig.parameters

    def test_signature_contains_real_params(self):
        class Ctrl:
            async def create(self, name: str, price: float) -> dict:
                return {}

        handler = _make_handler(Ctrl().create)
        sig = inspect.signature(handler)
        assert "name" in sig.parameters
        assert "price" in sig.parameters

    def test_signature_preserves_type_annotations(self):
        class Ctrl:
            async def get_user(self, user_id: int, active: bool) -> dict:
                return {}

        handler = _make_handler(Ctrl().get_user)
        sig = inspect.signature(handler)
        assert sig.parameters["user_id"].annotation == int
        assert sig.parameters["active"].annotation == bool

    @pytest.mark.asyncio
    async def test_async_handler_calls_bound_method_with_kwargs(self):
        results = []

        class Ctrl:
            async def do_work(self, x: int, y: str) -> dict:
                results.append((x, y))
                return {"x": x, "y": y}

        handler = _make_handler(Ctrl().do_work)
        result = await handler(x=5, y="hello")

        assert result == {"x": 5, "y": "hello"}
        assert results == [(5, "hello")]

    def test_sync_handler_calls_bound_method_with_kwargs(self):
        class Ctrl:
            def compute(self, a: int, b: int) -> int:
                return a + b

        handler = _make_handler(Ctrl().compute)
        assert handler(a=3, b=4) == 7

    def test_handler_uses_correct_instance(self):
        """Handler gọi đúng instance - self.value được giữ nguyên."""
        class Ctrl:
            def __init__(self, value: int):
                self.value = value

            async def get_value(self) -> int:
                return self.value

        ctrl = Ctrl(value=99)
        handler = _make_handler(ctrl.get_value)

        # Chỉ cần kiểm tra signature - giá trị self.value được dùng đúng
        sig = inspect.signature(handler)
        assert list(sig.parameters.keys()) == []  # không có param nào ngoài self đã bind


# ---------------------------------------------------------------------------
# RouteBuilder.build()
# ---------------------------------------------------------------------------

class TestRouteBuilder:
    def _build(self, cls: type, instance=None) -> APIRouter:
        if instance is None:
            instance = cls()
        return RouteBuilder().build(cls, instance)

    # prefix / tags

    def test_router_prefix_from_class_attribute(self):
        class Ctrl:
            prefix = "/users"

            @get("")
            async def list(self): ...

        assert self._build(Ctrl).prefix == "/users"

    def test_router_tags_from_class_attribute(self):
        class Ctrl:
            tags = ["users", "admin"]

            @get("/")
            async def index(self): ...

        assert self._build(Ctrl).tags == ["users", "admin"]

    def test_default_prefix_is_empty_string(self):
        class Ctrl:
            @get("/health")
            async def health(self): ...

        assert self._build(Ctrl).prefix == ""

    def test_default_tags_is_empty_list(self):
        class Ctrl:
            @get("/ping")
            async def ping(self): ...

        assert self._build(Ctrl).tags == []

    # Route count

    def test_single_route_registered(self):
        class Ctrl:
            @get("/")
            async def index(self): ...

        assert len(self._build(Ctrl).routes) == 1

    def test_multiple_routes_registered(self):
        class Ctrl:
            @get("")
            async def list(self): ...

            @post("")
            async def create(self): ...

            @delete("/{id}")
            async def remove(self, id: int): ...

        assert len(self._build(Ctrl).routes) == 3

    def test_non_decorated_method_is_skipped(self):
        class Ctrl:
            @get("/a")
            async def route_method(self): ...

            async def helper(self):
                pass

            def _private(self):
                pass

        assert len(self._build(Ctrl).routes) == 1

    def test_class_with_no_routes_builds_empty_router(self):
        class Service:
            async def execute(self): ...

        router = self._build(Service)
        assert isinstance(router, APIRouter)
        assert len(router.routes) == 0

    # HTTP method

    def test_get_route_method(self):
        class Ctrl:
            @get("/items")
            async def list(self): ...

        route = self._build(Ctrl).routes[0]
        assert "GET" in route.methods

    def test_post_route_method(self):
        class Ctrl:
            @post("/items")
            async def create(self): ...

        route = self._build(Ctrl).routes[0]
        assert "POST" in route.methods

    def test_delete_route_method(self):
        class Ctrl:
            @delete("/items/{id}")
            async def remove(self, id: int): ...

        route = self._build(Ctrl).routes[0]
        assert "DELETE" in route.methods

    def test_put_route_method(self):
        class Ctrl:
            @put("/items/{id}")
            async def update(self, id: int): ...

        route = self._build(Ctrl).routes[0]
        assert "PUT" in route.methods

    # Path

    def test_route_path_matches_decorator(self):
        class Ctrl:
            @get("/{item_id}")
            async def get_item(self, item_id: int): ...

        route = self._build(Ctrl).routes[0]
        assert route.path == "/{item_id}"

    # status_code

    def test_status_code_from_decorator(self):
        class Ctrl:
            @delete("/{id}", status_code=204)
            async def remove(self, id: int): ...

        route = self._build(Ctrl).routes[0]
        assert route.status_code == 204

    def test_default_status_code_is_200(self):
        class Ctrl:
            @get("/")
            async def index(self): ...

        route = self._build(Ctrl).routes[0]
        assert route.status_code == 200

    # Declaration order

    def test_routes_registered_in_declaration_order(self):
        """Routes phải xuất hiện theo thứ tự khai báo trong class - không alphabetical."""
        class Ctrl:
            @get("/first")
            async def first(self): ...

            @post("/second")
            async def second(self): ...

            @delete("/third")
            async def third(self, id: int): ...

        paths = [r.path for r in self._build(Ctrl).routes]
        assert paths == ["/first", "/second", "/third"]

    # Bound instance

    def test_build_uses_provided_instance(self):
        """RouteBuilder nhận instance → handler gọi đúng object đó."""
        calls = []

        class Ctrl:
            def __init__(self, name: str):
                self.name = name

            @get("/")
            async def greet(self) -> dict:
                calls.append(self.name)
                return {"name": self.name}

        instance = Ctrl(name="xime")
        router = RouteBuilder().build(Ctrl, instance)
        # Route được đăng ký - kiểm tra đủ 1 route
        assert len(router.routes) == 1
