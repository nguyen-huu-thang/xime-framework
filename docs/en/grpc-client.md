# gRPC Client SDK + Dynamic mTLS

**English** | [Tiếng Việt](../vn/grpc-client.md)

[← Code-First gRPC](grpc-codefirst.md) · **Companion — gRPC Client SDK** · [Starters →](starters.md)

---

[Code-First gRPC](grpc-codefirst.md) covers the **server**: you write Python
controllers and XIME serves them over gRPC. This page covers the **client**:
calling another service as if it were a local function - no hand-built channels,
no protobuf marshalling, no bare `grpc.RpcError` handling.

```text
target service (.proto + contract.json)
        │  xime grpc client
        ▼
clients/<service>/   ← self-contained Python SDK (Pydantic + client class)
        │  configure_grpc_clients(...) + application.yml
        ▼
inject straight into a constructor — XimeGrpcChannel handles deadline,
typed errors, dynamic mTLS
```

> **Requires:** `pip install "xime[grpc]"`

---

## 1. Generate the SDK from `.proto`

Take the target service's `.proto` files (and its `contract.json` if it is a
Xime service - see section 6), put them in a directory, and run:

```bash
xime grpc client --proto contracts/trust --out clients/trust
```

The result is a self-contained Python package:

```text
clients/trust/
├── __init__.py          # exports client classes + DTOs
├── _models.py           # Pydantic models + IntEnums mirrored from messages
├── _clients.py          # one client class per service, one method per rpc
└── _descriptors.binpb   # FileDescriptorSet, loaded at runtime
```

The key idea: **code in `app/` imports this package like a library** - it is not
code you edit, it is a generated artifact. The SDK does not use `*_pb2.py`;
message classes are built in a private `DescriptorPool` from
`_descriptors.binpb`, so two SDKs in one process never collide on module names.

A client class mirrors the server controller:

```python
# clients/trust/_clients.py — generated, do not edit
class KeyClient:
    def __init__(self, channel: grpc.aio.Channel) -> None: ...

    async def get_verification_keys(self, request: KeyQuery) -> KeyList: ...
```

---

## 2. Wire the client into DI

Following XIME's `configure_*` pattern. Declare it in `config/grpc.py`:

```python
# config/grpc.py
from xime.adapters.grpc import configure_grpc_clients
from clients.trust import KeyClient, CertClient

configure_grpc_clients("trust", KeyClient, CertClient)
#                       ^^^^^ client_id, matches grpc.clients.trust in YAML
```

And configure the address + security in `application.yml`:

```yaml
grpc:
  clients:
    trust:
      host: trust.internal
      port: 9090
      deadline_ms: 3000      # default per-call deadline; 0 disables
```

At startup the framework creates one `XimeGrpcChannel` per `client_id`,
instantiates each client class with it, and **registers the instances in the DI
container**. From there any class just declares a constructor parameter:

```python
class VerificationKeySynchronizer:
    def __init__(self, keys: KeyClient, cache: VerificationKeyCache):
        self._keys = keys
        self._cache = cache

    async def synchronize(self) -> None:
        result = await self._keys.get_verification_keys(KeyQuery(active_only=True))
        self._cache.update(result.keys)
```

Clients sharing a `client_id` share one channel. Channels are closed gracefully
on application shutdown.

> **Fail fast:** registering `configure_grpc_clients("trust", ...)` without a
> `grpc.clients.trust` block in YAML fails startup with a message that includes
> the YAML you need to add.

---

## 3. Deadlines and typed errors

`XimeGrpcChannel` adds two things at every call boundary - the generated SDK
never needs to know:

**Deadline.** Every call gets a default deadline (`deadline_ms` in YAML).
Override per call with `timeout=` (seconds). `deadline_ms: 0` disables it.

**Typed errors.** gRPC signals failures with `AioRpcError` carrying a status
code. XIME translates them into a dedicated exception hierarchy so you branch on
meaning, not on raw status codes:

| gRPC StatusCode | XIME exception |
|---|---|
| `DEADLINE_EXCEEDED` | `RemoteCallTimeout` |
| `UNAVAILABLE` | `RemoteServiceUnavailable` |
| anything else | `RemoteCallError` |

```python
from xime.core.exception.framework import (
    RemoteCallError, RemoteCallTimeout, RemoteServiceUnavailable,
)

try:
    keys = await self._keys.get_verification_keys(query)
except RemoteCallTimeout:
    ...                       # exceeded the deadline
except RemoteServiceUnavailable:
    ...                       # could not connect
except RemoteCallError as exc:
    if exc.code == "KeyNotFoundException":   # server-side exception name
        ...
```

`RemoteCallError` carries:

- `status` — the gRPC StatusCode name (`"NOT_FOUND"`, `"INTERNAL"`...).
- `code` — the server-side exception class name, read from the `xime-error`
  trailing metadata set by the server's `ErrorMappingInterceptor`. Empty for
  non-XIME targets (still typed).
- `path` — the failed method (`/xime.internal.KeyController/GetKeys`).
- `error_message` — the message from the server.

> This is the mirror of `configure_grpc_error_mappings` on the server: the
> server maps exception → StatusCode, the client maps StatusCode → exception
> back.

**Retry (optional).** Enable automatic retry for **unary** calls via YAML. Off
by default - opt in explicitly, in keeping with the "no magic" philosophy:

```yaml
grpc:
  clients:
    trust:
      retry:
        enabled: true
        max_attempts: 3            # total tries incl. the first
        initial_backoff_ms: 100
        max_backoff_ms: 2000
        backoff_multiplier: 2.0
        retryable_status: [UNAVAILABLE]   # gRPC StatusCode names
```

