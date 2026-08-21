"""
Test tích hợp routing layer - RouteBuilder → FastAPI → TestClient:
  - GET route trả về response đúng
  - GET với path parameter được parse đúng
  - GET với query parameter được parse đúng
  - POST nhận Pydantic body và trả về response đúng
  - DELETE trả về 204 No Content
  - Controller prefix được gắn vào URL
  - Controller instance được dùng xuyên suốt nhiều request (singleton)
  - Nhiều routes trong một controller đều hoạt động
  - Routes từ nhiều controllers độc lập trên cùng FastAPI app
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from xime.adapters.web.routing._builder import RouteBuilder
from xime.adapters.web.routing._decorators import delete, get, post, put


def _build_app(*controller_classes: type) -> FastAPI:
    """Tạo FastAPI app với các controller đã được đăng ký."""
    app = FastAPI()
    for cls in controller_classes:
        instance = cls()
        router = RouteBuilder().build(cls, instance)
        app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

def test_get_route_returns_200_and_json():
    class HealthController:
        prefix = "/health"

        @get("")
        async def check(self) -> dict:
            return {"status": "ok"}

    client = TestClient(_build_app(HealthController))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_with_path_parameter():
    class ItemController:
        prefix = "/items"

        @get("/{item_id}")
        async def get_item(self, item_id: int) -> dict:
            return {"item_id": item_id}

    client = TestClient(_build_app(ItemController))
    response = client.get("/items/42")
    assert response.status_code == 200
    assert response.json() == {"item_id": 42}


def test_get_with_query_parameter():
    class SearchController:
        prefix = "/search"

        @get("")
        async def search(self, q: str, limit: int = 10) -> dict:
            return {"query": q, "limit": limit}

    client = TestClient(_build_app(SearchController))
    response = client.get("/search?q=python&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "python"
    assert data["limit"] == 5


def test_get_with_default_query_parameter():
    class SearchController:
        prefix = "/search"

        @get("")
        async def search(self, q: str, limit: int = 20) -> dict:
            return {"limit": limit}

    client = TestClient(_build_app(SearchController))
    response = client.get("/search?q=test")
    assert response.json()["limit"] == 20


# ---------------------------------------------------------------------------
# POST
# ---------------------------------------------------------------------------

def test_post_receives_pydantic_body():
    class CreateItem(BaseModel):
        name: str
        price: float

    class ItemController:
        prefix = "/items"

        @post("", status_code=201)
        async def create(self, body: CreateItem) -> dict:
            return {"name": body.name, "price": body.price}

    client = TestClient(_build_app(ItemController))
    response = client.post("/items", json={"name": "Widget", "price": 9.99})
    assert response.status_code == 201
    assert response.json()["name"] == "Widget"
    assert response.json()["price"] == 9.99


def test_post_returns_201_status_code():
    class Ctrl:
        @post("/create", status_code=201)
        async def create(self) -> dict:
            return {"created": True}

    client = TestClient(_build_app(Ctrl))
    assert client.post("/create").status_code == 201


# ---------------------------------------------------------------------------
# PUT / PATCH
# ---------------------------------------------------------------------------

def test_put_route():
    class Ctrl:
        prefix = "/items"

        @put("/{item_id}")
        async def update(self, item_id: int) -> dict:
            return {"updated": item_id}

    client = TestClient(_build_app(Ctrl))
    response = client.put("/items/7")
    assert response.status_code == 200
    assert response.json() == {"updated": 7}


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_delete_route_returns_204():
    class Ctrl:
        prefix = "/items"

        @delete("/{item_id}", status_code=204)
        async def remove(self, item_id: int) -> None:
            return None

    client = TestClient(_build_app(Ctrl))
    response = client.delete("/items/1")
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Controller instance reuse
# ---------------------------------------------------------------------------

def test_controller_instance_is_reused_across_requests():
    """Cùng một instance controller dùng cho mọi request - state được giữ nguyên."""
    call_log: list[int] = []

    class CounterController:
        prefix = "/counter"

        @get("")
        async def count(self) -> dict:
            call_log.append(1)
            return {"calls": len(call_log)}

    instance = CounterController()
    router = RouteBuilder().build(CounterController, instance)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    client.get("/counter")
    response = client.get("/counter")
    assert response.json()["calls"] == 2


# ---------------------------------------------------------------------------
# Multiple routes in one controller
# ---------------------------------------------------------------------------

def test_multiple_routes_in_one_controller():
    class UserController:
        prefix = "/users"

        @get("")
        async def list_users(self) -> list:
            return []

        @get("/{user_id}")
        async def get_user(self, user_id: int) -> dict:
            return {"id": user_id}

        @post("")
        async def create_user(self) -> dict:
            return {"created": True}

    client = TestClient(_build_app(UserController))

    assert client.get("/users").status_code == 200
    assert client.get("/users/5").json() == {"id": 5}
    assert client.post("/users").status_code == 200


# ---------------------------------------------------------------------------
# Multiple controllers on same FastAPI app
# ---------------------------------------------------------------------------

def test_two_controllers_on_same_app():
    class UserController:
        prefix = "/users"

        @get("")
        async def list(self) -> list:
            return ["alice", "bob"]

    class ProductController:
        prefix = "/products"

        @get("")
        async def list(self) -> list:
            return ["widget", "gadget"]

    client = TestClient(_build_app(UserController, ProductController))

    users = client.get("/users").json()
    products = client.get("/products").json()
    assert "alice" in users
    assert "widget" in products


# ---------------------------------------------------------------------------
# URL prefix applied correctly
# ---------------------------------------------------------------------------

def test_prefix_applied_to_all_routes():
    class Ctrl:
        prefix = "/api/v1/items"

        @get("")
        async def list(self) -> list:
            return []

        @post("")
        async def create(self) -> dict:
            return {}

    client = TestClient(_build_app(Ctrl))

    assert client.get("/api/v1/items").status_code == 200
    assert client.post("/api/v1/items").status_code == 200
    assert client.get("/items").status_code == 404  # prefix bắt buộc
