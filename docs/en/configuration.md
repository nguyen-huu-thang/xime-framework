# Configuration

**English** | [Tiếng Việt](../vn/configuration.md)

[← Core Concepts](core-concepts.md) · **3/9 - Configuration** · [Routing →](routing.md)

---

XIME has a two-layer configuration model designed around two distinct audiences: the developer and the operator.

---

## Layer 1 - Framework Configuration (Developer)

Framework configuration is written in Python. It declares how XIME should behave: which packages to scan, how interfaces map to implementations, which routes to expose.

Location: `app/config/`

```text
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
    "my_service.application.usecase",
    "my_service.application.service",
    "my_service.infrastructure.persistence.repository",
    "my_service.infrastructure.client",
    "my_service.api.rest",
)

# Explicitly bind Protocol interfaces to implementations
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

The scanner skips any module whose path contains `domain`, `dto`, `entity`, `vo`, `constant`
or `exception`. That is a **default, not a law** - redeclare it with
`dependency.exclude_segments(...)`, including calling it empty to exclude nothing. ⚠ Never
calling it and calling it empty are two different things; see
[core-concepts.md](core-concepts.md) section 2.

The `dependency` variable name is the convention XIME looks for. You can also pass a `BindingConfig` directly to `Application`:

```python
app = Application(binding=my_custom_binding)
```

### `config/web.py`

Declares which packages contain controllers:

```python
from xime.adapters.web.routing import configure_controllers

configure_controllers("my_service.api.rest")
```

`configure_controllers()` stores the package in a module-level registry. The `WebAdapter` reads this registry when building the FastAPI app.

### `config/security.py`

Security-related configuration (authentication, authorization rules). Details depend on which security features you use.

---

## Layer 2 - Runtime Configuration (Operator)

Runtime configuration is YAML. It contains environment-specific values: hosts, ports, secrets, database URLs.

Location: `app/resources/`

```text
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
XIME_ENV=prod python -m app.main
# or
APP_ENV=prod python -m app.main
```

XIME checks `XIME_ENV` first, then falls back to `APP_ENV`. Defaults to `dev` if neither is set.

### Logging

Python's root logger defaults to `WARNING` with no handler, so every `INFO` log (including the framework's own startup messages) is swallowed - the app runs correctly but silently, which is easily mistaken for a hang.

To avoid this, XIME configures the root logger at bootstrap, reading an optional `logging:` block from `application.yml`:

```yaml
logging:
  enabled: true        # set false to make the framework leave logging untouched
  level: INFO          # DEBUG / INFO / WARNING / ERROR ... (case-insensitive)
  format: "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
  datefmt: "%H:%M:%S"
```

The whole block is optional - omit it to get the defaults above (enabled, `INFO`).

**Safety rule:** the framework configures logging **only** when `enabled: true` **and** the root logger has no handler yet. If your app calls `logging.basicConfig`/`dictConfig` itself (or runs under a harness that already set up logging, such as pytest), the framework does **not** override it - your setup always wins. To take full control, set `enabled: false`.

### DI options

```yaml
xime:
  di:
    dynamic-binding: false   # default; set true to enable runtime impl switching
```

`xime.di.dynamic-binding` turns on [dynamic interface binding](core-concepts.md#41-dynamic-binding-multiple-implementations): when a `bind` value is a tuple of implementations, enabling this flag makes every impl an eager singleton, injects a transparent proxy into consumers, and lets a `Switcher` repoint the interface app-wide at runtime. Off by default; a tuple binding then behaves exactly like binding its first element alone.

---

## Accessing Runtime Config in Code

Inject `RuntimeConfig` as a dependency:

```python
from xime.core.config import RuntimeConfig

class DatabasePool:
    def __init__(self, config: RuntimeConfig) -> None:
        self._host = config.get("database.host")
        self._port = config.get("database.port", default=5432)
```

Nested keys use dot notation.

---

## Config Discovery - Explicit, Not Magic

XIME **never auto-scans** for config files. Every config source is either:

1. Passed directly to `Application(binding=...)`, or
2. Imported explicitly by a `configure_*()` call

This makes the configuration surface visible and debuggable. If a config is not applied, you can trace exactly where it should have been registered.

```python
# BAD - XIME will not find this
class WebConfig:
    openapi_title = "My Service"

