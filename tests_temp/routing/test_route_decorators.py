"""
Test route decorators - @get, @post, @put, @patch, @delete:
  - Gắn RouteInfo metadata vào method, không tạo wrapper
  - HTTP method được set đúng theo từng decorator
  - Path được lưu đúng
  - Default values của RouteInfo (status_code=200, response_model=None, v.v.)
  - kwargs forwarded vào RouteInfo (status_code, response_model, summary, tags, v.v.)
  - Hai handler độc lập nhau (RouteInfo không bị chia sẻ)
"""
import pytest

from xime.adapters.web.routing._decorators import (
    ROUTE_ATTR,
    RouteInfo,
    delete,
    get,
    patch,
    post,
    put,
)


# ---------------------------------------------------------------------------
# Attribute tồn tại sau khi apply decorator
# ---------------------------------------------------------------------------

def test_get_sets_route_attr():
    @get("/users")
    async def handler(): ...

    assert hasattr(handler, ROUTE_ATTR)


def test_route_attr_is_route_info_instance():
    @get("/users")
    async def handler(): ...

    assert isinstance(getattr(handler, ROUTE_ATTR), RouteInfo)


def test_decorator_returns_original_function_not_wrapper():
    """Decorator chỉ thêm attribute, không bọc function - trả về chính function gốc."""
    async def original(): ...

    decorated = get("/users")(original)
    assert decorated is original


# ---------------------------------------------------------------------------
# HTTP method
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("decorator,expected_method", [
    (get,    "GET"),
    (post,   "POST"),
    (put,    "PUT"),
    (patch,  "PATCH"),
    (delete, "DELETE"),
])
def test_http_method_set_correctly(decorator, expected_method):
    @decorator("/test")
    async def handler(): ...

    route_info = getattr(handler, ROUTE_ATTR)
    assert route_info.method == expected_method


# ---------------------------------------------------------------------------
# Path
# ---------------------------------------------------------------------------

def test_path_stored_correctly():
    @get("/users/{user_id}")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).path == "/users/{user_id}"


def test_root_path():
    @get("/")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).path == "/"


def test_empty_path():
    @post("")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).path == ""


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

def test_default_status_code_is_200():
    @get("/")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).status_code == 200


def test_default_response_model_is_none():
    @get("/")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).response_model is None


def test_default_deprecated_is_false():
    @get("/")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).deprecated is False


def test_default_include_in_schema_is_true():
    @get("/")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).include_in_schema is True


def test_default_tags_is_none():
    @get("/")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).tags is None


def test_default_summary_is_none():
    @get("/")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).summary is None


# ---------------------------------------------------------------------------
# kwargs forwarding
# ---------------------------------------------------------------------------

def test_status_code_kwarg():
    @delete("/items/{id}", status_code=204)
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).status_code == 204


def test_response_model_kwarg():
    class MyModel: ...

    @get("/", response_model=MyModel)
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).response_model is MyModel


def test_summary_kwarg():
    @get("/", summary="List all users")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).summary == "List all users"


def test_description_kwarg():
    @get("/", description="Returns paginated list")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).description == "Returns paginated list"


def test_tags_kwarg():
    @get("/", tags=["users", "admin"])
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).tags == ["users", "admin"]


def test_deprecated_kwarg():
    @get("/", deprecated=True)
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).deprecated is True


def test_include_in_schema_false():
    @get("/internal", include_in_schema=False)
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).include_in_schema is False


def test_operation_id_kwarg():
    @get("/", operation_id="listUsers")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).operation_id == "listUsers"


def test_name_kwarg():
    @get("/", name="list_users_route")
    async def handler(): ...

    assert getattr(handler, ROUTE_ATTR).name == "list_users_route"


# ---------------------------------------------------------------------------
# Hai handlers độc lập nhau
# ---------------------------------------------------------------------------

def test_two_handlers_have_independent_route_info():
    @get("/a")
    async def handler_a(): ...

    @post("/b", status_code=201)
    async def handler_b(): ...

    info_a = getattr(handler_a, ROUTE_ATTR)
    info_b = getattr(handler_b, ROUTE_ATTR)

    assert info_a.path == "/a"
    assert info_a.method == "GET"
    assert info_a.status_code == 200
    assert info_b.path == "/b"
    assert info_b.method == "POST"
    assert info_b.status_code == 201


def test_route_info_is_not_shared_between_handlers():
    @get("/x")
    async def handler_x(): ...

    @get("/y")
    async def handler_y(): ...

    assert getattr(handler_x, ROUTE_ATTR) is not getattr(handler_y, ROUTE_ATTR)
