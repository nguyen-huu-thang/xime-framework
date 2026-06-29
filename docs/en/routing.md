# Routing

**English** | [Tiếng Việt](../vn/routing.md)

[← Configuration](configuration.md) · **4/9 — Routing** · [Transaction →](transaction.md)

---

XIME uses class-based controllers. A controller is a DI singleton whose methods are automatically registered as FastAPI routes.

---

## Basic Controller

```python
# app/api/rest/user_controller.py
from pydantic import BaseModel
from xime.adapters.web.routing import get, post, put, delete

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

class CreateUserRequest(BaseModel):
    name: str
    email: str

class UserController:
    prefix = "/users"
    tags = ["users"]

    def __init__(self, use_case: UserUseCase) -> None:
        self._use_case = use_case

    @get("/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> UserResponse:
        return await self._use_case.get(user_id)

    @post("", response_model=UserResponse, status_code=201)
    async def create_user(self, body: CreateUserRequest) -> UserResponse:
        return await self._use_case.create(body)

    @put("/{user_id}", response_model=UserResponse)
    async def update_user(self, user_id: int, body: CreateUserRequest) -> UserResponse:
        return await self._use_case.update(user_id, body)

    @delete("/{user_id}", status_code=204)
    async def delete_user(self, user_id: int) -> None:
        await self._use_case.delete(user_id)
```

---

## Route Decorators

| Decorator | HTTP Method |
| --- | --- |
| `@get(path, ...)` | GET |
| `@post(path, ...)` | POST |
| `@put(path, ...)` | PUT |
| `@patch(path, ...)` | PATCH |
| `@delete(path, ...)` | DELETE |

All decorators accept FastAPI `add_api_route()` parameters:

```python
@get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get a user by ID",
    tags=["users"],
    status_code=200,
    deprecated=False,
)
async def get_user(self, user_id: int) -> UserResponse:
    ...
```

---

## Controller Registration

Declare controller packages in `config/routing.py`:

```python
# config/routing.py
from xime.adapters.web.routing import configure_controllers

configure_controllers("api.rest")
configure_controllers("api.internal")  # multiple packages supported
```

Controllers must also be in the DI scan list:

```python
# config/dependency.py
dependency.scan("api.rest", "api.internal", ...)
```

**Note:** the requirement to list the package in both places is a known limitation. A future version may allow `configure_controllers()` to automatically add to the DI scan.

---

## What Makes a Class a Controller?

A class becomes a controller when:

1. It has at least one method decorated with `@get`, `@post`, `@put`, `@patch`, or `@delete`
2. Its package is registered via `configure_controllers()`

There is no `@Controller` annotation. The decorators on methods are the signal.

---

## How Route Registration Works

XIME registers routes **after** all singletons are created, inside the FastAPI lifespan:

```text
WebAdapter.build() → creates FastAPI app with lifespan
[uvicorn starts]
  lifespan begins
  → application.start()          ← DI builds singletons
  → _register_controllers()
      → scan controller classes
      → get instances from DI container
      → build FastAPI routes
      → app.include_router(router)
  → yield                        ← server accepts requests
```

This order matters: controller instances only exist after DI completes.

---

## Path Parameters

Path parameters are defined in the path string and declared as method parameters with the same name:

```python
@get("/{user_id}/orders/{order_id}")
async def get_order(self, user_id: int, order_id: int) -> OrderResponse:
    ...
```

FastAPI infers path vs query vs body parameters from the method signature.

---

## Request Body

Pydantic models in the method signature become the request body:

```python
class CreateOrderRequest(BaseModel):
    product_id: int
    quantity: int

@post("/{user_id}/orders", response_model=OrderResponse, status_code=201)
async def create_order(self, user_id: int, body: CreateOrderRequest) -> OrderResponse:
    ...
```

---

## Query Parameters

Simple types (str, int, bool) that are not path parameters become query parameters:

```python
@get("")
async def list_users(self, page: int = 1, size: int = 20, active: bool = True) -> list[UserResponse]:
    ...
```

Generated URL: `GET /users?page=2&size=10&active=true`

---