# GOOD - explicitly registered
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

`configure_openapi()` says **where** the documentation lives. Whether it is served
at all is decided by a different switch, below.

---

## `xime.dev` - one switch for everything development-only

```yaml
# resources/application-local.yml
xime:
  dev: true
```

**Off by default; turn it on if you want it.** It decides two things, and both are
easily forgotten on the way to production:

| | `xime.dev` off (default) | on |
|---|---|---|
| `/docs`, `/redoc`, `/openapi.json` | do not exist, 404 | served as usual |
| uvicorn access log (one line per request) | not printed | printed as usual |

An OpenAPI schema is a complete map of the API: every path, every parameter, every
field name, every error code. Served to anyone who can reach the port, it removes
the reconnaissance step almost entirely, which is why it does not belong in
production. FastAPI serves all three by default; **Xime does not, and that
difference is deliberate.**

The start-up log always states which side you are on, so you never have to guess:

```text
web default: API docs off - set xime.dev: true to serve them
web default: API docs EXPOSED at /docs, /redoc, /openapi.json (xime.dev is on)
```

The second line appearing in a production log means the development switch
travelled with the deployment to somewhere it should not have.

> ### Hiding `/docs` behind authentication is NOT the alternative
>
> Swagger UI is a page opened in a **browser**, and a browser attaches no
> `Authorization` header when you type a URL. Leaving `/docs` out of
> `public_paths` returns 401 to the very person who wants to read it. The real
> choice is not *"public or logged-in"* but **on in development, off in
> production** - which is what this switch does.

`xime init` writes `dev: true` into `resources/application.yml`, the file its
generated `.gitignore` already keeps out of git. The `application.yml.example` that
does go into git carries no such line.

Code that needs to know whether it is running in development asks the same place
rather than reading the key by hand - two places deciding one thing drift apart
sooner or later:

```python
from xime.core.config import DEV_KEY, is_dev_mode

if is_dev_mode(config):        # config: RuntimeConfig
    ...
print(DEV_KEY)                 # "xime.dev"
```

Anything that is not a real `RuntimeConfig` makes `is_dev_mode` return `False` -
fail-closed on purpose, because *"I could not read a configuration"* must never come
out as *"development, go ahead and expose things"*. A value that is not a
recognisable boolean **fails at start-up** rather than being guessed at.

⚠ The `docs_url`, `redoc_url` and `openapi_url` fields of `OpenApiConfig` are
**paths**, not switches: they are read only once `xime.dev` has said yes. Setting
`openapi_url=None` turns all three off, because both Swagger UI and ReDoc fetch the
schema from it in the browser.

### The access log, and why it sits behind this switch too

A line reading `INFO: 127.0.0.1:52341 - "GET /api/v1/products" 200 OK` for every
request is the cheapest observability there is while you are developing. It is also
a cost paid on **every single** request, and measured on a development machine it is
not as small as it looks:

| | µs per line | share of one request |
|---|---|---|
| off (a single `if`) | 0.04 | ~0% |
| written to a file, as under `systemd` or `nohup` | 31 | **~14%** |
| written to a colour terminal, when run by hand | 34 | ~15% |

The comparison point is 227 µs for a whole request through `WebAdapter` (4,396 req/s,
measured in 0.8.1). Those numbers belong to **that machine**, that disk, that
operating system - measure again on yours and they will differ, but the order of
magnitude will not.

⚠ **Only the access log goes quiet. Start-up logging is untouched** - the two travel
through different loggers (`uvicorn.access` and `uvicorn.error`), so you still see
which port each adapter opened, whether authentication was installed, and whether
documentation is being served.

⚠ **A missing access log fails silently** - no 404, no error, just an empty screen
that reads very easily as *"the app is not receiving any requests"*. So the start-up
line says so itself:

```text
web default: process main serving on 0.0.0.0:8100 (HTTP) [access log off - set xime.dev: true]
web default: process main serving on 0.0.0.0:8100 (HTTP) [access log on]
```

If you do want an access log in production, put a reverse proxy in front and take it
from there: nginx, Caddy and Traefik all record the same information in C, without
spending any of the Python process's budget on it.

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

[← Core Concepts](core-concepts.md) · **3/9 - Configuration** · [Routing →](routing.md)
