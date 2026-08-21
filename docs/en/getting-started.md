# Getting Started

**English** | [Tiếng Việt](../vn/getting-started.md)

**1/9 - Getting Started** · [Core Concepts →](core-concepts.md)

---

This guide walks you through creating your first XIME application.

---

## Prerequisites

- Python 3.11+
- Basic familiarity with async/await
- FastAPI knowledge is helpful but not required

---

## Installation

**Stable (recommended):**

```bash
pip install xime
```

**Latest from source** (may be slightly ahead of the PyPI release):

```bash
git clone https://github.com/nguyen-huu-thang/xime-framework
cd xime-framework
pip install -e .
```

---

## Project Structure

A minimal XIME application needs just one file:

```text
my-service/
└── app/
    └── main.py
```

It is recommended to add `config/` for DI configuration and `test/` for tests:

```text
my-service/
└── app/
    ├── main.py
    └── config/
        └── dependency.py
```

The recommended full structure for a microservice:

```text
my-service/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── rest/
│   │       └── user_controller.py
│   ├── application/
│   │   ├── usecase/
│   │   │   └── get_user_use_case.py
│   │   └── port/
│   │       └── outbound/
│   │           └── user_repository.py   ← Protocol (interface)
│   ├── infrastructure/
│   │   └── persistence/
│   │       └── repository/
│   │           └── jpa_user_repository.py
│   ├── domain/
│   │   └── user.py
│   ├── config/
│   │   ├── dependency.py
│   │   └── routing.py
│   └── resources/
│       └── application.yml
└── test/
```

---

## Step 1 - Define Your Domain

```python
# app/domain/user.py
from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str
```

---

## Step 2 - Define an Interface (Protocol)

```python
# app/application/port/outbound/user_repository.py
from typing import Protocol
from domain.user import User

class UserRepository(Protocol):
    async def find_by_id(self, user_id: int) -> User | None: ...
```

---

## Step 3 - Write the Use Case

```python
# app/application/usecase/get_user_use_case.py
from application.port.outbound.user_repository import UserRepository
from domain.user import User

class GetUserUseCase:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: int) -> User:
        user = await self._repository.find_by_id(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        return user
```

No annotations. No `@service`. XIME discovers this class from the package scan and resolves `UserRepository` automatically.

---

## Step 4 - Write the Implementation

```python
# app/infrastructure/persistence/repository/jpa_user_repository.py
from application.port.outbound.user_repository import UserRepository
from domain.user import User

class JpaUserRepository:
    async def find_by_id(self, user_id: int) -> User | None:
        # database query here
        return User(id=user_id, name="Alice", email="alice@example.com")
```

---

## Step 5 - Write the Controller

```python
# app/api/rest/user_controller.py
from pydantic import BaseModel
from xime.adapters.web.routing import get
from application.usecase.get_user_use_case import GetUserUseCase

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

class UserController:
    prefix = "/users"
    tags = ["users"]

    def __init__(self, use_case: GetUserUseCase) -> None:
        self._use_case = use_case

    @get("/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> UserResponse:
        user = await self._use_case.execute(user_id)
        return UserResponse(id=user.id, name=user.name, email=user.email)
```

---

## Step 6 - Configure Dependency Injection

```python
# app/config/dependency.py
from xime import BindingConfig
from application.port.outbound.user_repository import UserRepository
from infrastructure.persistence.repository.jpa_user_repository import JpaUserRepository

dependency = BindingConfig()

dependency.scan(
    "application.usecase",
    "infrastructure.persistence.repository",
    "api.rest",
)

dependency.bind({
    UserRepository: JpaUserRepository,
})
```

---

## Step 7 - Configure Routing

```python
# app/config/routing.py
from xime.adapters.web.routing import configure_controllers

configure_controllers("api.rest")
```

---

## Step 8 - Runtime Configuration

```yaml
# app/resources/application.yml
server:
  host: 0.0.0.0
  port: 8080

# Optional - XIME configures INFO logging by default; tune or disable it here.
logging:
  level: INFO
```

Logging is set up automatically at startup, so your app prints `INFO` logs out of
the box. See [Configuration → Logging](configuration.md) for the full block and the
opt-out rule.

---

## Step 9 - Entry Point

```python
# app/main.py
from xime import Application
from xime.adapters.web import WebAdapter

app = Application()

if __name__ == "__main__":
    app.use(WebAdapter()).run()
```

`Application()` auto-detects `app.config.dependency` because this file lives inside
the `app` package (run via `python -m app.main`). No explicit `config_module` needed.

To be explicit instead:

```python
app = Application(config_module="app.config.dependency")
```

---

## Step 10 - Run It

```bash
python -m app.main
```

Visit `http://localhost:8080/docs` for the auto-generated Swagger UI.

---

## What Just Happened?

When `Application` starts:

1. It imports `config/dependency.py` and reads `dependency`
2. Scans `application.usecase`, `infrastructure.persistence.repository`, `api.rest`
3. Finds `GetUserUseCase`, `JpaUserRepository`, `UserController`
4. Resolves: `UserController → GetUserUseCase → UserRepository`
5. Checks binding: `UserRepository → JpaUserRepository` ✓
6. Creates singletons in dependency order
7. `WebAdapter` registers `UserController` methods as FastAPI routes

All this happens before the first request. If anything is misconfigured, you get a clear error at startup.

---

## Startup Error Examples

Missing implementation binding:

```text
No Implementation Found
  Interface: UserRepository
  Hint: declare dependency.bind({UserRepository: YourImpl}) in config/dependency.py
```

Circular dependency:

```text
Circular dependency detected:
  UserService → AuthService → TokenService → UserService
```

Missing type hint:

```text
Missing Type Hint
  Class: GetUserUseCase
  Parameter: repository
  Hint: add a type annotation - def __init__(self, repository: UserRepository)
```

---

## Next Steps

Follow the link below to continue reading.

---

**1/9 - Getting Started** · [Core Concepts →](core-concepts.md)
