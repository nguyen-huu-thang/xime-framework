# Configuration

**English** | [Tiếng Việt](../vn/configuration.md)

[← Core Concepts](core-concepts.md) · **3/9 — Configuration** · [Routing →](routing.md)

---

XIME has a two-layer configuration model designed around two distinct audiences: the developer and the operator.

---

## Layer 1 — Framework Configuration (Developer)

Framework configuration is written in Python. It declares how XIME should behave: which packages to scan, how interfaces map to implementations, which routes to expose.

Location: `app/config/`

```
config/
├── dependency.py   ← DI: scan + bind
├── routing.py      ← controller registration
└── security.py     ← security config
```

### `config/dependency.py`

The central DI config file. XIME auto-discovers it at startup: tries `{main_package}.config.dependency` first (e.g. `app.config.dependency` when running `python -m app.main`), then falls back to `config.dependency`.

```python
from xime import BindingConfig
from application.port.outbound.user_repository import UserRepository
from infrastructure.persistence.repository.jpa_user_repository import JpaUserRepository

dependency = BindingConfig()

# Declare which packages to scan for DI-managed classes
dependency.scan(
    "application.usecase",
    "application.service",
    "infrastructure.persistence.repository",
    "infrastructure.client",
    "api.rest",
)

# Explicitly bind Protocol interfaces to implementations
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

The `dependency` variable name is the convention XIME looks for. You can also pass a `BindingConfig` directly to `Application`:

```python
app = Application(binding=my_custom_binding)
```

### `config/routing.py`

Declares which packages contain controllers:

```python
from xime.adapters.web.routing import configure_controllers

configure_controllers("api.rest")
```

`configure_controllers()` stores the package in a module-level registry. The `WebAdapter` reads this registry when building the FastAPI app.

### `config/security.py`

Security-related configuration (authentication, authorization rules). Details depend on which security features you use.

---

## Layer 2 — Runtime Configuration (Operator)

Runtime configuration is YAML. It contains environment-specific values: hosts, ports, secrets, database URLs.

Location: `app/resources/`

```
resources/
├── application.yml          ← base config (always loaded)
├── application-dev.yml      ← dev overrides (loaded when XIME_ENV=dev)
├── application-prod.yml     ← prod overrides (loaded when XIME_ENV=prod)
└── application-test.yml     ← test overrides (loaded when XIME_ENV=test)
```

### Base Config

```yaml
# resources/application.yml
server:
  host: 0.0.0.0
  port: 8080

database:
  host: localhost
  port: 5432
  name: mydb

redis:
  host: localhost
  port: 6379
```

### Environment Override

```yaml
# resources/application-prod.yml
server:
  port: 443

database:
  host: prod-db.internal
```

The env-specific file is **merged** on top of the base file. Keys not present in the env file keep their base values.

### Active Environment

Set the environment with an env var before starting:

```bash
XIME_ENV=prod python app/main.py
# or
APP_ENV=prod python app/main.py
```

XIME checks `XIME_ENV` first, then falls back to `APP_ENV`. Defaults to `dev` if neither is set.

---

## Accessing Runtime Config in Code

Inject `RuntimeConfig` as a dependency:

```python
from xime.config import RuntimeConfig

class DatabasePool:
    def __init__(self, config: RuntimeConfig) -> None:
        self._host = config.get("database.host")
        self._port = config.get("database.port", default=5432)
```

Nested keys use dot notation.

---

## Config Discovery — Explicit, Not Magic

XIME **never auto-scans** for config files. Every config source is either:

1. Passed directly to `Application(binding=...)`, or
2. Imported explicitly by a `configure_*()` call

This makes the configuration surface visible and debuggable. If a config is not applied, you can trace exactly where it should have been registered.

```python
# BAD — XIME will not find this
class WebConfig:
    openapi_title = "My Service"

# GOOD — explicitly registered
from xime.adapters.web.openapi import configure_openapi, OpenApiConfig

configure_openapi(OpenApiConfig(
    title="My Service",
    version="1.0.0",
))
```

---

## OpenAPI Configuration

```python
# config/openapi.py  (imported from main.py or routing.py)
from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer

configure_openapi(OpenApiConfig(
    title="User Service",
    version="1.0.0",
    description="Manages user accounts",
    security=JwtBearer(),
    public_paths=["/auth/login", "/health"],
))
```

---

## Passing Config to Application

Custom resources directory or config module:

```python
app = Application(
    resources_dir="conf",              # default: "resources"
    config_module="infra.di_config",   # default: None (auto-detected from __main__ package)
)
```


---

[← Core Concepts](core-concepts.md) · **3/9 — Configuration** · [Routing →](routing.md)
