"""Reload failures must remain failures through worker ACKs and management HTTP."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from xime.adapters.web import TlsReloadResult, TlsWorkerResult, WebAdapter, reload_tls
from xime.adapters.web._management import ManagementWebAdapter
from xime.adapters.web._tls_reload import _decode_worker_result, _encode_worker_result
from xime.core.bootstrap._processes import EndpointSpec, ProcessBlock, ProcessTopology
from xime.core.config.runtime import RuntimeConfig


def _worker(index: int, outcome: str) -> TlsWorkerResult:
    return TlsWorkerResult(
        index,
        outcome,
        certificate_fingerprint="a" * 64 if outcome != "failed" else None,
        detail="SSLError" if outcome == "failed" else None,
    )


def _topology(count: int = 1) -> ProcessTopology:
    spec = EndpointSpec("web", "default", "127.0.0.1", 0, None, False, {})
    return ProcessTopology(
        blocks=tuple(
            ProcessBlock(f"worker-{index}", index == 0, {spec.key: spec}) for index in range(count)
        )
    )


def _app(topology: ProcessTopology | None, cluster=None, adapters=()):
    runtime = RuntimeConfig.from_dict(
        {
            "webserver": {
                "ssl": {"reload": {"mode": "api"}},
                "management": {"enabled": True, "port": 9180},
            }
        }
    )
    return SimpleNamespace(
        _topology=topology,
        _cluster=cluster,
        _adapters=list(adapters),
        get=lambda _config_type: runtime,
    )


async def _post_reload(app, server_id: str = "default"):
    transport = ASGITransport(app=ManagementWebAdapter().build_app(app))
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        return await client.post("/tls/reload", json={"server_id": server_id})


@pytest.mark.parametrize(
    ("outcome", "workers", "missing", "succeeded"),
    [
        ("failed", (), (), False),
        ("reloaded", (), (), False),
        ("unchanged", (), (), False),
        ("failed", (_worker(0, "reloaded"),), (), False),
        ("partial", (_worker(0, "reloaded"),), (), False),
        ("timeout", (_worker(0, "unchanged"),), (), False),
        ("reloaded", (_worker(0, "reloaded"),), (1,), False),
        ("reloaded", (_worker(0, "reloaded"), _worker(1, "failed")), (), False),
        ("reloaded", (_worker(0, "reloaded"), _worker(1, "unchanged")), (), True),
        ("unchanged", (_worker(0, "unchanged"),), (), True),
    ],
)
def test_success_requires_completed_nonempty_worker_results(
    outcome, workers, missing, succeeded
) -> None:
    assert TlsReloadResult("default", outcome, workers, missing).succeeded is succeeded


@pytest.mark.anyio
@pytest.mark.parametrize("started", [False, True], ids=["before-start", "unknown-listener"])
async def test_missing_listener_is_a_failure_for_python_and_http(started: bool) -> None:
    app = _app(_topology() if started else None)
    server_id = "unknown" if started else "default"

    result = await reload_tls(app, server_id)
    assert result.outcome == "failed"
    assert not result.succeeded

    response = await _post_reload(app, server_id)
    assert response.status_code == 503
    assert response.json() == result.as_dict()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("has_manager", "active", "worker_outcome", "expected_status", "expected_outcome"),
    [
        (False, False, "reloaded", 503, "failed"),
        (True, False, "reloaded", 503, "failed"),
        (True, True, "failed", 503, "failed"),
        (True, True, "reloaded", 200, "reloaded"),
        (True, True, "unchanged", 200, "unchanged"),
    ],
    ids=["http-only", "stopped-tls", "invalid-certificate", "reloaded", "unchanged"],
)
async def test_management_preserves_local_listener_outcome(
    has_manager, active, worker_outcome, expected_status, expected_outcome
) -> None:
    adapter = WebAdapter()
    reload_call = AsyncMock(return_value=_worker(0, worker_outcome))
    adapter._tls_reloader = SimpleNamespace(reload=reload_call) if has_manager else None
    adapter._tls_listener_active = active
    app = _app(_topology(), adapters=(adapter,))

    response = await _post_reload(app)

    assert response.status_code == expected_status
    assert response.json()["outcome"] == expected_outcome
    assert adapter._tls_listener_active is active
    if has_manager and active:
        reload_call.assert_awaited_once()
    else:
        reload_call.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("worker_outcomes", "missing", "expected_status", "expected_outcome"),
    [
        ({0: "reloaded", 1: "reloaded"}, (), 200, "reloaded"),
        ({0: "unchanged", 1: "unchanged"}, (), 200, "unchanged"),
        ({0: "reloaded", 1: "unchanged"}, (), 200, "reloaded"),
        ({0: "failed", 1: "failed"}, (), 503, "failed"),
        ({0: "reloaded", 1: "failed"}, (), 503, "partial"),
        ({0: "reloaded"}, (1,), 503, "partial"),
        ({}, (0, 1), 504, "timeout"),
        ({}, (), 503, "failed"),
    ],
    ids=[
        "all-reloaded",
        "all-unchanged",
        "mixed-success",
        "all-failed",
        "partial-failure",
        "missing-ack",
        "timeout",
        "empty-response",
    ],
)
async def test_management_preserves_cluster_outcome(
    worker_outcomes, missing, expected_status, expected_outcome
) -> None:
    acknowledgements = {
        index: _encode_worker_result(_worker(index, outcome))
        for index, outcome in worker_outcomes.items()
    }
    request = AsyncMock(return_value=(acknowledgements, missing))
    cluster = SimpleNamespace(clustered=True, request_adapter_command=request)
    app = _app(_topology(2), cluster=cluster)

    response = await _post_reload(app)

    assert response.status_code == expected_status
    body = response.json()
    assert body["outcome"] == expected_outcome
    assert body["missing_workers"] == list(missing)
    assert {worker["worker_index"] for worker in body["workers"]} == set(worker_outcomes)
    request.assert_awaited_once()
    assert request.await_args.kwargs["targets"] == (0, 1)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\x01\x00",
        b"\x01\x00\x05",
        b"\x01\x02a",
        b"\x01\x00\x00extra",
        b"\x01\x01\xff\x00",
        b"\x01\x00\x01\xff",
        b"\x09\x00\x00",
    ],
    ids=[
        "empty",
        "no-detail-length",
        "truncated-detail",
        "truncated-fingerprint",
        "trailing-bytes",
        "non-ascii-fingerprint",
        "non-ascii-detail",
        "unknown-status",
    ],
)
def test_malformed_worker_ack_is_never_successful(payload: bytes) -> None:
    result = _decode_worker_result(1, payload)
    assert result.outcome == "failed"
    assert result.detail == "InvalidAcknowledgement"
    assert not TlsReloadResult("default", "reloaded", (result,)).succeeded


@pytest.mark.parametrize("outcome", ["reloaded", "unchanged", "failed"])
def test_valid_worker_ack_retains_its_result(outcome: str) -> None:
    result = _worker(1, outcome)
    assert _decode_worker_result(1, _encode_worker_result(result)) == result


@pytest.mark.anyio
async def test_management_rejects_truncated_success_ack() -> None:
    cluster = SimpleNamespace(
        clustered=True,
        request_adapter_command=AsyncMock(return_value=({0: b"\x01\x00\x05"}, ())),
    )

    response = await _post_reload(_app(_topology(), cluster=cluster))

    assert response.status_code == 503
    assert response.json()["outcome"] == "failed"
    assert response.json()["workers"][0]["detail"] == "InvalidAcknowledgement"
