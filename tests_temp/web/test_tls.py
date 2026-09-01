"""
Test TLS (HTTPS) cho web adapter (0.6.3):

  _tls_kwargs() - validate + dựng tham số ssl_* cho uvicorn:
    - không cấu hình -> dict rỗng (HTTP thuần, hành vi cũ y nguyên)
    - certfile + keyfile hợp lệ -> ssl_certfile/ssl_keyfile
    - chỉ certfile / chỉ keyfile -> StartupException nêu đúng thiếu gì
    - file không tồn tại -> StartupException nêu key + đường dẫn
    - cert_reqs/ciphers không cấu hình -> KHÔNG truyền (giữ mặc định uvicorn)
    - cert_reqs dạng chữ -> ánh xạ đúng hằng ssl.CERT_*
    - cert_reqs sai chính tả -> Pydantic từ chối lúc dựng config

  uvicorn.Config - nối dây thật, không mock:
    - không TLS -> is_ssl False
    - có TLS   -> is_ssl True, config.ssl là SSLContext sau load()

  WebAdapter(ssl=...) - multi-server:
    - mặc định kế thừa WebServerConfig.from_runtime(runtime).ssl
    - truyền ssl tường minh -> đè lên server.ssl
    - truyền ServerTlsConfig() rỗng -> tắt TLS cho riêng server đó
"""
import datetime
import os
import ssl

import pytest
import uvicorn
from fastapi import FastAPI

from xime.adapters.web import ServerTlsConfig, WebAdapter, WebServerConfig
from xime.adapters.web._adapter import _tls_kwargs
from xime.core.bootstrap._processes import EndpointSpec
from xime.core.bootstrap._slot import AdapterSlot
from xime.core.config import RuntimeConfig
from xime.core.exception import StartupException

