# Native gRPC TLS handshake logging

This opt-in feature creates Python LogRecords for inbound TLS handshake failures,
before an RPC exists. File output uses the [logging file sink](logging.md).
It uses the official grpcio wheel, without a native patch or proxy.

The parser accepts grpcio 1.72.1's `handshake_manager ...: error=` prefix and
the newer `CallNextHandshakerLocked: error=` prefix. Endpoint fields come only
from the metadata tail of the same record, never from reason text or a previous
record. Successful traces do not count as parse loss. The grpcio/grpcio-tools
dependency floor remains 1.72.1. Legacy pointers may use a `0x` prefix on Linux
or fixed-width 8/16-digit hexadecimal without `0x` on Windows.

Use matching development framework and app sources. The updated mains require
this API; the previously published wheel does not contain it yet.

```yaml
grpc:
  handshake_logging:
    enabled: false
    level: WARNING
    rate_limit_per_second: 20
    queue_capacity: 1024
    max_record_bytes: 65536
logging:
  console: {enabled: true, level: INFO}
  file:
    enabled: false
    level: DEBUG
    path: runtime/logs/application.jsonl
```

Enable the two switches independently: native on/file off creates Python events;
file on/native off captures ordinary Python logs. The native settings belong at
top-level `grpc.handshake_logging`, shared by all listeners in that process.
Only TLS listeners are registered for these events.

## Prepare before importing grpc

In each process's main module, before importing grpc, the adapter or app config:

```python
from xime.observability import prepare_grpc_handshake_logging

prepare_grpc_handshake_logging()  # reads effective resources/application.yml

from xime import Application  # noqa: E402
from xime.adapters.grpc import GrpcAdapter  # noqa: E402
import app.config as config  # noqa: E402

app = Application().add_config(config).use(GrpcAdapter())
if __name__ == "__main__":
    app.run_configured()
```

Keep the preparation outside the main guard so spawned workers also run it before
grpc imports. A custom resources directory must match Application's directory.
For embedding/tests, pass `runtime=RuntimeConfig(...)` instead. Off does not import
grpc or allocate a pipe, thread or tracer. Enabled setup after grpc imports fails
clearly. App startup also rejects enabled YAML when preparation was omitted.

This is an explicit exception to avoiding work at module level: native logging
must be prepared before native import/initialization. Ordinary app connections
and business initialization still belong in lifecycle hooks.

## Process lifetime, application lifetime

The native stderr pipe and its two daemon threads live until the **OS process
exits**. Application stop/start unregisters listeners, drains events with bounded
waits and closes the Python file sink; the native pipe stays installed. No stderr
restoration is attempted while grpcio remains loaded. Repeating preparation with
the same settings is idempotent. Changing native settings, including enabled,
requires restarting the OS process. Spawn is supported; inherited fork state is
rejected. The file switch may change across Application restarts independently.

The supervisor's file writer stays shared across workers. Each worker captures
its own native events and PID; the supervisor does not reattribute worker traces
to itself. Promotion and worker respawn retain the normal logging ownership.

An exit drain marker is removed internally, never forwarded as app output. Reader
and dispatcher drains each wait up to 2 seconds. Pipe/FD cleanup belongs to the OS
at process exit, allowing late native destructors to keep logging. Forced exit,
kill, timeout and overload can lose the tail; no durable-delivery promise applies.

## Events and stderr handling

The logger is `xime.grpc.handshake`; the event field is
`grpc_tls_handshake_failed`. JSON files contain the usual timestamp, service, PID,
process and level plus `fields.server_id`, remote/local IP and port, cause,
grpcio_version and address_status. The timestamp is UTC observation time. Missing
addresses/ambiguous listener IDs are null with an explicit status; no previous
peer or thread is used to guess them. Background events have no invented request
ID or authenticated identity. IPv4/IPv6 are normalized.

Only whitelisted causes and fields enter Python logging. Raw buffers, native
pointers, credentials and SNI contents are excluded. A timeout whose native error
only says read failed remains `handshake_read_failed`; the collector does not
invent a more precise cause. SNI is a destination name, not a source IP. Client
outbound failures are excluded from the server event stream.

Xime adds only the handshaker tracer. Existing operator trace flags remain;
conflicting negative flags fail before setup. Traces enabled by Xime are normally
suppressed from console; operator-owned traces remain visible. Other stderr data,
including ordinary gRPC library error messages and unknown continuation lines,
is passed through. `logging.console.enabled` controls Python console records,
not every native library's independent stderr messages.

Xime's Python console and fallback diagnostics bypass the capture pipe. A custom
console is handed over with `Application.use_logging_console(handler)` as in the
file logging guide; stderr handlers are temporarily pointed at the original
destination, preserving their formatter/filter. Stderr handlers left outside
that handover are rejected during native attach. Raw passthrough retains normal
stderr backpressure; a permanently blocked external stderr destination can still
block native writers. Rate/queue bounds apply to normalized event processing.

## Counters and limits

```python
from xime.observability import grpc_handshake_logging_stats

stats = grpc_handshake_logging_stats()
```

Counters are cumulative per process: received, emitted, rate_limited,
queue_dropped, truncated, unparsed, unregistered, inactive, logger_filtered,
passthrough_errors, read_errors and flush_timeouts. Emitted counts LogRecords,
not confirmed disk writes. Off returns zero counters without installing anything.
Loss/parse statistics also produce `grpc_handshake_logging_summary` at most every
5 seconds and when detaching an application. Native records/buffers and the
normalized queue are bounded. Rate limiting does not remove C-core trace
generation cost on new handshakes. Native level is still filtered by Python logger
and sink levels; no application-owned logging setup is silently raised.

The process-lifetime design is tested on Windows and Linux/Python 3.13.5,
including grpcio 1.72.1 and resolver versions. A Windows/Python 3.12 run also
checks the 1.72.1 floor against real connection addresses and on-disk records.
Linux/Python 3.12 and a real VPS deployment still require separate evidence;
static type checking does not replace runtime measurements.
