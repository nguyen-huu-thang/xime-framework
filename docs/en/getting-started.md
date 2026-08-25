# Getting Started

**English** | [Tiếng Việt](../vn/getting-started.md)

**1/9 - Getting Started** · [Core Concepts →](core-concepts.md)

---

This guide walks you through building your first XIME application.

---

## Requirements

- Python 3.11+
- Basic async/await knowledge
- FastAPI familiarity helps but is not required

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

## The short path: `xime init`

The framework ships a project generator. Three commands and you have a running app:

```bash
xime init my-service
cd my-service
python main.py
```

It produces exactly the layout this guide teaches, plus a `/ping` route for you to delete.
The rest of this guide builds every file by hand on **that same layout**, so you can see what
each piece does.

---

## Project Structure

A minimal XIME application needs just one file:

```text
my-service/
└── main.py
```

Add `config/` for DI configuration:

```text
my-service/
├── main.py
└── config/
    ├── __init__.py
    └── dependency.py
```

Recommended full structure for a microservice:

```text
my-service/
├── main.py                     <- entry point, at the ROOT
├── config/                     <- architecture configuration, at the ROOT
│   ├── __init__.py             <- everything that must run at import time
│   ├── dependency.py           <- DI: scan + bind
│   └── web.py                  <- routing, middleware, CORS
├── my_service/                 <- business code, package named after the project
│   ├── __init__.py
│   ├── api/
│   │   └── user_controller.py
│   ├── application/
│   │   ├── usecase/
│   │   │   └── get_user_use_case.py
│   │   └── port/
│   │       └── outbound/
│   │           └── user_repository.py   <- Protocol (interface)
│   ├── infrastructure/
│   │   └── persistence/
│   │       └── repository/
│   │           └── jpa_user_repository.py
│   └── domain/
│       └── user.py
├── resources/                  <- operational configuration, at the ROOT
│   └── application.yml
└── test/
```

⚠ **`main.py`, `config/` and `resources/` live at the PROJECT ROOT, not inside the business
package.** The framework looks for `resources/application.yml` **relative to the directory you
run the command from**, and that command is `python main.py` from the root. Put it inside the
package and the file is **ignored silently**: the app still starts, runs on framework
defaults, and nothing warns you.

⚠ **The business package name (`my_service`) is yours, the framework does not mandate one.**
But it must match the paths you write in `dependency.scan()` and `configure_controllers()`.
`xime init` takes the project name and turns `-` into `_`.

---

## Step 1 - Define the Domain

```python
# my_service/domain/user.py
from dataclasses import dataclass


@dataclass
class User:
    id: int
    name: str
    email: str
```

---

## Step 2 - Define the Interface (Protocol)

```python
# my_service/application/port/outbound/user_repository.py
from typing import Protocol

from my_service.domain.user import User


class UserRepository(Protocol):
    async def find_by_id(self, user_id: int) -> User | None: ...
```

---

## Step 3 - Write the Use Case

```python
# my_service/application/usecase/get_user_use_case.py
from my_service.application.port.outbound.user_repository import UserRepository
from my_service.domain.user import User


class GetUserUseCase:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def execute(self, user_id: int) -> User | None:
        return await self.repository.find_by_id(user_id)
```

Dependencies are declared with **constructor type hints**. No annotations, no decorators.

---

## Step 4 - Write the Implementation

```python
# my_service/infrastructure/persistence/repository/jpa_user_repository.py
from my_service.domain.user import User


class JpaUserRepository:
    async def find_by_id(self, user_id: int) -> User | None:
        return User(id=user_id, name="Alice", email="alice@example.com")
```

No need to inherit from `UserRepository`. `Protocol` uses structural typing, and the mapping
is declared explicitly in step 6.

---

## Step 5 - Write the Controller

```python
# my_service/api/user_controller.py
from pydantic import BaseModel
from xime.adapters.web import get

from my_service.application.usecase.get_user_use_case import GetUserUseCase


class UserResponse(BaseModel):
    id: int
    name: str
    email: str


class UserController:
    def __init__(self, get_user: GetUserUseCase):
        self.get_user = get_user

    @get("/users/{user_id}")
    async def get_user_by_id(self, user_id: int) -> UserResponse:
        user = await self.get_user.execute(user_id)
        return UserResponse(id=user.id, name=user.name, email=user.email)
```

The controller is a singleton in the DI container too, so it receives the use case through its
constructor like any other class.

---

## Step 6 - Configure DI