- Only **unary** calls are retried - a streaming request/response cannot be
  replayed safely once consumed.
- Only `UNAVAILABLE` by default (the request usually never reached the server,
  so retrying is safe). Adding other statuses for non-idempotent calls risks
  duplicate side effects - opt in deliberately.
- Each attempt gets its own **deadline** (`deadline_ms`); exponential backoff
  capped at `max_backoff_ms`. After the last attempt it raises the typed error
  as usual.

---

## 4. Dynamic mTLS (rotation without downtime)

To call over mTLS with auto-rotating certificates, reuse the same
`GrpcCertificateProvider` registered for the server (the certificate identifies
the service, so inbound and outbound share one source - see
[Code-First gRPC](grpc-codefirst.md), dynamic TLS section). Just turn on
`dynamic`:

```yaml
grpc:
  clients:
    trust:
      host: trust.internal
      port: 9090
      tls:
        enabled: true
        dynamic: true        # cert from the provider, no files declared
```

```python
# config/grpc.py — one provider for both server and client
configure_grpc_tls(provider=TrustGrpcCertificateProvider)
configure_grpc_clients("trust", KeyClient)
```

How it works: on each call, `XimeGrpcChannel` compares `provider.version()` with
the current channel's version. Different (the cert rotated) → it builds a new
channel with the new cert; the old channel closes gracefully so in-flight calls
finish - **no cut sessions, no restart**. Same → it reuses the channel (just a
string compare, zero cost).

This is the outbound counterpart to the server's dynamic certificate. Your cert
rotation machinery just updates the resolver as usual; both directions pick up
the new cert on the next handshake.

**Multi-server.** By default the client uses the provider registered under
`server_id="default"`. If the service has multiple providers keyed by
`server_id` (e.g. internal vs public) and this client needs a different
identity, set `tls.server_id`:

```yaml
grpc:
  clients:
    public-api:
      tls:
        enabled: true
        dynamic: true
        server_id: public     # use configure_grpc_tls(..., server_id="public")
```

`get_provider()` still falls back to `"default"` when that `server_id` has no
dedicated registration.

**Static mode** (`dynamic: false` or omitted) reads certs from files:

```yaml
grpc:
  clients:
    trust:
      tls:
        enabled: true
        ca_file:   certs/ca.pem      # verify the server
        cert_file: certs/client.crt  # mTLS: present own cert
        key_file:  certs/client.key
```

Declaring no files → use the system CA roots (plain TLS to a public endpoint).

---

## 5. Streaming

The client class reflects the endpoint's stream kind:

```python
# upload (client streaming): pass the request + an async iterator of byte chunks
async def push_doc(self, request: PushMeta, chunks: AsyncIterator[bytes]) -> PushDone: ...

# download (server streaming): returns an async iterator of byte chunks
def pull_doc(self, request: PullQuery) -> AsyncIterator[bytes]: ...
```

```python
async def chunks():
    yield b"part-1"
    yield b"part-2"

done = await client.push_doc(PushMeta(name="document"), chunks())

async for chunk in client.pull_doc(PullQuery(parts=3)):
    process(chunk)
```

The chunk-wrapper convention (metadata first, chunks after) is fully handled by
the framework - business code never sees the wrapper message.

---

## 6. Xime services vs foreign services (Java...)

The generator also reads a `contract.json` sidecar if present - that file is
emitted next to the `.proto` by a Xime service's `xime grpc generate`, recording
what proto flattens away:

- **Sidecar present** (target is Xime): the SDK mirrors 1:1 - original method
  names, `Decimal`/`UUID`/`date` types exactly as in the source DTOs, both unary
  and streaming.
- **No sidecar** (target written in Java, only `.proto`): the generator falls
  back to proto-only - unary methods only, types follow plain proto mapping
  (`Decimal` becomes `str`...). Streaming methods are skipped with a warning.

To call a Java service, just copy its `.proto` into `contracts/` and run
`xime grpc client` as usual.

---

## 7. Packaging the SDK (optional)

By default `--out` is the importable package, committed into the consumer repo.
When a service has many consumers, emit a pip-installable layout for the producer
to distribute:

```bash
xime grpc client --proto contracts/trust --out sdk/python \
    --package trust-client --package-version 1.0.0
```

```text
sdk/python/
├── pyproject.toml        # name, version, depends on xime[grpc]
└── trust_client/         # package name, '-' becomes '_'
    └── ...
```

Consumers install via a local path (`pip install -e ./sdk/python`) or a git URL
(`pip install "trust-client @ git+<repo>@<tag>#subdirectory=sdk/python"`) - no
private PyPI required. Versions are managed with git tags.

---

## 8. Quick reference

| Task | API |
|---|---|
| Generate SDK | `xime grpc client --proto <dir> --out <dir>` |
| Generate as package | add `--package <name> [--package-version <v>]` |
| Wire into DI | `configure_grpc_clients("<id>", ClientA, ClientB)` |
| Address + deadline | `grpc.clients.<id>.{host,port,deadline_ms}` (YAML) |
| Dynamic mTLS | `tls.dynamic: true` + `configure_grpc_tls(provider=...)` |
| Static mTLS | `tls.{ca_file,cert_file,key_file}` (YAML) |
| Override one deadline | `await client.method(req, timeout=<seconds>)` |
| Catch errors | `RemoteCallError` / `RemoteCallTimeout` / `RemoteServiceUnavailable` |

---

[← Code-First gRPC](grpc-codefirst.md) · **Companion — gRPC Client SDK** · [Starters →](starters.md)
