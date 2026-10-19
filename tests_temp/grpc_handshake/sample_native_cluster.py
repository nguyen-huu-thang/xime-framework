"""Fixture process topology: native logging + real gRPC + primary/respawn."""

# ruff: noqa: E402 -- native setup must precede every grpc import
from xime.observability import prepare_grpc_handshake_logging

prepare_grpc_handshake_logging()

import asyncio
import os
from pathlib import Path
from types import ModuleType

import grpc

from xime import Application
from xime.adapters.grpc import GrpcAdapter
from xime.core.bootstrap.adapter import Adapter
from xime.core.config import BindingConfig


class ProbeGrpc(GrpcAdapter):
    def _register_codefirst(self, app):
        async def ping(request, context):
            return str(os.getpid()).encode()

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


class Control(Adapter, scaling="replicated"):
    adapter_kind = "control"
    adapter_id = "default"

    def assign_slot(self, slot):
        pass

    async def start(self, app):
        self.stopped = asyncio.Event()

    async def serve(self):
        pid = os.getpid()
        Path(f"{pid}.ready").touch()
        os.write(2, f"WORKER_STDERR_{pid}\n".encode())
        while not self.stopped.is_set():
            if Path(f"{pid}.die").exists():
                os._exit(23)
            await asyncio.sleep(0.03)

    async def stop(self):
        if hasattr(self, "stopped"):
            self.stopped.set()


class Primary(Control, scaling="singleton"):
    adapter_kind = "primaryprobe"

    async def start(self, app):
        self.stopped = asyncio.Event()
        Path(f"{os.getpid()}.primary").touch()

    async def serve(self):
        await self.stopped.wait()


config = ModuleType("native_probe_config")
config.dependency = BindingConfig()
app = Application().add_config(config).use(ProbeGrpc()).use(Control()).use(Primary())

if __name__ == "__main__":
    app.share_load().run()
