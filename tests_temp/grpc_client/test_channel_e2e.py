"""E2E XimeGrpcChannel + ErrorMappingInterceptor (Phase 2) qua TCP thật.

Chứng minh:
  - SDK sinh ra (Phase 1) chạy nguyên vẹn trên XimeGrpcChannel thay vì
    grpc.aio.Channel trần - không sửa một dòng mã sinh nào
  - Controller raise exception → client nhận RemoteCallError typed,
    .code mang tên exception phía server (trailing metadata xime-error)
  - Deadline mặc định từ config → RemoteCallTimeout khi server chậm
"""
from __future__ import annotations

import asyncio
import importlib
import sys

import pytest

pytest.importorskip("grpc")
pytest.importorskip("grpc_tools")

import grpc.aio  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from xime.adapters.grpc.client import generate_client_sdk  # noqa: E402
from xime.adapters.grpc.client._channel import XimeGrpcChannel  # noqa: E402
from xime.adapters.grpc.client._config import GrpcClientConfig  # noqa: E402
from xime.adapters.grpc.codefirst._builder import ContractBuilder  # noqa: E402
from xime.adapters.grpc.codefirst._generator import _run_protoc  # noqa: E402
from xime.adapters.grpc.codefirst._lock import LockFile  # noqa: E402
from xime.adapters.grpc.codefirst._pb2_loader import load_message_classes  # noqa: E402
from xime.adapters.grpc.codefirst._proto_emitter import ProtoEmitter  # noqa: E402
from xime.adapters.grpc.codefirst._service_builder import CodeFirstGrpcBuilder  # noqa: E402
from xime.adapters.grpc.codefirst._sidecar import emit_sidecar  # noqa: E402
from xime.adapters.grpc.interceptors._error import ErrorMappingInterceptor  # noqa: E402
from xime.core.contract import command  # noqa: E402
from xime.core.exception.framework import (  # noqa: E402
    RemoteCallError,
    RemoteCallTimeout,
)


class EchoQuery(BaseModel):
    text: str


class EchoReply(BaseModel):
    text: str


class MissingThingError(Exception):
    pass


class Ch2EchoController:
    server_id = "ch2e2e"

    @command("echo")
    async def echo(self, request: EchoQuery) -> EchoReply:
        if request.text == "explode":
            raise MissingThingError("thing is gone")
        if request.text == "slow":
            await asyncio.sleep(1.0)
        return EchoReply(text=request.text)


class FakeApp:
    def __init__(self, instances: dict) -> None:
        self._instances = instances

    def get(self, cls):
        return self._instances[cls]


@pytest.mark.asyncio
async def test_generated_sdk_over_xime_channel(tmp_path):
    # 1) Sinh proto + sidecar + SDK (đường Phase 1).
    model = ContractBuilder("ch2e2e", LockFile()).build([Ch2EchoController])
    files = ProtoEmitter().emit(model)
    files["ch2e2e/contract.json"] = emit_sidecar(model)
    out = tmp_path / "generated"
    for rel, text in files.items():
        path = out.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _run_protoc(str(out), files)

    sdk_dir = tmp_path / "clients" / "ch2_sdk"
    generate_client_sdk(str(out / "ch2e2e"), str(sdk_dir))

    sys.path.insert(0, str(tmp_path / "clients"))
    try:
        sdk = importlib.import_module("ch2_sdk")

        # 2) Server thật với ErrorMappingInterceptor (map MissingThingError).
        messages = load_message_classes(str(out), "ch2e2e")
        server = grpc.aio.server(
            interceptors=[
                ErrorMappingInterceptor({MissingThingError: grpc.StatusCode.NOT_FOUND})
            ]
        )
        CodeFirstGrpcBuilder(
            FakeApp({Ch2EchoController: Ch2EchoController()}), model, messages
        ).register_all(server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()

        # 3) SDK chạy trên XimeGrpcChannel - không sửa mã sinh.
        channel = XimeGrpcChannel(
            "ch2", GrpcClientConfig(host="127.0.0.1", port=port, deadline_ms=300)
        )
        try:
            client = sdk.Ch2EchoClient(channel)

            # happy path
            reply = await client.echo(sdk.EchoQuery(text="hello"))
            assert reply.text == "hello"

            # lỗi nghiệp vụ → typed error, đúng status đã map + tên exception
            with pytest.raises(RemoteCallError) as err:
                await client.echo(sdk.EchoQuery(text="explode"))
            assert err.value.status == "NOT_FOUND"
            assert err.value.code == "MissingThingError"
            assert "thing is gone" in err.value.error_message
            assert err.value.path.endswith("Ch2EchoController/Echo")

            # deadline mặc định 300ms < server 1s → RemoteCallTimeout
            with pytest.raises(RemoteCallTimeout):
                await client.echo(sdk.EchoQuery(text="slow"))
        finally:
            await channel.close()
            await server.stop(None)
    finally:
        sys.path.remove(str(tmp_path / "clients"))
        for mod in ("ch2_sdk", "ch2_sdk._clients", "ch2_sdk._models"):
            sys.modules.pop(mod, None)
