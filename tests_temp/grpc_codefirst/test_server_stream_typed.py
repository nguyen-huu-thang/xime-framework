"""Server streaming of TYPED records (not byte chunks).

`@stream` + an `async def ... -> AsyncIterator[Model]` handler produces
`rpc Watch(Req) returns (stream Resp)` - the response side is an ordinary DTO,
so a Java peer reads the .proto without knowing anything about xime's chunk
wrapper. The byte-download form (DownloadStream) is untouched.
`@stream` + handler async generator sinh ra `returns (stream Resp)` với DTO
thường; dạng tải file theo byte (DownloadStream) giữ nguyên.

Covered here: contract IR, .proto text, sidecar, startup validation, the
generated SDK end-to-end over real gRPC, handler cleanup on cancellation, and
the proto-only fallback (a Python service consuming a JAVA service's stream).
"""
from __future__ import annotations

import importlib
import shutil
import sys
from collections.abc import AsyncIterator

import pytest

pytest.importorskip("grpc")
pytest.importorskip("grpc_tools")

import grpc.aio  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from xime.adapters.grpc.client import generate_client_sdk  # noqa: E402
from xime.adapters.grpc.codefirst._builder import ContractBuilder  # noqa: E402
from xime.adapters.grpc.codefirst._generator import _run_protoc  # noqa: E402
from xime.adapters.grpc.codefirst._lock import LockFile  # noqa: E402
from xime.adapters.grpc.codefirst._model import StreamKind  # noqa: E402
from xime.adapters.grpc.codefirst._pb2_loader import load_message_classes  # noqa: E402
from xime.adapters.grpc.codefirst._proto_emitter import ProtoEmitter  # noqa: E402
from xime.adapters.grpc.codefirst._service_builder import (  # noqa: E402
    CodeFirstGrpcBuilder,
)
from xime.adapters.grpc.codefirst._sidecar import emit_sidecar  # noqa: E402
from xime.core.contract import DownloadStream, command, stream  # noqa: E402
from xime.core.exception.framework import StartupException  # noqa: E402


# ---------------------------------------------------------------------------
# DTOs + controller (module level so get_type_hints resolves the annotations)
# ---------------------------------------------------------------------------

class WatchRequest(BaseModel):
    after_sequence: int


class WatchEvent(BaseModel):
    sequence: int
    account_id: str


class TypedWatchController:
    server_id = "typedstream"

    def __init__(self) -> None:
        self.closed = False

    @command("ping")
    async def ping(self, request: WatchRequest) -> WatchEvent:
        return WatchEvent(sequence=request.after_sequence, account_id="ping")

    @stream("watch")
    async def watch(self, request: WatchRequest) -> AsyncIterator[WatchEvent]:
        try:
            for i in range(1, 4):
                yield WatchEvent(
                    sequence=request.after_sequence + i,
                    account_id=f"acc-{i}",
                )
        finally:
            # Proves the handler's own cleanup runs when the client goes away.
            self.closed = True


class FakeApp:
    def __init__(self, instances: dict) -> None:
        self._instances = instances

    def get(self, cls):
        return self._instances[cls]


def _build_model():
    return ContractBuilder("typedstream", LockFile()).build([TypedWatchController])


def _method(model, rpc_name: str):
    return next(m for m in model.services[0].methods if m.rpc_name == rpc_name)


# ---------------------------------------------------------------------------
# Contract IR / proto / sidecar
# ---------------------------------------------------------------------------

class TestContract:
    def test_kind_is_typed_stream(self):
        method = _method(_build_model(), "Watch")
        assert method.kind is StreamKind.SERVER_STREAM_TYPED
        assert method.response_py is WatchEvent
        # No stream parameter: the handler IS the generator.
        assert method.stream_param == ""

    def test_response_message_is_the_dto_not_a_wrapper(self):
        model = _build_model()
        assert _method(model, "Watch").response_message == "WatchEvent"
        assert "WatchChunk" not in model.messages

    def test_proto_declares_stream_of_the_dto(self):
        model = _build_model()
        text = "".join(ProtoEmitter().emit(model).values())
        assert "rpc Watch(WatchRequest) returns (stream WatchEvent);" in text
        # The unary sibling is unaffected.
        assert "rpc Ping(WatchRequest) returns (WatchEvent);" in text

    def test_sidecar_entry_carries_response_and_no_wrapper(self):
        import json

        payload = json.loads(emit_sidecar(_build_model()))
        entry = payload["services"]["TypedWatchController"]["methods"]["Watch"]
        assert entry["kind"] == "server_stream_typed"
        assert entry["request"] == "WatchRequest"
        assert entry["response"] == "WatchEvent"
        assert "wrapper" not in entry
        assert payload["wrappers"] == []


# ---------------------------------------------------------------------------
# Startup validation - every wrong shape must fail at build time, not at the
# first RPC.
# ---------------------------------------------------------------------------

class SyncGenIsNotAllowed:
    server_id = "bad"

    @command("tick")
    async def tick(self, request: WatchRequest) -> AsyncIterator[WatchEvent]:
        yield WatchEvent(sequence=1, account_id="x")


class BothStreamParamAndYield:
    server_id = "bad"

    @stream("tick")
    async def tick(
        self, request: WatchRequest, download: DownloadStream
    ) -> AsyncIterator[WatchEvent]:
        yield WatchEvent(sequence=1, account_id="x")


