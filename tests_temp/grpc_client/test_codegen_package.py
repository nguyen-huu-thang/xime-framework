"""
Test chế độ --package của xime grpc client (Phase 4):

  - layout pip-installable: <out>/pyproject.toml + <out>/<module>/...
  - pyproject chứa name/version, dependency xime[grpc], package-data *.binpb
  - module import được (out_dir trên sys.path như khi pip install -e)
  - tên package không map được sang module hợp lệ → ValueError
  - không truyền package → layout phẳng như cũ (tương thích ngược)
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest

pytest.importorskip("grpc")
pytest.importorskip("grpc_tools")

from pydantic import BaseModel  # noqa: E402

from xime.adapters.grpc.client import generate_client_sdk  # noqa: E402
from xime.adapters.grpc.codefirst._builder import ContractBuilder  # noqa: E402
from xime.adapters.grpc.codefirst._lock import LockFile  # noqa: E402
from xime.adapters.grpc.codefirst._proto_emitter import ProtoEmitter  # noqa: E402
from xime.adapters.grpc.codefirst._sidecar import emit_sidecar  # noqa: E402
from xime.core.contract import command  # noqa: E402


class PingQuery(BaseModel):
    text: str


class PingReply(BaseModel):
    text: str


class PkgPingController:
    server_id = "pkgmode"

    @command("ping")
    async def ping(self, request: PingQuery) -> PingReply: ...


@pytest.fixture()
def proto_dir(tmp_path) -> str:
    """Sinh proto + sidecar của controller mẫu vào thư mục tạm."""
    model = ContractBuilder("pkgmode", LockFile()).build([PkgPingController])
    files = ProtoEmitter().emit(model)
    files["pkgmode/contract.json"] = emit_sidecar(model)
    out = tmp_path / "generated"
    for rel, text in files.items():
        path = out.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return str(out / "pkgmode")


class TestPackageMode:
    def test_layout_and_pyproject(self, proto_dir, tmp_path):
        out = tmp_path / "sdk"
        result = generate_client_sdk(
            proto_dir, str(out), package="ping-client", package_version="1.2.3"
        )

        # layout: pyproject ở root, SDK trong module dir tên gạch dưới
        assert (out / "pyproject.toml").exists()
        assert (out / "ping_client" / "__init__.py").exists()
        assert (out / "ping_client" / "_models.py").exists()
        assert (out / "ping_client" / "_descriptors.binpb").exists()
        assert str(out / "pyproject.toml") in result.written

        content = (out / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "ping-client"' in content
        assert 'version = "1.2.3"' in content
        assert "xime[grpc]" in content
        assert 'ping_client = ["*.binpb"]' in content

    def test_module_is_importable(self, proto_dir, tmp_path):
        out = tmp_path / "sdk"
        generate_client_sdk(proto_dir, str(out), package="ping-client")

        sys.path.insert(0, str(out))
        try:
            sdk = importlib.import_module("ping_client")
            assert hasattr(sdk, "PkgPingClient")
            assert hasattr(sdk, "PingQuery")
        finally:
            sys.path.remove(str(out))
            for mod in ("ping_client", "ping_client._clients", "ping_client._models"):
                sys.modules.pop(mod, None)

    def test_invalid_package_name_raises(self, proto_dir, tmp_path):
        with pytest.raises(ValueError, match="Invalid package name"):
            generate_client_sdk(proto_dir, str(tmp_path / "sdk"), package="123 bad")

    def test_no_package_keeps_flat_layout(self, proto_dir, tmp_path):
        out = tmp_path / "clients" / "ping"
        generate_client_sdk(proto_dir, str(out))
        assert (out / "__init__.py").exists()
        assert not (out / "pyproject.toml").exists()
        assert not (tmp_path / "clients" / "pyproject.toml").exists()
