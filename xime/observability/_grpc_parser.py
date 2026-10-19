"""Bounded native framing. Peer/cause always come from one handshaker record."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote

_PREFIX = re.compile(rb"^[IWEF]\d{4} \d{2}:\d{2}:\d+\.\d+\s+\d+ (?P<source>[^]\r\n]+)\] ")
_END = re.compile(rb"read_buffer\.Length\(\)=\d+, exit_early=\d+}\s*$")
# Legacy Windows builds print pointers as fixed-width hex without a 0x prefix.
_STATUS_HEAD = re.compile(
    rb"(?:CallNextHandshakerLocked:|handshake_manager (?:0x[0-9a-fA-F]+|[0-9a-fA-F]{16}|[0-9a-fA-F]{8}):) error="
)
_TAIL_HEAD = re.compile(r"\A(?:true|false|0|1) index=\d+, args=\{endpoint=[^,\r\n]+, args=\{")
_TAIL_END = re.compile(r"\A\d+, exit_early=\d+\}\s*\Z")
_CAUSES = (
    "PEER_DID_NOT_RETURN_A_CERTIFICATE",
    "HTTP_REQUEST",
    "HTTPS_PROXY_REQUEST",
    "WRONG_VERSION_NUMBER",
    "UNSUPPORTED_PROTOCOL",
    "NO_SHARED_CIPHER",
    "NO_COMMON_SIGNATURE_ALGORITHMS",
    "CERTIFICATE_VERIFY_FAILED",
    "BAD_PACKET_LENGTH",
    "TLSV1_ALERT_UNKNOWN_CA",
    "SSLV3_ALERT_CERTIFICATE_UNKNOWN",
)


def canonical_ip(host: str) -> str:
    parsed = ipaddress.ip_address(host)
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
        parsed = parsed.ipv4_mapped
    return str(parsed)


def address(value: str) -> tuple[str, int] | None:
    family, _, rest = unquote(value).partition(":")
    if family not in ("ipv4", "ipv6"):
        return None
    host, _, port = rest.rpartition(":")
    try:
        parsed = canonical_ip(host.strip("[]"))
        number = int(port)
        return (parsed, number) if 0 < number <= 65535 else None
    except ValueError:
        return None


@dataclass(frozen=True)
class NativeFailure:
    remote: tuple[str, int] | None
    local: tuple[str, int] | None
    cause: str


def handshaker_payload(record: bytes) -> bytes | None:
    """Accept both official trace prefixes without trusting free-form reason text.

    Nhận hai tiền tố trace chính thức, không dùng reason tự do làm metadata.
    """
    prefix = _PREFIX.match(record)
    if prefix is None or b"handshaker.cc:" not in prefix["source"]:
        return None
    status = _STATUS_HEAD.match(record, prefix.end())
    return record[status.end() :] if status is not None else None


def parse_failure(record: bytes) -> NativeFailure | None:
    payload = handshaker_payload(record)
    if payload is None:
        return None
    body = payload.decode("utf-8", errors="replace")
    # Parse the metadata tail separately; reason text is untrusted and must not
    # override endpoint fields. Partitioning also avoids unbounded regex backtracking.
    status, separator, tail = body.rpartition(" shutdown=")
    head = _TAIL_HEAD.match(tail)
    if not separator or head is None:
        return None
    arguments, separator, footer = tail[head.end() :].rpartition("}, read_buffer.Length()=")
    if not separator or _TAIL_END.fullmatch(footer) is None:
        return None
    if "grpc.internal.server_credentials=" not in arguments:
        return None
    if status.startswith("OK ") or status == "OK":
        return None

    def endpoint(key: str) -> tuple[str, int] | None:
        match = re.search(r"grpc\.internal\.endpoint_" + key + r"_address=([^,}\s]+)", arguments)
        return address(match[1]) if match else None

    cause = next((code.lower() for code in _CAUSES if code in status), None)
    if cause is None:
        if "Handshake timed out" in status:
            cause = "timeout"
        elif "End of TCP stream" in status or "Socket closed" in status:
            cause = "peer_closed"
        elif "Handshake read failed" in status:
            cause = "handshake_read_failed"
        elif "Ssl handshake failed" in status:
            cause = "tls_handshake_failed"
        else:
            cause = "handshake_failed"
    return NativeFailure(endpoint("peer"), endpoint("local"), cause)


class NativeFramer:
    def __init__(
        self,
        *,
        limit: int,
        quiet: bool,
        forward: Callable[[bytes], None],
        record: Callable[[bytes], None],
        count: Callable[[str], None],
        drain_marker: bytes = b"",
        drained: Callable[[], None] | None = None,
    ) -> None:
        self.limit, self.quiet = limit, quiet
        self.forward, self.record, self.count = forward, record, count
        self.pending = bytearray()
        self.forwarded = 0
        self.active = bytearray()
        self.discard_line = False
        self.drain_marker, self.drained = drain_marker, drained
        self._control_tail = b""

    @staticmethod
    def _possible_prefix(data: bytes | bytearray) -> bool:
        return (
            bool(data)
            and data[0] in b"IWEF"
            and all(48 <= c <= 57 for c in data[1:5])
            and (len(data) < 6 or data[5] == 32)
        )

    def feed(self, data: bytes) -> None:
        if self.drain_marker:
            data = self._control_tail + data
            self._control_tail = b""
            while (index := data.find(self.drain_marker)) >= 0:
                self._feed_plain(data[:index])
                self.flush_partial()
                if self.drained is not None:
                    self.drained()
                data = data[index + len(self.drain_marker) :]
            for size in range(min(len(data), len(self.drain_marker) - 1), 0, -1):
                if data.endswith(self.drain_marker[:size]):
                    self._control_tail = data[-size:]
                    data = data[:-size]
                    break
        self._feed_plain(data)

    def _feed_plain(self, data: bytes) -> None:
        for part in data.splitlines(keepends=True):
            if self.discard_line:
                self.forward(part)
                if part.endswith(b"\n"):
                    self.discard_line = False
                continue
            self.pending.extend(part)
            if len(self.pending) > self.limit:
                self.forward(bytes(self.pending[self.forwarded :]))
                self.pending.clear()
                self.forwarded = 0
                self.active.clear()
                self.discard_line = not part.endswith(b"\n")
                self.count("truncated")
                continue
            if part.endswith(b"\n"):
                self._line(bytes(self.pending), self.forwarded)
                self.pending.clear()
                self.forwarded = 0
            elif not self._possible_prefix(self.pending):
                # Ordinary stderr without newline is forwarded immediately.
                self.forward(bytes(self.pending[self.forwarded :]))
                self.forwarded = len(self.pending)

    def _line(self, line: bytes, forwarded: int) -> None:
        prefix = _PREFIX.match(line)
        if prefix is not None:
            if self.active:
                self.count("unparsed")
                self.active.clear()
            source = prefix["source"]
            managed = any(
                name in source
                for name in (
                    b"handshaker.cc:",
                    b"handshaker.h:",
                    b"channel_trace.h:",
                    b"security_handshaker.cc:",
                )
            )
            if not self.quiet or not managed or line[:1] in (b"W", b"E", b"F"):
                self.forward(line[forwarded:])
            body = line[prefix.end() :]
            if b"handshaker.cc:" in source and _STATUS_HEAD.match(body) is not None:
                self.active.extend(line)
            elif b"handshaker.cc:" in source and (
                body.startswith(b"CallNextHandshakerLocked:")
                or (body.startswith(b"handshake_manager ") and b"args={" in body and b"error=" in body)
            ):
                self.count("unparsed")
        else:
            # Never swallow unrecognized lines, including multiline continuations.
            self.forward(line[forwarded:])
            if self.active:
                self.active.extend(line)
            elif b"CallNextHandshakerLocked: error=" in line:
                self.count("unparsed")
        if len(self.active) > self.limit:
            self.active.clear()
            self.count("truncated")
        elif self.active and _END.search(self.active):
            self.record(bytes(self.active))
            self.active.clear()

    def flush_partial(self) -> None:
        if self.pending:
            self.forward(bytes(self.pending[self.forwarded :]))
            self.pending.clear()
            self.forwarded = 0
        if self.active:
            self.active.clear()
            self.count("unparsed")
