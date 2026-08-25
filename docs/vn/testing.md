# Testing

[English](../en/testing.md) | **Tiếng Việt**

[← Starters](starters.md) · **7/9 - Testing** · [Kiến trúc →](architecture.md)

---

## Triết lý

DI của XIME dựa trên constructor, nghĩa là testing rất đơn giản: tạo object thực với dependency giả, không cần mocking framework cho trường hợp cơ bản.

```python
# Unit test thuần - không cần XIME machinery
def test_create_user():
    repository = FakeUserRepository()
    use_case = CreateUserUseCase(repository=repository)
    result = asyncio.run(use_case.execute(CreateUserCommand(name="Alice")))
    assert result.name == "Alice"
```

---

## Fake Implementation

Viết fake là class Python bình thường. Chúng thỏa mãn Protocol interface theo cấu trúc:

```python
class FakeUserRepository:
    def __init__(self) -> None:
        self._store: dict[int, User] = {}
        self._next_id = 1

    async def find_by_id(self, user_id: int) -> User | None:
        return self._store.get(user_id)

    async def save(self, user: User) -> User:
        user = User(id=self._next_id, name=user.name, email=user.email)
        self._store[self._next_id] = user
        self._next_id += 1
        return user
```

---

## Fake Transaction / Read-only Manager

`xime.testing` cung cấp `FakeTransactionManager` thực thi khối lệnh mà không có transaction database thực:

```python
from xime.testing import FakeTransactionManager

async def test_create_user_with_transaction():
    repository = FakeUserRepository()
    transaction = FakeTransactionManager()
    use_case = CreateUserUseCase(repository=repository, transaction=transaction)

    user = await use_case.execute(CreateUserCommand(name="Bob"))
    assert user.name == "Bob"
```

Usecase chỉ đọc dùng `FakeReadOnlyManager` - bản no-op đối xứng cho khối
`async with self.read_only():`:

```python
from xime.testing import FakeReadOnlyManager

async def test_get_product_detail():
    service = ProductService(
        read_only=FakeReadOnlyManager(),
        products=FakeProductRepository(),
    )
    detail = await service.get_detail("p-1")
    assert detail.name == "Bàn phím"
```

---

## Integration Test với DI Override

Cho integration test dùng DI container thực nhưng hoán đổi component cụ thể:

```python
# test/conftest.py
import pytest
from xime import Application, BindingConfig

@pytest.fixture
async def app():
    binding = BindingConfig()
    binding.scan("my_service.application.usecase", "my_service.infrastructure.persistence.repository")
    binding.bind({
        UserRepository: TestUserRepository,   # override cho test
        TransactionManager: SqlAlchemyTransactionManager,
    })

    async with Application(binding=binding) as app:
        yield app
```

```python
# test/test_create_user.py
async def test_create_user(app):
    use_case = app.get(CreateUserUseCase)
    result = await use_case.execute(CreateUserCommand(name="Charlie"))
    assert result.name == "Charlie"
```

---

## Test Isolation

Mỗi test fixture tạo `Application` mới. Vì singleton sống bên trong `Application` instance (không phải trong module-level global), các test được cô lập hoàn toàn:

```python
@pytest.fixture
async def app():
    async with Application(binding=test_binding) as app:
        yield app
    # Application.stop() được gọi ở đây - tất cả singleton được dispose
```

---

## Testing Controller

Controller là DI singleton. Để test controller, khởi tạo nó với fake use case:

```python
async def test_get_user_controller():
    use_case = FakeGetUserUseCase(user=User(id=1, name="Alice", email="alice@example.com"))
    controller = UserController(use_case=use_case)

    response = await controller.get_user(user_id=1)
    assert response.name == "Alice"
```

Cho HTTP-level test (test routing, middleware, serialization), dùng `WebAdapter.build_app()` để lấy FastAPI instance mà không chạy uvicorn:

```python
from httpx import AsyncClient
from xime.adapters.web import WebAdapter

async def test_get_user_http(app):
    fastapi_app = WebAdapter().build_app(app)
    async with AsyncClient(app=fastapi_app, base_url="http://test") as client:
        response = await client.get("/users/1")
        assert response.status_code == 200
        assert response.json()["name"] == "Alice"
```

---

## Testing với Database thực

Cho test dùng database thực (khuyến nghị cho repository test):

```python
@pytest.fixture
async def db_session(test_engine):
    async with AsyncSession(test_engine) as session:
        yield session
        await session.rollback()   # dọn dẹp sau mỗi test

async def test_save_user(db_session):
    repository = JpaUserRepository(session=db_session)
    user = await repository.save(User(name="Dave", email="dave@example.com"))
    assert user.id is not None
```

Dùng test database (URL riêng, xóa sạch giữa các lần chạy test) thay vì mock database layer.

---

## Module `xime.testing`

| Tiện ích | Mô tả |
| --- | --- |
| `FakeTransactionManager` | Transaction no-op cho unit test |
| `FakeReadOnlyManager` | Khối chỉ đọc no-op cho unit test |
| `override_binding(cls, fake)` | Tạm thời thay thế DI binding |

Thêm testing utility sẽ được bổ sung khi framework trưởng thành.

---

[← Starters](starters.md) · **7/9 - Testing** · [Kiến trúc →](architecture.md)
