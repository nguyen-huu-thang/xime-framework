from __future__ import annotations

import asyncio
import datetime
import os
import socket
import ssl
from pathlib import Path
from types import SimpleNamespace

import pytest
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from xime.adapters.web import ServerTlsConfig, WebAdapter, reload_tls
from xime.adapters.web._tls_reload import TlsContextReloader
from xime.core.bootstrap._processes import EndpointSpec, ProcessBlock, ProcessTopology
from xime.core.bootstrap._slot import AdapterSlot
from xime.core.config.runtime import RuntimeConfig


def _write_pair(directory: Path, stem: str, cert: x509.Certificate, key) -> tuple[Path, Path]:
    cert_path = directory / f"{stem}-cert.pem"
    key_path = directory / f"{stem}-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


@pytest.fixture(params=["rsa", "ecdsa"])
def certificate_set(tmp_path: Path, request: pytest.FixtureRequest):
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Xime Test CA")])
    now = datetime.datetime.now(datetime.UTC)
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_path = tmp_path / "ca.pem"
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))

    pairs = {}
    for label in ("a", "b", "c"):
        key = (
            rsa.generate_private_key(public_exponent=65537, key_size=2048)
            if request.param == "rsa"
            else ec.generate_private_key(ec.SECP256R1())
        )
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(ca.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                False,
            )
            .add_extension(
                x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        pairs[label] = _write_pair(tmp_path, label, cert, key)
    return tmp_path, ca_path, pairs


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _asgi(_scope, _receive, send) -> None:
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b""})


async def _request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    writer.write(b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: keep-alive\r\n\r\n")
    await writer.drain()
    response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=3)
    assert response.startswith(b"HTTP/1.1 204")


def _serial(writer: asyncio.StreamWriter) -> int:
    der = writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
    return x509.load_der_x509_certificate(der).serial_number


@pytest.mark.anyio
@pytest.mark.parametrize("tls_version", [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3])
@pytest.mark.parametrize("cipher_policy", [None, "ECDHE+AESGCM"])
async def test_reload_is_atomic_deduplicated_and_preserves_existing_connection(
    certificate_set, tls_version, cipher_policy,
) -> None:
    directory, ca_path, pairs = certificate_set
    active_cert, active_key = directory / "active-cert.pem", directory / "active-key.pem"
    active_cert.write_bytes(pairs["a"][0].read_bytes())
    active_key.write_bytes(pairs["a"][1].read_bytes())
    cert_a = x509.load_pem_x509_certificate(active_cert.read_bytes())
    cert_b_path, key_b_path = pairs["b"]
    cert_b = x509.load_pem_x509_certificate(cert_b_path.read_bytes())
    cert_c_path, key_c_path = pairs["c"]
    cert_c = x509.load_pem_x509_certificate(cert_c_path.read_bytes())

    reloader = TlsContextReloader(
        ServerTlsConfig(
            certfile=str(active_cert),
            keyfile=str(active_key),
            ciphers=cipher_policy,
        ),
        "default",
    )
    config = uvicorn.Config(
        _asgi,
        host="127.0.0.1",
        port=_free_port(),
        lifespan="off",
        access_log=False,
        ssl_certfile=str(active_cert),
        ssl_keyfile=str(active_key),
        ssl_context_factory=reloader.ssl_context_factory,
        **({"ssl_ciphers": cipher_policy} if cipher_policy is not None else {}),
    )
    config.load()
    server = uvicorn.Server(config)
    server.lifespan = config.lifespan_class(config)
    await server.startup(sockets=None)
    serving = asyncio.create_task(server.main_loop())

    client_context = ssl.create_default_context(cafile=str(ca_path))
    client_context.minimum_version = client_context.maximum_version = tls_version
    if cipher_policy is not None:
        client_context.set_ciphers(cipher_policy)
    host, port = "127.0.0.1", config.port
    writer_a = None
    try:
        reader_a, writer_a = await asyncio.open_connection(
            host, port, ssl=client_context, server_hostname="localhost"
        )
        assert _serial(writer_a) == cert_a.serial_number
        await _request(reader_a, writer_a)

        stat = active_cert.stat()
        os.utime(active_cert, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
        metadata_only = await reloader.reload()
        assert metadata_only.outcome == "unchanged"

        active_cert.write_bytes(cert_b_path.read_bytes())
        active_key.write_bytes(key_b_path.read_bytes())
        results = await asyncio.gather(reloader.reload(), reloader.reload())
        assert sorted(result.outcome for result in results) == ["reloaded", "unchanged"]

        # The existing TLS connection retains A while a new handshake sees B.
        await _request(reader_a, writer_a)
        reader_b, writer_b = await asyncio.open_connection(
            host, port, ssl=client_context, server_hostname="localhost"
        )
        try:
            assert _serial(writer_b) == cert_b.serial_number
            await _request(reader_b, writer_b)
        finally:
            writer_b.close()
            await writer_b.wait_closed()

        no_sni_context = ssl.create_default_context(cafile=str(ca_path))
        no_sni_context.check_hostname = False
        no_sni_context.minimum_version = no_sni_context.maximum_version = tls_version
        reader_no_sni, writer_no_sni = await asyncio.open_connection(
            host, port, ssl=no_sni_context, server_hostname=None
        )
        try:
            assert _serial(writer_no_sni) == cert_b.serial_number
            await _request(reader_no_sni, writer_no_sni)
        finally:
            writer_no_sni.close()
            await writer_no_sni.wait_closed()

        # A mismatched pair cannot replace B; retrying with a valid C pair works.
        active_cert.write_bytes(cert_c_path.read_bytes())
        failed = await reloader.reload()
        assert failed.outcome == "failed"
        reader_old, writer_old = await asyncio.open_connection(
            host, port, ssl=client_context, server_hostname="localhost"
        )
        try:
            assert _serial(writer_old) == cert_b.serial_number
            await _request(reader_old, writer_old)
        finally:
            writer_old.close()
            await writer_old.wait_closed()
        active_key.write_bytes(key_c_path.read_bytes())
        changed = await reloader.reload()
        assert changed.outcome == "reloaded"
        assert changed.certificate_fingerprint is not None

        reader_c, writer_c = await asyncio.open_connection(
            host, port, ssl=client_context, server_hostname="localhost"
        )
        try:
            assert _serial(writer_c) == cert_c.serial_number
            await _request(reader_c, writer_c)
        finally:
            writer_c.close()
            await writer_c.wait_closed()
        with pytest.raises(ssl.SSLCertVerificationError):
            await asyncio.open_connection(
                host, port, ssl=client_context, server_hostname="wrong.invalid"
            )
        wrong_ca = ssl.create_default_context()
        wrong_ca.minimum_version = wrong_ca.maximum_version = tls_version
        with pytest.raises(ssl.SSLCertVerificationError):
            await asyncio.open_connection(host, port, ssl=wrong_ca, server_hostname="localhost")
    finally:
        if writer_a is not None:
            writer_a.close()
            await writer_a.wait_closed()
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=5)
        if server.started:
            await server.shutdown(sockets=None)


