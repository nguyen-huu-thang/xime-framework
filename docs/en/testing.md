# Testing

**English** | [Tiếng Việt](../vn/testing.md)

---

## Philosophy

XIME's DI is constructor-based, which means testing is straightforward: create real objects with fake dependencies, no mocking framework needed for the basic case.

```python
# Pure unit test — no XIME machinery involved
def test_create_user():
    repository = FakeUserRepository()
    use_case = CreateUserUseCase(repository=repository)
    result = asyncio.run(use_case.execute(CreateUserCommand(name="Alice")))
    assert result.name == "Alice"
```

---

## Fake Implementations

Write fakes as plain Python classes. They satisfy the Protocol interface structurally:

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

## Fake Transaction Manager

`xime.testing` provides a `FakeTransactionManager` that executes the block without a real database transaction:

```python
from xime.testing import FakeTransactionManager

async def test_create_user_with_transaction():
    repository = FakeUserRepository()
    transaction = FakeTransactionManager()
    use_case = CreateUserUseCase(repository=repository, transaction=transaction)

    user = await use_case.execute(CreateUserCommand(name="Bob"))
    assert user.name == "Bob"
```

---

## Integration Tests with DI Override

For integration tests that use the real DI container but swap specific components:

```python
# test/conftest.py
import pytest
from xime import Application, BindingConfig

@pytest.fixture
async def app():
    binding = BindingConfig()
    binding.scan("application.usecase", "infrastructure.persistence.repository")
    binding.bind({
        UserRepository: TestUserRepository,   # override for tests
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

Each test fixture creates a fresh `Application`. Because singletons live inside the `Application` instance (not in module-level globals), tests are fully isolated:

```python
@pytest.fixture
async def app():
    async with Application(binding=test_binding) as app:
        yield app
    # Application.stop() is called here — all singletons are disposed
```

---

## Testing Controllers

Controllers are DI singletons. To test a controller, instantiate it with fake use cases:

```python
async def test_get_user_controller():
    use_case = FakeGetUserUseCase(user=User(id=1, name="Alice", email="alice@example.com"))
    controller = UserController(use_case=use_case)

    response = await controller.get_user(user_id=1)
    assert response.name == "Alice"
```

For HTTP-level tests (testing routing, middleware, serialization), use `WebAdapter.build_app()` to get the FastAPI instance without running uvicorn:

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

## Testing with Real Database

For tests that use a real database (recommended for repository tests):

```python
@pytest.fixture
async def db_session(test_engine):
    async with AsyncSession(test_engine) as session:
        yield session
        await session.rollback()   # clean up after each test

async def test_save_user(db_session):
    repository = JpaUserRepository(session=db_session)
    user = await repository.save(User(name="Dave", email="dave@example.com"))
    assert user.id is not None
```

Use a test database (separate URL, wiped between test runs) rather than mocking the database layer.

---

## `xime.testing` Module

| Utility | Description |
| --- | --- |
| `FakeTransactionManager` | No-op transaction for unit tests |
| `override_binding(cls, fake)` | Temporarily replace a DI binding |

More testing utilities will be added as the framework matures.
