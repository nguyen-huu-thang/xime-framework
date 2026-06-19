"""Test Code-First gRPC — generation pipeline (no grpc runtime needed).

  - Type mapping: scalars, list, dict, Optional, datetime, Annotated int, nested
  - Lock file: field-number stability across add / remove / re-add
  - Builder + emitter: command / upload / download shapes, oneof wrapper, shared→common
  - Generator: generate writes files, check detects drift
"""
from __future__ import annotations

import datetime
import enum
import os
from typing import Annotated, Optional

import pytest
from pydantic import BaseModel

from xime.adapters.grpc.codefirst._builder import ContractBuilder
from xime.adapters.grpc.codefirst._lock import LockFile
from xime.adapters.grpc.codefirst._proto_emitter import ProtoEmitter
from xime.adapters.grpc.codefirst._type_map import (
    ProtoInt32,
    ProtoUInt64,
    UnsupportedTypeError,
    map_type,
)
from xime.core.contract import DownloadStream, UploadStream, command, stream
from xime.core.exception import StartupException


# ---------------------------------------------------------------------------
# Fake registry for direct map_type tests
# ---------------------------------------------------------------------------

class _Reg:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.enums: list[str] = []

    def register_message(self, model) -> str:
        self.messages.append(model.__name__)
        return model.__name__

    def register_enum(self, en) -> str:
        self.enums.append(en.__name__)
        return en.__name__


class Sub(BaseModel):
    x: int


# ===========================================================================
# Type mapping
# ===========================================================================

@pytest.mark.parametrize(
    "py_type, expected",
    [
        (str, ("string", False)),
        (bytes, ("bytes", False)),
        (bool, ("bool", False)),
        (int, ("int64", False)),
        (float, ("double", False)),
        (list[str], ("repeated string", False)),
        (dict[str, int], ("map<string, int64>", False)),
        (Optional[str], ("string", True)),
        (str | None, ("string", True)),
        (Annotated[int, ProtoInt32], ("int32", False)),
        (Annotated[int, ProtoUInt64], ("uint64", False)),
    ],
)
def test_map_type_scalars(py_type, expected):
    assert map_type(py_type, _Reg()) == expected


def test_map_type_datetime():
    proto, optional = map_type(datetime.datetime, _Reg())
    assert proto == "google.protobuf.Timestamp"


def test_map_type_nested_registers_message():
    reg = _Reg()
    assert map_type(Sub, reg) == ("Sub", False)
    assert reg.messages == ["Sub"]


def test_map_type_unsupported_raises():
    class Weird:
        pass

    with pytest.raises(UnsupportedTypeError):
        map_type(Weird, _Reg())


# ===========================================================================
# Lock file — field-number stability (THE critical concern)
# ===========================================================================

def test_lock_keeps_numbers_and_appends_new():
    lock = LockFile()
    assert lock.assign_numbers("M", ["a", "b", "c"]) == {"a": 1, "b": 2, "c": 3}
    # add d → keeps a/b/c, d gets 4
    assert lock.assign_numbers("M", ["a", "b", "c", "d"]) == {"a": 1, "b": 2, "c": 3, "d": 4}


def test_lock_reserves_removed_and_never_reuses():
    lock = LockFile()
    lock.assign_numbers("M", ["a", "b", "c", "d"])     # a1 b2 c3 d4
    # remove b, add e → e must NOT reuse 2
    result = lock.assign_numbers("M", ["a", "c", "d", "e"])
    assert result["e"] == 5
    rec = lock.messages["M"]
    assert 2 in rec.reserved_numbers
    assert "b" in rec.reserved_names
    # re-adding b gets a fresh number, never the reserved 2
    again = lock.assign_numbers("M", ["a", "c", "d", "e", "b"])
    assert again["b"] != 2
    assert again["b"] == 6


def test_lock_roundtrip_save_load(tmp_path):
    lock = LockFile()
    lock.assign_numbers("M", ["a", "b"])
    path = str(tmp_path / "proto.lock.json")
    lock.save(path)

    loaded = LockFile.load(path)
    assert loaded.messages["M"].fields == {"a": 1, "b": 2}
    # numbers stay identical after a reload + regen
    assert loaded.assign_numbers("M", ["a", "b"]) == {"a": 1, "b": 2}


# ===========================================================================
# Builder + emitter
# ===========================================================================

