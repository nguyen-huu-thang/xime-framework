# Console and rotating file logging

Xime uses Python `logging`; no extra dependency is required. Configure it in the
effective `application.yml` and restart the application to apply changes.

```yaml
logging:
  enabled: true
  level: INFO
  service_name: example
  console:
    enabled: true
    level: INFO
  file:
    enabled: false  # change to true to create the file writer
    level: DEBUG
    path: runtime/logs/application.jsonl
    format: json
    max_bytes: 10485760
    backup_count: 5
    queue_capacity: 4096
    max_record_bytes: 65536
    shutdown_timeout: 5
```

With file enabled, DEBUG reaches only the file while INFO and above reach both
sinks. Each sink inherits `logging.level` when its level is omitted. Existing
`logging.format` and `logging.datefmt` continue to control the default console.
Named loggers with explicit levels or `propagate=False` retain their Python
logging behavior; Xime cannot recover records they filter out before root.

`logging.enabled: false` leaves application logging untouched. Combining it with
`file.enabled: true` is invalid. File logging defaults to off and then allocates
no file, directory, lock, queue or writer thread. Console can be disabled while
file stays enabled. With both sinks off, a NullHandler prevents lastResort output.

## File ownership and retention

Paths resolve relative to the Python process's working directory. Each application
has one append-mode RotatingFileHandler, never one handler per worker. A cluster's
supervisor creates the queue using Xime's spawn context and owns the writer;
promotion and worker respawn retain that writer. Single-process applications use
a bounded in-process queue and QueueListener. No file I/O runs in a request task.

A persistent `<path>.lock` sidecar holds an OS lock. Another independent Xime
instance targeting that canonical path fails startup. Give independent services
separate paths. Do not remove the sidecar while a writer is running. The lock is
released at normal stop or process exit; the sidecar itself may remain.

Files append across restarts. Rotation keeps the active file plus `.1` through
`.backup_count`, deleting only that configured family as it rotates. The size
threshold is approximate: UTF-8/newline handling and one oversized record can
exceed `max_bytes` by up to one bounded record plus its newline. No age-based
retention or external logrotate coordination is provided. Use one rotation owner.

`backup_count` accepts 1–100, queue capacity 1–100000, record limit 1024–1048576
bytes and shutdown timeout greater than 0 up to 30 seconds; max_bytes must be
positive. JSON is one valid object per line. Text also escapes embedded newlines.

## Context, safety and failure handling

File records include UTC ISO-8601 `timestamp`, `service`, `pid`, `process`,
`logger`, `level`, `message`, and `exception` when available. `service_name` is
independent of any identity system; when omitted Xime uses the main module's
package or `application` for a direct script. Request/correlation IDs come from
the producer's `request_context` or explicit record fields, before queueing.
Other `extra` fields are sanitized into `fields`. Background jobs need no fake ID.

Sensitive field names, common credential assignments, Bearer/Basic credentials,
JWT-shaped strings, URL passwords and private-key PEM blocks are masked in file
records. Extras have depth/count limits; oversized records omit extras and shorten
message/exception with `truncated: true`. This is defense in depth: arbitrary
secrets embedded in prose cannot all be recognized. Console formatting/redaction
remains with its existing formatter. Avoid logging secrets at the call site.

Queueing is nonblocking. Full queues drop records, increment a per-producer count
and emit a rate-limited diagnostic directly to stderr. Runtime write/rotation
errors use the same independent fallback and do not echo the failed payload.
Startup path/lock errors fail fast without printing the configured path value.
Diagnostics bypass logging to prevent recursion; multiprocessing's internal
debug logger is excluded from the file queue for the same reason.

Shutdown removes producers and drains with bounded waits: up to one
`shutdown_timeout` for the listener and another for its multiprocessing feeder.
A stalled writer retains its lock until its thread exits. Queues are not durable:
overload, timeout or forced termination may lose the tail. Killing a worker while
it writes a multiprocessing queue can also corrupt the queue; this is a Python
IPC limitation, not a delivery guarantee. `Application.run()` owns shutdown
signals for the entire worker: SIGINT/SIGTERM stop all adapters and PreDestroy
hooks before closing logging, rather than only stopping the web server. Repeated
signals do not cancel cleanup again; the supervisor retains its timeout/kill
fallback. Embedded `start()`/`stop()` does not take over the host's handlers.
POSIX is checked separately; Windows `terminate()` is forced termination and
does not provide the same cleanup guarantee.

## An application with a custom console

Without handover, Xime preserves existing root handlers when file is off. Enabling
file in that state fails with guidance instead of silently changing ownership.
Register the one console handler before startup:

```python
import logging
from xime import Application

console = logging.StreamHandler()
console.setFormatter(MyJsonFormatter())
app = Application().use_logging_console(console)
# register adapters, then app.run() / app.run_configured()
```

An already installed handler can be handed over too. Xime retains its formatter
and filters, applies explicit YAML levels/switches, and restores its original
level/membership at stop. When no YAML console/root level is explicitly supplied,
the custom console retains its prior effective level. Other root handlers cause
a clear ownership error. Do not call dictConfig again after bootstrap.

This file sink receives Python LogRecords. Native gRPC C-core TLS handshake
diagnostics use the separate opt-in [native collector](grpc-handshake-logging.md);
enabling file logging alone does not capture their source IPs.

References: [Python logging cookbook](https://docs.python.org/3.14/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes),
[QueueHandler/QueueListener](https://docs.python.org/3.14/library/logging.handlers.html#queuehandler),
[multiprocessing queue restrictions](https://docs.python.org/3.14/library/multiprocessing.html#pipes-and-queues).