class MissingIteratorAnnotation:
    server_id = "bad"

    @stream("tick")
    async def tick(self, request: WatchRequest) -> WatchEvent:
        yield WatchEvent(sequence=1, account_id="x")


class YieldsSomethingElse:
    server_id = "bad"

    @stream("tick")
    async def tick(self, request: WatchRequest) -> AsyncIterator[str]:
        yield "not a model"


class NeitherStreamParamNorYield:
    server_id = "bad"

    @stream("tick")
    async def tick(self, request: WatchRequest) -> WatchEvent:
        return WatchEvent(sequence=1, account_id="x")


class TestValidation:
    @staticmethod
    def _build(controller: type) -> str:
        with pytest.raises(StartupException) as exc:
            ContractBuilder("bad", LockFile()).build([controller])
        return str(exc.value)

    def test_command_cannot_be_a_generator(self):
        assert "@command" in self._build(SyncGenIsNotAllowed)

    def test_stream_param_and_yield_are_mutually_exclusive(self):
        message = self._build(BothStreamParamAndYield)
        assert "not both" in message

    def test_yield_without_async_iterator_annotation(self):
        assert "AsyncIterator" in self._build(MissingIteratorAnnotation)

    def test_yielded_type_must_be_a_basemodel(self):
        assert "AsyncIterator" in self._build(YieldsSomethingElse)

    def test_plain_coroutine_stream_still_rejected(self):
        message = self._build(NeitherStreamParamNorYield)
        assert "UploadStream or DownloadStream" in message


# ---------------------------------------------------------------------------
# Serving glue
# ---------------------------------------------------------------------------

class TestServingGlue:
    @pytest.mark.asyncio
    async def test_handler_generator_is_closed_on_cancellation(self, tmp_path):
        """A watch stream lives for hours; when the client leaves, the handler's
        `finally:` must run then - not whenever the GC gets to it."""
        model = _build_model()
        files = ProtoEmitter().emit(model)
        out = tmp_path / "generated"
        for rel, text in files.items():
            path = out.joinpath(*rel.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        _run_protoc(str(out), files)
        messages = load_message_classes(str(out), "typedstream")

        controller = TypedWatchController()
        builder = CodeFirstGrpcBuilder(
            FakeApp({TypedWatchController: controller}), model, messages
        )
        method = _method(model, "Watch")
        handler = builder._server_stream_typed_handler(method, controller.watch)

        request = messages["WatchRequest"](after_sequence=10)
        agen = handler.unary_stream(request, context=None)
        first = await agen.__anext__()
        assert first.sequence == 11
        assert controller.closed is False

        await agen.aclose()  # what gRPC does when the peer disappears
        assert controller.closed is True


# ---------------------------------------------------------------------------
# End to end: generated SDK ↔ real server over TCP
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generated_sdk_consumes_typed_stream(tmp_path):
    model = _build_model()
    files = ProtoEmitter().emit(model)
    files["typedstream/contract.json"] = emit_sidecar(model)

    out = tmp_path / "generated"
    for rel, text in files.items():
        path = out.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _run_protoc(str(out), files)

    sdk_root = tmp_path / "clients"
    result = generate_client_sdk(str(out / "typedstream"), str(sdk_root / "watch_sdk"))
    assert not result.skipped_methods

    sys.path.insert(0, str(sdk_root))
    try:
        sdk = importlib.import_module("watch_sdk")

        messages = load_message_classes(str(out), "typedstream")
        controller = TypedWatchController()
        server = grpc.aio.server()
        CodeFirstGrpcBuilder(
            FakeApp({TypedWatchController: controller}), model, messages
        ).register_all(server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()

        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                client = sdk.TypedWatchClient(channel)

                events = [
                    event
                    async for event in client.watch(sdk.WatchRequest(after_sequence=100))
                ]
                assert [e.sequence for e in events] == [101, 102, 103]
                assert [e.account_id for e in events] == ["acc-1", "acc-2", "acc-3"]
                # Typed all the way through - not bytes, not a wrapper.
                assert isinstance(events[0], sdk.WatchEvent)
        finally:
            await server.stop(None)
    finally:
        sys.path.remove(str(sdk_root))
        for mod in ("watch_sdk", "watch_sdk._clients", "watch_sdk._models"):
            sys.modules.pop(mod, None)


def test_proto_only_fallback_generates_server_streams(tmp_path):
    """No contract.json - the case of consuming a JAVA service.

    Before this feature every streaming method was skipped, which is exactly
    the link the platform needs (Python data-service ← Java user-service).
    """
    model = _build_model()
    files = ProtoEmitter().emit(model)
    out = tmp_path / "generated"
    for rel, text in files.items():
        path = out.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _run_protoc(str(out), files)

    # A foreign service ships .proto only.
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    for proto in (out / "typedstream").glob("*.proto"):
        shutil.copy(proto, foreign / proto.name)
    assert not (foreign / "contract.json").exists()

    sdk_root = tmp_path / "clients"
    result = generate_client_sdk(str(foreign), str(sdk_root / "foreign_sdk"))
    assert not result.skipped_methods

    source = (sdk_root / "foreign_sdk" / "_clients.py").read_text(encoding="utf-8")
    assert "def watch(self, request: WatchRequest) -> AsyncIterator[WatchEvent]:" in source
    assert "server_stream_typed" in source