class HashRequest(BaseModel):
    file_id: str


class HashResponse(BaseModel):
    digest: str


class EncryptRequest(BaseModel):
    name: str


class EncryptResponse(BaseModel):
    total: int


class DownloadRequest(BaseModel):
    parts: int


class CryptoController:
    server_id = "public"

    @command("hash")
    async def hash(self, request: HashRequest) -> HashResponse: ...

    @stream("encrypt")
    async def encrypt(self, request: EncryptRequest, upload: UploadStream) -> EncryptResponse: ...

    @stream("download")
    async def download(self, request: DownloadRequest, download: DownloadStream) -> None: ...


def _emit(controllers, server_id="public"):
    model = ContractBuilder(server_id, LockFile()).build(controllers)
    return model, ProtoEmitter().emit(model)


def test_emitter_renders_command_upload_download():
    _model, files = _emit([CryptoController])
    text = files["public/crypto.proto"]
    assert "rpc Hash(HashRequest) returns (HashResponse);" in text
    assert "rpc Encrypt(stream EncryptChunk) returns (EncryptResponse);" in text
    assert "rpc Download(DownloadRequest) returns (stream DownloadChunk);" in text


def test_emitter_upload_wrapper_is_oneof():
    _model, files = _emit([CryptoController])
    text = files["public/crypto.proto"]
    assert "message EncryptChunk {" in text
    assert "oneof payload {" in text
    assert "EncryptRequest metadata = 1;" in text
    assert "bytes chunk = 2;" in text


def test_emitter_header_and_package():
    _model, files = _emit([CryptoController])
    text = files["public/crypto.proto"]
    assert text.startswith("// Code generated by `xime grpc generate`. DO NOT EDIT.")
    assert 'syntax = "proto3";' in text
    assert "package xime.public;" in text


class UserResponse(BaseModel):
    id: int
    name: str


class GetReq(BaseModel):
    id: int


class UserController:
    server_id = "public"

    @command("get")
    async def get(self, request: GetReq) -> UserResponse: ...


class ProfileController:
    server_id = "public"

    @command("me")
    async def me(self, request: GetReq) -> UserResponse: ...


class Color(enum.IntEnum):
    RED = 1
    GREEN = 2


class ColorReq(BaseModel):
    id: int


class ColorResp(BaseModel):
    color: Color


class ColorController:
    server_id = "public"

    @command("c")
    async def c(self, request: ColorReq) -> ColorResp: ...


def test_shared_message_goes_to_common():
    # UserResponse used by two controllers → common.proto; both import it.
    model = ContractBuilder("public", LockFile()).build([UserController, ProfileController])
    files = ProtoEmitter().emit(model)
    assert "public/common.proto" in files
    assert "message UserResponse" in files["public/common.proto"]
    assert 'import "common.proto";' in files["public/user.proto"]
    assert 'import "common.proto";' in files["public/profile.proto"]


def test_builder_rejects_missing_response():
    class Bad:
        server_id = "public"

        @command("x")
        async def x(self, request: HashRequest): ...   # no return annotation

    with pytest.raises(StartupException):
        ContractBuilder("public", LockFile()).build([Bad])


def test_builder_rejects_sync_command():
    # A plain `def` endpoint would crash at the first RPC (server awaits it).
    class Bad:
        server_id = "public"

        @command("x")
        def x(self, request: HashRequest) -> HashResponse: ...   # not async

    with pytest.raises(StartupException, match="async def"):
        ContractBuilder("public", LockFile()).build([Bad])


def test_builder_rejects_async_generator_command():
    # An `async def` with `yield` is an async generator, not a coroutine —
    # awaiting it raises TypeError. Must be rejected at startup too.
    class Bad:
        server_id = "public"

        @command("x")
        async def x(self, request: HashRequest) -> HashResponse:
            yield  # makes this an async generator function

    with pytest.raises(StartupException, match="async def"):
        ContractBuilder("public", LockFile()).build([Bad])


def test_enum_unspecified_prepended():
    model = ContractBuilder("public", LockFile()).build([ColorController])
    text = ProtoEmitter().emit(model)["public/color.proto"]
    assert "enum Color {" in text
    assert "COLOR_UNSPECIFIED = 0;" in text
    assert "RED = 1;" in text


# ===========================================================================
# Generator — generate + check (drift detection)
# ===========================================================================