# ---------------------------------------------------------------------------
# Fixtures - cert tự ký, không cần CA thật
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cert_pair(tmp_path_factory):
    """Sinh một cặp cert/key tự ký, trả (certfile, keyfile) dạng str."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    directory = tmp_path_factory.mktemp("tls")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
        )
        .sign(key, hashes.SHA256())
    )

    certfile = directory / "cert.pem"
    keyfile = directory / "key.pem"
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return str(certfile), str(keyfile)


@pytest.fixture
def tls(cert_pair) -> ServerTlsConfig:
    certfile, keyfile = cert_pair
    return ServerTlsConfig(certfile=certfile, keyfile=keyfile)


# ---------------------------------------------------------------------------
# _tls_kwargs - không cấu hình
# ---------------------------------------------------------------------------

class TestTlsDisabled:
    def test_empty_config_yields_no_kwargs(self):
        assert _tls_kwargs(ServerTlsConfig(), "default") == {}

    def test_default_server_config_has_tls_disabled(self):
        assert WebServerConfig.from_runtime(RuntimeConfig()).ssl.enabled is False

    def test_enabled_property_follows_certfile_or_keyfile(self, cert_pair):
        certfile, keyfile = cert_pair
        assert ServerTlsConfig(certfile=certfile).enabled is True
        assert ServerTlsConfig(keyfile=keyfile).enabled is True
        assert ServerTlsConfig(ciphers="HIGH").enabled is False


# ---------------------------------------------------------------------------
# _tls_kwargs - fail fast khi cấu hình sai
# ---------------------------------------------------------------------------

class TestTlsValidation:
    @staticmethod
    def _missing_line(exc) -> str:
        """Chỉ lấy dòng 'Missing :' - phần Detail nhắc cả hai tên nên không xét."""
        return next(
            line for line in str(exc.value).splitlines() if "Missing" in line
        )

    def test_certfile_without_keyfile_fails(self, cert_pair):
        certfile, _ = cert_pair
        with pytest.raises(StartupException) as exc:
            _tls_kwargs(ServerTlsConfig(certfile=certfile), "default")
        missing = self._missing_line(exc)
        assert "keyfile" in missing
        assert "certfile" not in missing

    def test_keyfile_without_certfile_fails(self, cert_pair):
        _, keyfile = cert_pair
        with pytest.raises(StartupException) as exc:
            _tls_kwargs(ServerTlsConfig(keyfile=keyfile), "default")
        missing = self._missing_line(exc)
        assert "certfile" in missing
        assert "keyfile" not in missing.replace("certfile", "")

    def test_missing_certfile_on_disk_fails_with_path(self, cert_pair):
        _, keyfile = cert_pair
        config = ServerTlsConfig(certfile="/nope/absent.pem", keyfile=keyfile)
        with pytest.raises(StartupException) as exc:
            _tls_kwargs(config, "default")
        message = str(exc.value)
        assert "certfile" in message
        assert "/nope/absent.pem" in message

    def test_missing_keyfile_on_disk_fails_with_path(self, cert_pair):
        certfile, _ = cert_pair
        config = ServerTlsConfig(certfile=certfile, keyfile="/nope/absent-key.pem")
        with pytest.raises(StartupException) as exc:
            _tls_kwargs(config, "default")
        assert "/nope/absent-key.pem" in str(exc.value)

    def test_missing_ca_certs_on_disk_fails(self, tls):
        config = tls.model_copy(update={"ca_certs": "/nope/ca.pem"})
        with pytest.raises(StartupException) as exc:
            _tls_kwargs(config, "default")
        assert "ca_certs" in str(exc.value)

    def test_directory_instead_of_file_fails(self, cert_pair, tmp_path):
        _, keyfile = cert_pair
        config = ServerTlsConfig(certfile=str(tmp_path), keyfile=keyfile)
        with pytest.raises(StartupException) as exc:
            _tls_kwargs(config, "default")
        assert "not a regular file" in str(exc.value)

    @pytest.mark.skipif(
        os.name == "nt", reason="chmod 000 không chặn đọc trên Windows"
    )
    def test_unreadable_keyfile_fails_with_permission_detail(self, cert_pair, tmp_path):
        """Ca thật hay gặp: certbot ghi privkey.pem chỉ cho root."""
        certfile, keyfile = cert_pair
        locked = tmp_path / "locked-key.pem"
        locked.write_bytes(open(keyfile, "rb").read())
        locked.chmod(0o000)
        try:
            config = ServerTlsConfig(certfile=certfile, keyfile=str(locked))
            with pytest.raises(StartupException) as exc:
                _tls_kwargs(config, "default")
            message = str(exc.value)
            assert "Not Readable" in message
            assert str(locked) in message
        finally:
            locked.chmod(0o600)

    def test_error_names_the_server_id(self, cert_pair):
        certfile, _ = cert_pair
        with pytest.raises(StartupException) as exc:
            _tls_kwargs(ServerTlsConfig(certfile=certfile), "admin")
        assert "admin" in str(exc.value)

    def test_invalid_cert_reqs_spelling_rejected_by_config(self):
        with pytest.raises(Exception):
            ServerTlsConfig(cert_reqs="mandatory")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _tls_kwargs - nội dung kwargs
# ---------------------------------------------------------------------------

class TestTlsKwargs:
    def test_minimal_config_passes_cert_and_key_only(self, tls, cert_pair):
        certfile, keyfile = cert_pair
        assert _tls_kwargs(tls, "default") == {
            "ssl_certfile": certfile,
            "ssl_keyfile": keyfile,
        }

    def test_unset_optionals_are_not_forwarded(self, tls):
        """uvicorn có mặc định riêng cho cert_reqs/ciphers - truyền None sẽ vỡ."""
        kwargs = _tls_kwargs(tls, "default")
        assert "ssl_cert_reqs" not in kwargs
        assert "ssl_ciphers" not in kwargs
        assert "ssl_ca_certs" not in kwargs
        assert "ssl_keyfile_password" not in kwargs

    @pytest.mark.parametrize(
        "spelling,expected",
        [
            ("none", ssl.CERT_NONE),
            ("optional", ssl.CERT_OPTIONAL),
            ("required", ssl.CERT_REQUIRED),
        ],
    )
    def test_cert_reqs_spelling_maps_to_stdlib_constant(self, tls, spelling, expected):
        config = tls.model_copy(update={"cert_reqs": spelling})
        assert _tls_kwargs(config, "default")["ssl_cert_reqs"] == expected

    def test_cert_reqs_none_string_is_forwarded_not_dropped(self, tls):
        """`cert_reqs: none` là lựa chọn tường minh, khác với bỏ trống."""
        config = tls.model_copy(update={"cert_reqs": "none"})
        assert "ssl_cert_reqs" in _tls_kwargs(config, "default")

    def test_mtls_options_forwarded(self, tls, cert_pair):
        certfile, _ = cert_pair
        config = tls.model_copy(
            update={"ca_certs": certfile, "cert_reqs": "required", "ciphers": "HIGH"}
        )
        kwargs = _tls_kwargs(config, "default")
        assert kwargs["ssl_ca_certs"] == certfile
        assert kwargs["ssl_cert_reqs"] == ssl.CERT_REQUIRED
        assert kwargs["ssl_ciphers"] == "HIGH"

    def test_keyfile_password_forwarded(self, tls):
        config = tls.model_copy(update={"keyfile_password": "s3cret"})
        assert _tls_kwargs(config, "default")["ssl_keyfile_password"] == "s3cret"


# ---------------------------------------------------------------------------
# Nối dây thật với uvicorn.Config (không mock)
# ---------------------------------------------------------------------------

class TestUvicornWiring:
    def test_without_tls_config_is_not_ssl(self):
        config = uvicorn.Config(FastAPI(), host="127.0.0.1", port=0)
        assert config.is_ssl is False

    def test_with_tls_config_builds_ssl_context(self, tls):
        config = uvicorn.Config(
            FastAPI(), host="127.0.0.1", port=0, **_tls_kwargs(tls, "default")
        )
        assert config.is_ssl is True
        config.load()
        assert isinstance(config.ssl, ssl.SSLContext)

    def test_mtls_options_survive_context_build(self, tls, cert_pair):
        """Ca dễ vỡ nhất: cert_reqs/ca_certs phải dựng được context thật."""
        certfile, _ = cert_pair
        config_model = tls.model_copy(
            update={"ca_certs": certfile, "cert_reqs": "required"}
        )
        config = uvicorn.Config(
            FastAPI(), host="127.0.0.1", port=0, **_tls_kwargs(config_model, "default")
        )
        config.load()
        assert config.ssl.verify_mode == ssl.CERT_REQUIRED


# ---------------------------------------------------------------------------
# End-to-end: phục vụ HTTPS thật rồi gọi vào
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_real_https_request_succeeds(tls, cert_pair):
    """Chạy uvicorn thật với cert tự ký và gọi HTTPS vào - chứng minh cả dây nối.

    Đây là ca duy nhất bắt được lỗi ở khâu handshake thật, thứ mà kiểm tra kwargs
    hay SSLContext tĩnh không thấy được.
    """
    import asyncio

    import httpx

    certfile, _ = cert_pair
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        log_level="warning",
        **_tls_kwargs(tls, "default"),
    )
    server = uvicorn.Server(config)
    serving = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(10):
            while not server.started:
                await asyncio.sleep(0.01)

            port = server.servers[0].sockets[0].getsockname()[1]
            # Tin đúng cert tự ký vừa sinh, không tắt verify - nếu framework nối
            # dây sai thì handshake hỏng thật chứ không bị che.
            trust = ssl.create_default_context(cafile=certfile)
            async with httpx.AsyncClient(verify=trust) as client:
                response = await client.get(f"https://localhost:{port}/ping")

        assert response.status_code == 200
        assert response.json() == {"ok": True}
    finally:
        server.should_exit = True
        await serving


# ---------------------------------------------------------------------------
# WebAdapter - kế thừa và override TLS
# ---------------------------------------------------------------------------

class TestWebAdapterTlsResolution:
    """⚠ **ĐỔI Ở 0.8**: `ssl` không còn là đối số constructor - nó ở trong ô cấu
    hình (`process.web.<id>.ssl`). Tính chất bảo mật thì **giữ nguyên**: ô không
    khai thì kế thừa `server.ssl`, vì một server phụ âm thầm chạy HTTP trong khi
    server chính đã HTTPS là lỗ hổng không ai để ý.
    """

    @staticmethod
    def _slot(adapter_id: str, options: dict) -> AdapterSlot:
        spec = EndpointSpec(
            kind="web", adapter_id=adapter_id, host=None, port=8081,
            path=None, shared=False, options=options,
        )
        return AdapterSlot(
            process_id="main", primary=True, spec=spec, single=True
        )

    def test_a_cell_without_ssl_inherits_server_ssl(self, cert_pair):
        certfile, keyfile = cert_pair
        runtime = RuntimeConfig.from_dict(
            {"server": {"ssl": {"certfile": certfile, "keyfile": keyfile}}}
        )
        resolved = WebAdapter.resolve_tls(self._slot("default", {}), runtime)
        assert resolved.certfile == certfile

    def test_a_secondary_endpoint_inherits_it_too(self, cert_pair):
        """Server phụ KHÔNG được âm thầm chạy HTTP khi server chính đã HTTPS."""
        certfile, keyfile = cert_pair
        runtime = RuntimeConfig.from_dict(
            {"server": {"ssl": {"certfile": certfile, "keyfile": keyfile}}}
        )
        resolved = WebAdapter.resolve_tls(self._slot("admin", {}), runtime)
        assert resolved.enabled is True

    def test_a_cell_with_its_own_ssl_wins(self, cert_pair):
        certfile, keyfile = cert_pair
        runtime = RuntimeConfig.from_dict(
            {"server": {"ssl": {"certfile": "/other/cert.pem", "keyfile": keyfile}}}
        )
        slot = self._slot("admin", {"ssl": {"certfile": certfile, "keyfile": keyfile}})
        assert WebAdapter.resolve_tls(slot, runtime).certfile == certfile

    def test_an_empty_ssl_block_opts_an_endpoint_out(self, cert_pair):
        """Vế đối chứng của kế thừa, và là chỗ `ssl=ServerTlsConfig()` cũ về.

        Không có nó thì kế thừa trở thành ép buộc, và một điểm phục vụ nội bộ
        không có cách nào cố ý chạy HTTP thuần.
        """
        certfile, keyfile = cert_pair
        runtime = RuntimeConfig.from_dict(
            {"server": {"ssl": {"certfile": certfile, "keyfile": keyfile}}}
        )
        resolved = WebAdapter.resolve_tls(self._slot("internal", {"ssl": {}}), runtime)
        assert resolved.enabled is False
        assert _tls_kwargs(resolved, "internal") == {}

    def test_no_ssl_anywhere_stays_plain_http(self):
        resolved = WebAdapter.resolve_tls(self._slot("default", {}), RuntimeConfig())
        assert resolved.enabled is False
        assert _tls_kwargs(resolved, "default") == {}


# ---------------------------------------------------------------------------
# Cấu hình từ YAML (dot-notation vẫn đọc được)
# ---------------------------------------------------------------------------

def test_runtime_config_parses_ssl_block(cert_pair):
    certfile, keyfile = cert_pair
    runtime = RuntimeConfig.from_dict(
        {
            "server": {
                "host": "0.0.0.0",
                "port": 8107,
                "ssl": {
                    "certfile": certfile,
                    "keyfile": keyfile,
                    "cert_reqs": "required",
                },
            }
        }
    )
    assert WebServerConfig.from_runtime(runtime).port == 8107
    assert WebServerConfig.from_runtime(runtime).ssl.cert_reqs == "required"
    assert runtime.get("server.ssl.certfile") == certfile