## Controller as a DI Singleton

Controllers participate fully in DI. They can inject use cases, services, or any other DI-managed component:

```python
class OrderController:
    prefix = "/orders"

    def __init__(
        self,
        create_order: CreateOrderUseCase,
        get_order: GetOrderUseCase,
        cancel_order: CancelOrderUseCase,
    ) -> None:
        self._create = create_order
        self._get = get_order
        self._cancel = cancel_order
```

---

## Route Order

Routes are registered in the **order they are declared** in the class (Python 3.7+ dict insertion order). This matters for FastAPI when paths overlap:

```python
@get("/me")          # registered first — matched before /{user_id}
async def get_me(self) -> UserResponse: ...

@get("/{user_id}")   # registered second
async def get_user(self, user_id: int) -> UserResponse: ...
```

---

## Middleware and Exception Handlers

The web adapter installs `RequestContextMiddleware` (and `JwtAuthMiddleware`
when the JWT starter is used) automatically. To add your own middleware or map
exceptions to responses, declare them in the config layer following the
`configure_*` pattern - no `WebAdapter` subclassing.

**Custom middleware** — `configure_middleware(cls, **options)`:

```python
# config/web.py
from xime.adapters.web import configure_middleware
from starlette.middleware.cors import CORSMiddleware

configure_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])
```

Your middleware sits between `RequestContextMiddleware` (outermost) and
`JwtAuthMiddleware` (innermost), so e.g. CORS preflight is handled before auth.
Among your middleware, the one declared first runs first.

**Middleware needing DI services / runtime config** (since 0.6.1) — `configure_middleware`
only takes *static* options. When your own middleware needs a singleton from the
DI container or a value from runtime config (only known after the container is
built), use the `Inject` / `FromConfig` markers as option values instead of
subclassing `WebAdapter`. The framework resolves them at `build_app()`:

```python
# config/web.py
from xime.adapters.web import configure_middleware, Inject, FromConfig
from app.security.jwt_middleware import JwtMiddleware
from app.service.authentication_service import AuthenticationService
from app.service.user_service import UserService

configure_middleware(
    JwtMiddleware,
    auth_svc=Inject(AuthenticationService),   # → app.get(AuthenticationService)
    user_svc=Inject(UserService),
    realm=FromConfig("auth.realm", "default"),  # → RuntimeConfig.get("auth.realm", ...)
)
```

- `Inject(SomeType)` resolves to the DI singleton; a missing binding fails fast at startup.
- `FromConfig("a.b", default)` reads `RuntimeConfig` via dot-notation, falling back to `default`.
- Non-marker values pass through unchanged (fully backward compatible).

**CORS** (since 0.6.1) — `configure_cors(...)` is a first-class helper. Any
argument you leave unset is read from `application.yml` under `cors.<name>`,
falling back to Starlette's defaults, so operators tune CORS via YAML without
touching code. Declare it before other middleware so it stays outermost.

```python
# config/web.py
from xime.adapters.web import configure_cors

configure_cors(allow_origins=["http://localhost:3000"], allow_credentials=True)
# or configure_cors()  → read everything from the cors.* block in application.yml
```

**Global exception handlers** — `configure_exception_handlers({Exc: handler})`:

```python
# config/web.py
from xime.adapters.web import configure_exception_handlers

async def app_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"errorKey": exc.key, "code": exc.code, "message": str(exc)},
    )

configure_exception_handlers({AppException: app_exception_handler})
```

Handlers use FastAPI's `(request, exc) -> Response` signature and are applied to
the app in `build_app()`, so they work both when serving and in HTTP integration
tests - no need to repeat `try/except` in every controller.

Both functions are partitioned by `server_id` (the second argument), matching
multi-server setups.

---

## Known Limitations

- **Two-package declaration** — must list in both `dependency.scan()` and `configure_controllers()`
- **`__all__` not respected by controller scanner** — all controller classes in the package are found regardless of `__all__`
- **WebSocket and gRPC routing** — not yet in scope for class-based controllers

---

[← Configuration](configuration.md) · **4/9 — Routing** · [Transaction →](transaction.md)