def _client_identity(directory: Path, label: str):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, label)])
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"{label} CA")])
    now = datetime.datetime.now(datetime.UTC)
    ca = (
        x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
        .add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=False, decipher_only=False,
        ), True)
        .sign(key, hashes.SHA256())
    )
    ca_path = directory / f"{label}-ca.pem"
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    client_key = ec.generate_private_key(ec.SECP256R1())
    client = (
        x509.CertificateBuilder().subject_name(name).issuer_name(ca_name)
        .public_key(client_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]), False)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = _write_pair(directory, label, client, client_key)
    return ca_path, cert_path, key_path


@pytest.mark.anyio
@pytest.mark.parametrize("tls_version", [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3])
async def test_mtls_ca_rotation_accepts_only_the_current_client_ca(certificate_set, tls_version):
    directory, server_ca, pairs = certificate_set
    identities = {name: _client_identity(directory, name) for name in ("client-a", "client-b")}
    active_ca = directory / "active-client-ca.pem"
    active_ca.write_bytes(identities["client-a"][0].read_bytes())
    cert, key = pairs["a"]
    tls = ServerTlsConfig(
        certfile=str(cert), keyfile=str(key), ca_certs=str(active_ca), cert_reqs="required",
    )
    reloader = TlsContextReloader(tls, "default")
    config = uvicorn.Config(
        _asgi, host="127.0.0.1", port=0, lifespan="off", access_log=False,
        ssl_certfile=str(cert), ssl_keyfile=str(key), ssl_ca_certs=str(active_ca),
        ssl_cert_reqs=ssl.CERT_REQUIRED, ssl_context_factory=reloader.ssl_context_factory,
    )
    config.load()
    server = uvicorn.Server(config)
    server.lifespan = config.lifespan_class(config)
    await server.startup()
    port = server.servers[0].sockets[0].getsockname()[1]
    serving = asyncio.create_task(server.main_loop())

    async def accepted(identity):
        context = ssl.create_default_context(cafile=str(server_ca))
        context.minimum_version = context.maximum_version = tls_version
        if identity is not None:
            _, client_cert, client_key = identities[identity]
            context.load_cert_chain(client_cert, client_key)
        writer = None
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(
                "127.0.0.1", port, ssl=context, server_hostname="localhost",
            ), timeout=3)
            await _request(reader, writer)
            return True
        except (OSError, asyncio.IncompleteReadError, TimeoutError):
            return False
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass

    try:
        for current in ("client-a", "client-b"):
            if current == "client-b":
                active_ca.write_bytes(identities[current][0].read_bytes())
                assert (await reloader.reload()).outcome == "reloaded"
            for identity in ("client-a", "client-b", None):
                assert await accepted(identity) is (identity == current)
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=5)
        await server.shutdown()