```python
# config/dependency.py
from xime.core.config import BindingConfig

from my_service.application.port.outbound.user_repository import UserRepository
from my_service.infrastructure.persistence.repository.jpa_user_repository import JpaUserRepository

dependency = BindingConfig()

# Scan by LAYER, not the whole tree: a class joins the container because of where it lives.
dependency.scan(
    "my_service.api",
    "my_service.application.usecase",
    "my_service.infrastructure.persistence.repository",
)

# Interface (Protocol) -> implementation, declared explicitly.
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

The scanner skips any module whose path contains `domain`, `dto`, `entity`, `vo`, `constant`
or `exception`, so `my_service/domain/` needs no declaration. It also skips `Protocol`,
abstract classes and Pydantic `BaseModel`. That default is **overridable** with
`dependency.exclude_segments(...)`; see [Core Concepts](core-concepts.md) section 2.

---

## Step 7 - Configure Routing

```python
# config/web.py
from xime.adapters.web import configure_controllers

configure_controllers("my_service.api")
```

The same string appears in two places, and that is deliberate: `dependency.scan()` **builds
the instances**, while `configure_controllers()` says **which packages hold controllers** so
routes can be registered from those instances. Add a file under `my_service/api/` and it is
picked up without touching either line.

---

## Step 8 - The `config` package

```python
# config/__init__.py
from config.dependency import dependency

from config import web  # noqa: F401  - imported so configure_* runs at startup

__all__ = ["dependency"]
```

⭐ **This file is not cosmetic.** It is where you **explicitly declare everything that must run
at import time**, and the order you write is the order it runs. `configure_controllers`,
`configure_cors`, `configure_jwt`, `configure_grpc_tls` and friends only take effect when the
module containing them is imported, so they have to appear here.

⚠ **Do not rely on the auto-discovery of older releases.** It located the config package
through `__main__.__spec__.parent`, and that value is **different in a child process**: the
framework looked in the wrong place and then **silently** fell back to an empty DI container -
the child started fine, with no routes, and nothing warned you. Declaring it with
`add_config()` in step 10 is the correct path for one process and for many.

---

## Step 9 - Runtime Configuration

```yaml
# resources/application.yml
server:
  host: 127.0.0.1
  port: 8080

# Optional - XIME configures logging at INFO by default; adjust or disable here.
logging:
  level: INFO
```

To see **every key** the framework understands, with comments and defaults:

```bash
xime config --print
```

Logging is set up automatically at startup, so your app prints `INFO` logs out of the box. See
[Configuration → Logging](configuration.md) for the full block and the opt-out rule.

---

## Step 10 - Entry Point

```python
# main.py
from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

import config

app = Application()
app.add_config(config)
app.use(WebAdapter())

if __name__ == "__main__":
    app.run()
```

⭐ **The three middle lines live at MODULE LEVEL, not inside `if __name__`.** The day you run
several processes, each child **re-runs this very file** to rebuild the application, and there
`__name__` is `__mp_main__` so the `if` block never fires. Put `use()` inside that block and
the children come up with no adapters and an empty DI container.

⚠ In exchange, **module level is for DECLARING, not for DOING**: everything outside
`if __name__` runs `N+1` times for `N` child processes. Do not open connections, read files or
call `uuid4()` here. Check with `xime check module-level`. Details:
[Multi-process](multi-process.md).

---

## Step 11 - Run the application

```bash
python main.py
```

Try it:

```bash
curl http://localhost:8080/users/1
# {"id":1,"name":"Alice","email":"alice@example.com"}
```

Open `http://localhost:8080/docs` for the auto-generated Swagger UI.

---

## What just happened?

When `Application` starts:

1. It reads the `config` package you passed to `add_config()` and takes the `dependency` object
2. It imports `config/web.py` (because `config/__init__.py` imports it), running `configure_controllers`
3. It scans `my_service.api`, `my_service.application.usecase`, `my_service.infrastructure.persistence.repository`
4. It finds `UserController`, `GetUserUseCase`, `JpaUserRepository`
5. It resolves: `UserController → GetUserUseCase → UserRepository`
6. It checks the binding: `UserRepository → JpaUserRepository` ✓
7. It creates singletons in dependency order
8. `WebAdapter` registers `UserController`'s methods as FastAPI routes

All of this happens before the first request. If anything is wrong, you get a clear error at
startup.

---

## Startup error examples

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

Click the link below to continue.

---

**1/9 - Getting Started** · [Core Concepts →](core-concepts.md)
