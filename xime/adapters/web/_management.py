"""Private loopback management listener built on the web adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from xime.core.bootstrap._internal_adapters import (
    InternalAdapterContribution,
    register_internal_adapter_provider,
)
from xime.core.bootstrap.adapter import SCALING_SINGLETON
from xime.core.bootstrap.application import Application
from xime.core.config.runtime import RuntimeConfig

from ._adapter import WebAdapter
from ._health import add_management_health_routes
from ._server_config import WebServerConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xime.core.bootstrap.adapter import Adapter


MANAGEMENT_ADAPTER_ID = "xime_management"


class _TlsReloadRequest(BaseModel):
    server_id: str = Field(default="default", min_length=1, max_length=64)


class ManagementWebAdapter(WebAdapter, scaling=SCALING_SINGLETON):
    """Framework-owned FastAPI listener. It is never registered by app code."""

    _xime_internal = True

    def __init__(self) -> None:
        super().__init__(MANAGEMENT_ADAPTER_ID)

    def build_app(self, xime_app: Application):
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        from ._tls_reload import reload_tls

        fastapi_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        add_management_health_routes(fastapi_app, xime_app)
        runtime = xime_app.get(RuntimeConfig)
        config = WebServerConfig.from_runtime(runtime)
        if config.ssl.reload.mode in {"api", "both"}:
            @fastapi_app.post("/tls/reload", include_in_schema=False)
            async def _reload_tls(request: _TlsReloadRequest):
                result = await reload_tls(xime_app, request.server_id)
                if result.succeeded:
                    return JSONResponse(result.as_dict(), status_code=200)
                status_code = 504 if result.outcome == "timeout" else 503
                return JSONResponse(result.as_dict(), status_code=status_code)

        return fastapi_app


def _management_provider(
    runtime: RuntimeConfig, _adapters: tuple[Adapter, ...]
) -> Iterable[InternalAdapterContribution]:
    config = WebServerConfig.from_runtime(runtime)
    management = config.management
    if not management.enabled:
        return ()
    return (
        InternalAdapterContribution(
            adapter=ManagementWebAdapter(),
            host=management.host,
            port=management.port,
            # An empty TLS cell is explicit: the loopback listener is plain HTTP
            # and never inherits the browser-facing certificate.
            options={"ssl": {}},
            where="webserver.management",
        ),
    )


register_internal_adapter_provider(_management_provider)

__all__ = ["MANAGEMENT_ADAPTER_ID"]
