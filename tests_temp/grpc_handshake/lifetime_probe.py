"""Real Application/GrpcAdapter restarts; native pipe stays installed until exit."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import ssl
import time
from dataclasses import asdict
from pathlib import Path

from xime.core.config import BindingConfig, RuntimeConfig
from xime.observability import grpc_handshake_logging_stats, prepare_grpc_handshake_logging


async def main(args):
    native_cfg = {
        "enabled": args.native,
        "rate_limit_per_second": args.rate,
        "queue_capacity": args.capacity,
    }
    runtime = RuntimeConfig.from_dict(
        {
            "logging": {
                "console": {"enabled": args.console, "level": "ERROR"},
                "service_name": "native-probe",
                "file": {
                    "enabled": args.file,
                    "level": "DEBUG",
                    "path": str(args.workdir / "application.jsonl"),
                },
            },
            "grpc": {"handshake_logging": native_cfg},
        }
    )
    prepare_grpc_handshake_logging(runtime=runtime)
    import grpc
    from probe import certificates

    from xime import Application
    from xime.adapters.grpc import GrpcAdapter, configure_grpc_interceptors
    from xime.core.bootstrap._supervisor import prepare_worker

    events = []
    calls = []

    class Capture(logging.Handler):
        def emit(self, record):
            if args.slow_handler:
                import time

                time.sleep(args.slow_handler)
            if getattr(record, "event", None) == "grpc_tls_handshake_failed":
                events.append(
                    {
                        key: getattr(record, key, None)
                        for key in (
                            "server_id",
                            "remote_ip",
                            "remote_port",
                            "local_ip",
                            "local_port",
                            "cause",
                            "process",
                            "request_id",
                        )
                    }
                )

    logger = logging.getLogger("xime.grpc.handshake")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(Capture())

    class Counter(grpc.aio.ServerInterceptor):
        async def intercept_service(self, continuation, details):
            calls.append(details.method)
            return await continuation(details)

    configure_grpc_interceptors([Counter()])

    async def ping(request, context):
        return b"ok"

    class ProbeAdapter(GrpcAdapter):
        def _reuseport_option(self):
            return [*super()._reuseport_option(), ("grpc.server_handshake_timeout_ms", 400)]

        def _register_codefirst(self, app):
            self._server.add_generic_rpc_handlers(
                (
                    grpc.method_handlers_generic_handler(
                        "probe.Test",
                        {
                            "Ping": grpc.unary_unary_rpc_method_handler(ping),
                        },
                    ),
                )
            )

    ca, (server_key, server_cert), (client_key, client_cert) = certificates()
    for name, value in (("server.key", server_key), ("server.crt", server_cert), ("ca.crt", ca)):
        (args.workdir / name).write_bytes(value)
    host = "::1" if args.ipv6 else "127.0.0.1"
    family = socket.AF_INET6 if args.ipv6 else socket.AF_INET
    ports = []
    for _ in range(2):
        with socket.socket(family) as sock:
            sock.bind((host, 0))
            ports.append(sock.getsockname()[1])
    raw = runtime.model_dump()
    raw["grpc"]["tls"] = {
        "enabled": True,
        "mutual": True,
        "cert_file": str(args.workdir / "server.crt"),
        "key_file": str(args.workdir / "server.key"),
        "ca_file": str(args.workdir / "ca.crt"),
    }
    raw["process"] = {
        "grpc": {
            name: {"host": host, "port": port} for name, port in zip(("default", "other"), ports)
        }
    }
    runtime = RuntimeConfig.from_dict(raw)
    expected = []
    timings = []

    def fail(server_id, port, epoch, index):
        with socket.socket(family) as sock:
            sock.settimeout(2)
            sock.connect((host, port))
            expected.append(
                {
                    "server_id": server_id,
                    "remote_ip": host,
                    "remote_port": sock.getsockname()[1],
                    "local_ip": host,
                    "local_port": port,
                }
            )
            if args.all_faults and index == 1:
                context = ssl.create_default_context(cadata=ca.decode())
                context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
                try:
                    context.wrap_socket(sock, server_hostname="localhost").close()
                except OSError:
                    pass
                return
            if args.all_faults and index == 2:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                context.minimum_version = ssl.TLSVersion.TLSv1
                context.maximum_version = ssl.TLSVersion.TLSv1_1
                context.set_ciphers("ALL:@SECLEVEL=0")
                try:
                    context.wrap_socket(sock, server_hostname="localhost").close()
                except OSError:
                    pass
                return
            if args.all_faults and index == 3:
                sock.sendall(b"\x16\x03\x01")
                return
            if not (args.all_faults and index == 4):
                sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
            try:
                sock.recv(512)
            except OSError:
                pass

    for epoch in range(2):
        app = Application(binding=BindingConfig()).use(ProbeAdapter()).use(ProbeAdapter("other"))
        app._runtime = runtime
        topology = app._resolve_topology(runtime)
        app._adapters = prepare_worker(topology, app._adapters, topology.ids[0], {}, single=True)
        try:
            await app.start()
            await app._start_adapters()
            workload_started = time.perf_counter()
            cpu_started = time.process_time()
            if args.failures > 1:
                await asyncio.gather(
                    *(
                        asyncio.to_thread(fail, name, port, epoch, index)
                        for index in range(args.failures)
                        for name, port in zip(("default", "other"), ports)
                    )
                )
            else:
                for name, port in zip(("default", "other"), ports):
                    await asyncio.to_thread(fail, name, port, epoch, 0)
            credentials = grpc.ssl_channel_credentials(ca, client_key, client_cert)
            for port in ports:
                target = f"[{host}]:{port}" if args.ipv6 else f"{host}:{port}"
                async with grpc.aio.secure_channel(
                    target, credentials, options=[("grpc.ssl_target_name_override", "localhost")]
                ) as channel:
                    assert (
                        await channel.unary_unary("/probe.Test/Ping")(b"ping", timeout=3) == b"ok"
                    )
            workload_seconds = time.perf_counter() - workload_started
            await asyncio.sleep(0.2)
        finally:
            await app._stop_adapters()
            await app.stop()
        timings.append(
            {"workload_seconds": workload_seconds, "cpu_seconds": time.process_time() - cpu_started}
        )
        os.write(2, f"UNRELATED_STDERR_EPOCH_{epoch}\n".encode())
    await asyncio.sleep(0.1)
    print(
        json.dumps(
            {
                "events": events,
                "expected": expected,
                "intercepted": calls,
                "stats": asdict(grpc_handshake_logging_stats()),
                "timings": timings,
                "pid": os.getpid(),
                "version": grpc.__version__,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--file", action="store_true")
    parser.add_argument("--console", action="store_true")
    parser.add_argument("--ipv6", action="store_true")
    parser.add_argument("--failures", type=int, default=1)
    parser.add_argument("--all-faults", action="store_true")
    parser.add_argument("--rate", type=int, default=20)
    parser.add_argument("--capacity", type=int, default=1024)
    parser.add_argument("--slow-handler", type=float, default=0)
    args = parser.parse_args()
    if args.all_faults:
        args.failures = 5
    args.workdir.mkdir(parents=True, exist_ok=True)
    asyncio.run(main(args))
