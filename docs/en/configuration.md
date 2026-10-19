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
webserver:
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
webserver:
  port: 443

database:
  host: prod-db.internal
```

The env-specific file is **merged** on top of the base file. Keys not present in the env file keep their base values.

### HTTPS, certificate reload, and management port

```yaml
webserver:
  ssl:
    certfile: /etc/letsencrypt/live/example/fullchain.pem
    keyfile: /etc/letsencrypt/live/example/privkey.pem
    reload:
      mode: both                 # off, watch, api, both
      interval_seconds: 300      # watcher; defaults to 300 seconds
  management:
    enabled: true
    host: 127.0.0.1              # IPv4 or IPv6 loopback only
    port: 9180
```

`webserver.ssl` supplies the default TLS settings for web listeners. Xime reads the cert/key files directly, including Certbot symlinks. If a replacement pair is incomplete or invalid, the active context stays in place and Xime retries; existing TLS connections keep their negotiated version, while new connections use the certificate after a successful load.

**Cipher compatibility:** with Uvicorn 0.47.0, a Windows/Python 3.14.8/OpenSSL 3.5.9 measurement found that the default `TLSv1` string could not handshake with Python's default client when TLS 1.2 was forced; TLS 1.3 still worked. Uvicorn 0.48.0 changed to OpenSSL's default cipher list and passed that TLS 1.2 measurement. If you use Uvicorn 0.47.0 and need TLS 1.2, set a server-side `ciphers` value (for example, `ECDHE+AESGCM`) or upgrade Uvicorn, then test with your application's clients.

`mode: watch` checks files in **every worker serving TLS**. `api` disables the watcher and enables immediate reload requests; `both` enables both; `off` neither watches nor exposes the HTTP reload endpoint. The 300-second default is only the fallback polling interval. It does not delay the Python function or HTTP API. Application code can always call:

```python
from xime.adapters.web import reload_tls

result = await reload_tls(app, server_id="default")
```

The function does not need a management port and works with `mode: off`. Each worker reads its local files. If the watcher, API, or function reports the same file pair, a per-worker lock and in-memory version marker ensure that worker loads it only once. Certificate/private-key data never travels over `ProcessLink`.

When `management` is enabled, Xime adds a plain-HTTP web listener bound only to loopback. Under `processes:`, this internal listener is a singleton: the current primary owns the port, and a promoted primary binds the same port after takeover. The application's `process`/`processes` YAML does not change. Management always serves detailed `/healthz` and `/readyz`; `/tls/reload` is added only when the mode is `api` or `both`, and accepts `{"server_id":"default"}`.

A Certbot deploy hook can request an immediate reload after a successful renewal:

```bash
curl --fail-with-body -X POST http://127.0.0.1:9180/tls/reload \
  -H 'Content-Type: application/json' \
  -d '{"server_id":"default"}'
```

The response reports each worker; errors or missing workers give the hook a failing status. This version binds management to loopback but does not add API authentication yet. Management does not inherit the public certificate and does not serve business controllers or Swagger.

`management.enabled` defaults to `false`. When enabled, `port` is required and `host` must be a loopback IP; API reload requires management to be enabled. Do not declare both `webserver:` and `server:`. The old `server:` block remains as a compatibility alias; `environments.server` remains the independent environment branch name.

Public `/healthz` and `/readyz` still require `configure_health()`. Their bodies only contain `{"status":"ok"}` or `{"status":"unavailable"}`; detailed health is on the loopback management port when enabled.

### Active Environment

Set the environment with an env var before starting:

```bash
XIME_ENV=prod python -m app.main
# or
APP_ENV=prod python -m app.main
```

XIME checks `XIME_ENV` first, then falls back to `APP_ENV`. If neither is set, only `application.yml` is loaded. This profile-based behavior remains supported for existing applications.

### Select local/server from one file

An application that carries both environments in one `application.yml` may declare `xime.dev` and two `environments` branches:

```yaml
xime:
  dev: true # true = local; false = server/VPS

webserver:
  port: 8178

environments:
  local:
    webserver:
      host: 0.0.0.0
    database:
      url: postgresql+asyncpg://localhost/my_app
  server:
    webserver:
      host: 127.0.0.1
      ssl:
        certfile: /etc/letsencrypt/live/example/fullchain.pem
        keyfile: /etc/letsencrypt/live/example/privkey.pem
    database:
      url: postgresql+asyncpg://db.internal/my_app
```

The loader deeply merges the selected branch into common keys and removes `environments` from the runtime configuration. Mappings merge deeply; a list in the selected branch replaces the common list. Both branches must exist and be mappings. `xime.dev` must be explicitly set to a boolean and cannot be repeated in a branch. This mode cannot be combined with `XIME_ENV`/`APP_ENV`; conflicting selectors stop startup. `xime check config` checks known framework key names in both branches and validates effective logging settings. Overlay checks do not replace inspecting the effective TLS configuration and verifying it with an HTTPS handshake. Applications without `environments` retain the existing behavior.

An environment branch that declares `process:` or `processes:` replaces the common topology as a group; a branch without either key inherits the common topology. This lets local inherit the existing `processes:` while a low-memory server declares only `process:`. Use `app.run_configured()` so Xime enables the supervisor only when the effective config declares `processes:`. The effective config cannot declare both `process:` and `processes:`.

### Logging

Xime supports independent console and rotating file handlers. File logging is
opt-in and defaults to off. Existing console-only configuration stays compatible.
See [logging.md](logging.md) for YAML, custom console handover, multi-process
ownership, redaction, queue limits and shutdown behavior.

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
# resources/application.yml
xime:
  dev: true
environments:
  local: { ... }
  server: { ... }
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

## Checker coverage and dependency floors (Unreleased)

`xime check config` checks framework keys in common configuration and both
`environments.local/server`, including the inactive branch. Required fields and
server/webserver conflicts are checked after merging common values, so a partial
overlay may inherit required settings. IDs under `process.web.<id>` or
`processes.<process_id>.web.<id>` are dynamic; SSL keys within those endpoints
are checked. Application-owned blocks remain outside the framework schema.
Intentional HTTP and empty SSL blocks remain supported. Findings show key
paths rather than credential values; unreadable files are inconclusive.

Development dependency floors are PyJWT 2.15.0 for jwt, AnyIO 4.14.2 at runtime,
and Uvicorn 0.48.0 for web. Updating source metadata does not upgrade an existing
environment; update dependencies through the application's deployment workflow.
Explicit cipher configuration still wins.

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
