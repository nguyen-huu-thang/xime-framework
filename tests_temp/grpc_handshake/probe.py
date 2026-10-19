"""G4a loopback feasibility probe. No app services, database or external peers.

Run in a fresh subprocess; GRPC_TRACE is read during native initialization.
The probe intentionally exercises native FD 2 independently of sys.stderr.
Experimental redirection is subprocess-only: native stderr restoration currently
fails on the measured Windows wheels. Do not use FdCapture as a runtime collector.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import ssl
import sys
import threading
from datetime import UTC, datetime, timedelta


def certificates():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "probe-ca")])
    now = datetime.now(UTC)
    ca = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    def leaf(common, usage):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common)]))
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=2))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(common)]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        return (
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            cert.public_bytes(serialization.Encoding.PEM),
        )

    return (
        ca.public_bytes(serialization.Encoding.PEM),
        leaf("localhost", ExtendedKeyUsageOID.SERVER_AUTH),
        leaf("client", ExtendedKeyUsageOID.CLIENT_AUTH),
    )


class FdCapture:
    def __init__(self, windows_handle=True):
        self.windows_handle = windows_handle
        self.original = os.dup(2)
        self.read, write = os.pipe()
        self.blocks = []
        self.stored = 0
        self.truncated = False
        os.dup2(write, 2)
        os.close(write)
        if self.windows_handle:
            self.sync_windows_handle()
        self.thread = threading.Thread(target=self.consume, daemon=True)
        self.thread.start()

    def consume(self):
        while data := os.read(self.read, 8192):
            if self.stored + len(data) <= 4 * 1024 * 1024:
                self.blocks.append(data)
                self.stored += len(data)
            else:
                self.truncated = True
            view = memoryview(data)
            while view:
                written = os.write(self.original, view)
                view = view[written:]

    def close(self):
        os.dup2(self.original, 2)
        if self.windows_handle:
            self.sync_windows_handle()
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError("FD 2 capture did not reach EOF")
        os.close(self.read)
        os.close(self.original)
        return b"".join(self.blocks).decode("utf-8", errors="replace")

    @staticmethod
    def sync_windows_handle():
        if os.name == "nt":
            import ctypes
            import msvcrt
            from ctypes import wintypes

            setter = ctypes.WinDLL("kernel32", use_last_error=True).SetStdHandle
            setter.argtypes = (wintypes.DWORD, wintypes.HANDLE)
            setter.restype = wintypes.BOOL
            if not setter(wintypes.DWORD(-12), msvcrt.get_osfhandle(2)):
                raise ctypes.WinError(ctypes.get_last_error())


async def run(args):
    capture = (
        FdCapture(not args.fd_only) if args.capture and args.capture_at == "before-import" else None
    )
    import grpc

    init_channels = []

    if args.capture and args.capture_at == "after-import":
        capture = FdCapture(not args.fd_only)

    if args.timing == "after-import":
        os.environ["GRPC_TRACE"] = "handshaker"
    if args.timing == "after-init":
        init_channels.append(grpc.insecure_channel("localhost:1"))
        os.environ["GRPC_TRACE"] = "handshaker"
    if args.capture and args.capture_at == "after-init":
        init_channels.append(grpc.insecure_channel("localhost:1"))
        capture = FdCapture(not args.fd_only)

    ca, (server_key, server_cert), (client_key, client_cert) = certificates()
    intercepted = []

    class Interceptor(grpc.aio.ServerInterceptor):
        async def intercept_service(self, continuation, details):
            intercepted.append(details.method)
            return await continuation(details)

    server = grpc.aio.server(
        interceptors=[Interceptor()], options=[("grpc.server_handshake_timeout_ms", 500)]
    )

    async def ping(request, context):
        return b"ok"

    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "probe.Test",
                {
                    "Ping": grpc.unary_unary_rpc_method_handler(ping),
                },
            ),
        )
    )
    port = server.add_secure_port(
        "127.0.0.1:0",
        grpc.ssl_server_credentials(
            [(server_key, server_cert)], root_certificates=ca, require_client_auth=True
        ),
    )
    await server.start()
    expected = []

    def connection(case):
        sock = socket.create_connection(("127.0.0.1", port), timeout=2)
        expected.append(
            {
                "case": case,
                "remote_ip": sock.getsockname()[0],
                "remote_port": sock.getsockname()[1],
                "local_ip": "127.0.0.1",
                "local_port": port,
            }
        )
        return sock

    def plaintext():
        with connection("http") as sock:
            sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
            try:
                sock.recv(512)
            except OSError:
                pass

    def no_cert():
        context = ssl.create_default_context(cadata=ca.decode())
        context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        with connection("missing_cert") as sock:
            try:
                with context.wrap_socket(sock, server_hostname="localhost") as tls:
                    tls.sendall(b"x")
                    tls.recv(512)
            except OSError:
                pass

    def old_tls():
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = ssl.TLSVersion.TLSv1
        context.maximum_version = ssl.TLSVersion.TLSv1_1
        context.set_ciphers("ALL:@SECLEVEL=0")
        with connection("old_tls") as sock:
            try:
                context.wrap_socket(sock, server_hostname="localhost").close()
            except OSError:
                pass

    for call in (plaintext, no_cert, old_tls):
        await asyncio.to_thread(call)
        await asyncio.sleep(0.1)
    with connection("abort") as sock:
        sock.sendall(b"\x16\x03\x01")
    await asyncio.sleep(0.1)
    with connection("timeout") as sock:
        await asyncio.sleep(0.8)

    # SNI rejection is checked with a real gRPC TLS client separately from the
    # known-source-port raw clients. A mismatching SNI may only be a warning.
    credentials = grpc.ssl_channel_credentials(ca, client_key, client_cert)
    statuses = {}
    for name in ("wrong.invalid", "localhost"):
        async with grpc.aio.secure_channel(
            f"127.0.0.1:{port}", credentials, options=[("grpc.ssl_target_name_override", name)]
        ) as channel:
            try:
                result = await channel.unary_unary("/probe.Test/Ping")(b"ping", timeout=1)
                statuses[name] = result.decode()
            except grpc.aio.AioRpcError as exc:
                statuses[name] = exc.code().name
    os.write(2, b"PROBE_NATIVE_PASSTHROUGH\n")
    sys.stderr.write("PROBE_PYTHON_PASSTHROUGH\n")
    await server.stop(0)
    await asyncio.sleep(0.3)
    native = capture.close() if capture is not None else ""
    # Prove native logging still reaches the original destination after restore.
    server2 = grpc.aio.server()
    restored_port = server2.add_secure_port(
        "127.0.0.1:0",
        grpc.ssl_server_credentials(
            [(server_key, server_cert)], root_certificates=ca, require_client_auth=True
        ),
    )
    await server2.start()

    def after_restore():
        with socket.create_connection(("127.0.0.1", restored_port), timeout=2) as sock:
            sock.sendall(b"GET /after-restore HTTP/1.1\r\n\r\n")
            try:
                sock.recv(512)
            except OSError:
                pass

    await asyncio.to_thread(after_restore)
    async with grpc.aio.secure_channel(
        f"127.0.0.1:{restored_port}",
        credentials,
        options=[("grpc.ssl_target_name_override", "restore-wrong.invalid")],
    ) as restored_channel:
        try:
            await asyncio.wait_for(restored_channel.channel_ready(), timeout=0.4)
        except TimeoutError:
            pass
    await asyncio.sleep(0.1)
    await server2.stop(0)
    for init_channel in init_channels:
        init_channel.close()
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(native, encoding="utf-8")
    print(
        json.dumps(
            {
                "grpcio": grpc.__version__,
                "timing": args.timing,
                "captured_bytes": len(native.encode()),
                "capture_truncated": capture.truncated if capture else False,
                "restored_port": restored_port,
                "expected": expected,
                "rpc_statuses": statuses,
                "intercepted": intercepted,
                "passthrough_native": "PROBE_NATIVE_PASSTHROUGH" in native,
                "passthrough_python": "PROBE_PYTHON_PASSTHROUGH" in native,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--timing",
        choices=("off", "before-import", "after-import", "after-init"),
        default="before-import",
    )
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--fd-only", action="store_true")
    parser.add_argument(
        "--capture-at",
        choices=("before-import", "after-import", "after-init"),
        default="before-import",
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.timing == "before-import":
        os.environ["GRPC_TRACE"] = "handshaker"
    else:
        os.environ.pop("GRPC_TRACE", None)
    asyncio.run(run(args))