@pytest.fixture
def cf_package(tmp_path, monkeypatch):
    """Write a temp package with a controller, importable by ControllerScanner."""
    import sys

    pkg_dir = tmp_path / "cf_app"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "controllers.py").write_text(
        "from pydantic import BaseModel\n"
        "from xime.core.contract import command\n\n"
        "class PingReq(BaseModel):\n    msg: str\n\n"
        "class PongResp(BaseModel):\n    msg: str\n\n"
        "class PingController:\n"
        "    server_id = 'public'\n"
        "    @command('ping')\n"
        "    async def ping(self, request: PingReq) -> PongResp: ...\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    # Drop any cached import from a previous test run.
    for name in list(sys.modules):
        if name == "cf_app" or name.startswith("cf_app."):
            del sys.modules[name]
    return "cf_app"


def test_generate_writes_proto_and_lock(cf_package, tmp_path):
    from xime.adapters.grpc.codefirst._generator import generate

    out = str(tmp_path / "generated")
    lock = str(tmp_path / "proto.lock.json")
    result = generate([cf_package], output_dir=out, lock_file=lock, run_protoc=False)

    proto_path = os.path.join(out, "public", "ping.proto")
    assert proto_path in result.written
    assert os.path.exists(proto_path)
    assert os.path.exists(lock)
    text = open(proto_path, encoding="utf-8").read()
    assert "rpc Ping(PingReq) returns (PongResp);" in text


def test_check_ok_then_detects_drift(cf_package, tmp_path):
    from xime.adapters.grpc.codefirst._generator import check, generate

    out = str(tmp_path / "generated")
    lock = str(tmp_path / "proto.lock.json")
    generate([cf_package], output_dir=out, lock_file=lock, run_protoc=False)

    assert check([cf_package], output_dir=out, lock_file=lock).ok

    # Corrupt the file on disk → stale
    proto_path = os.path.join(out, "public", "ping.proto")
    open(proto_path, "a", encoding="utf-8").write("\n// tampered\n")
    res = check([cf_package], output_dir=out, lock_file=lock)
    assert not res.ok
    assert proto_path in res.stale

    # Remove the file → missing
    os.remove(proto_path)
    res2 = check([cf_package], output_dir=out, lock_file=lock)
    assert not res2.ok
    assert proto_path in res2.missing


# ===========================================================================
# CLI — xime grpc generate / check (config loading + exit codes)
# ===========================================================================

@pytest.fixture
def cli_project(tmp_path, monkeypatch):
    """A project tree with a controller package and a config package."""
    import sys

    (tmp_path / "cli_app").mkdir()
    (tmp_path / "cli_app" / "__init__.py").write_text("")
    (tmp_path / "cli_app" / "controllers.py").write_text(
        "from pydantic import BaseModel\n"
        "from xime.core.contract import command\n\n"
        "class PingReq(BaseModel):\n    msg: str\n\n"
        "class PongResp(BaseModel):\n    msg: str\n\n"
        "class PingController:\n"
        "    server_id = 'public'\n"
        "    @command('ping')\n"
        "    async def ping(self, request: PingReq) -> PongResp: ...\n"
    )
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "__init__.py").write_text("")
    (tmp_path / "config" / "grpc.py").write_text(
        "from xime.adapters.grpc.codefirst import configure_grpc_codefirst\n"
        "configure_grpc_codefirst(packages=['cli_app'], output_dir='generated', "
        "lock_file='proto.lock.json')\n"
    )

    monkeypatch.chdir(tmp_path)
    from xime.adapters.grpc.codefirst._config import codefirst_registry
    codefirst_registry.reset()
    for name in list(sys.modules):
        if name in ("cli_app", "config") or name.startswith(("cli_app.", "config.")):
            del sys.modules[name]
    yield tmp_path
    codefirst_registry.reset()


def test_cli_generate_then_check(cli_project):
    from xime.cli._main import main

    assert main(["grpc", "generate", "--no-protoc"]) == 0
    assert (cli_project / "generated" / "public" / "ping.proto").exists()
    assert (cli_project / "proto.lock.json").exists()

    # check passes right after generate
    assert main(["grpc", "check"]) == 0

    # tamper → check fails with non-zero exit
    (cli_project / "generated" / "public" / "ping.proto").write_text("// broken\n")
    assert main(["grpc", "check"]) == 1