@pytest.mark.anyio
async def test_web_adapter_watcher_reloads_without_an_external_hook(certificate_set) -> None:
    directory, ca_path, pairs = certificate_set
    active_cert, active_key = directory / "watch-cert.pem", directory / "watch-key.pem"
    active_cert.write_bytes(pairs["a"][0].read_bytes())
    active_key.write_bytes(pairs["a"][1].read_bytes())
    serial_b = x509.load_pem_x509_certificate(pairs["b"][0].read_bytes()).serial_number
    port = _free_port()
    runtime = RuntimeConfig.from_dict(
        {
            "webserver": {
                "ssl": {
                    "certfile": str(active_cert),
                    "keyfile": str(active_key),
                    "ciphers": "ECDHE+AESGCM",
                    "reload": {"mode": "watch", "interval_seconds": 1},
                }
            }
        }
    )

    class _App:
        @staticmethod
        def get(_target):
            return runtime

    class _ProbeWebAdapter(WebAdapter):
        def build_app(self, _xime_app: _App):
            return _asgi

    adapter = _ProbeWebAdapter()
    adapter.assign_slot(
        AdapterSlot(
            process_id="main",
            primary=True,
            spec=EndpointSpec(
                kind="web",
                adapter_id="default",
                host="127.0.0.1",
                port=port,
                path=None,
                shared=False,
                options={},
            ),
        )
    )
    client_context = ssl.create_default_context(cafile=str(ca_path))
    client_context.set_ciphers("ECDHE+AESGCM")
    await adapter.start(_App())  # type: ignore[arg-type]
    serving = asyncio.create_task(adapter.serve())
    direct_app = None
    try:
        active_reader, active_writer = await asyncio.open_connection(
            "127.0.0.1", port, ssl=client_context, server_hostname="localhost"
        )
        try:
            await _request(active_reader, active_writer)
        finally:
            active_writer.close()
            await active_writer.wait_closed()

        active_cert.write_bytes(pairs["b"][0].read_bytes())
        active_key.write_bytes(pairs["b"][1].read_bytes())
        deadline = asyncio.get_running_loop().time() + 8
        observed: int | None = None
        while asyncio.get_running_loop().time() < deadline:
            try:
                reader, writer = await asyncio.open_connection(
                    "127.0.0.1", port, ssl=client_context, server_hostname="localhost"
                )
                try:
                    observed = _serial(writer)
                    await _request(reader, writer)
                finally:
                    writer.close()
                    await writer.wait_closed()
            except (OSError, ssl.SSLError):
                pass
            if observed == serial_b:
                break
            await asyncio.sleep(0.2)
        assert observed == serial_b, "the local watcher did not apply the new certificate"

        topology = ProcessTopology(
            blocks=(
                ProcessBlock(
                    process_id="main",
                    primary=True,
                    endpoints={("web", "default"): adapter._slot.spec},
                ),
            )
        )
        direct_app = SimpleNamespace(
            _adapters=[adapter],
            _cluster=SimpleNamespace(clustered=False, index=0),
            _topology=topology,
        )
        direct = await reload_tls(direct_app)  # type: ignore[arg-type]
        assert direct.outcome == "unchanged"
        assert direct.succeeded
    finally:
        await adapter.stop()
        await asyncio.wait_for(serving, timeout=5)
    assert direct_app is not None
    after_stop = await reload_tls(direct_app)  # type: ignore[arg-type]
    assert after_stop.outcome == "failed"


@pytest.mark.anyio
async def test_watcher_uses_bounded_early_retry_backoff(monkeypatch) -> None:
    adapter = WebAdapter()
    adapter._server = SimpleNamespace(should_exit=False)
    delays: list[int] = []

    class _Reloader:
        calls = 0

        async def reload(self):
            self.calls += 1
            if self.calls == 4:
                adapter._server.should_exit = True
                return SimpleNamespace(outcome="reloaded")
            return SimpleNamespace(outcome="failed")

    reloader = _Reloader()
    adapter._tls_reloader = reloader  # type: ignore[assignment]

    async def _sleep(delay: int) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _sleep)
    await adapter._watch_tls(300)

    assert reloader.calls == 4
    assert delays == [300, 5, 10, 30]
