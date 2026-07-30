from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ._channel import XimeGrpcChannel

if TYPE_CHECKING:
    from xime.core.config.runtime import RuntimeConfig


class GrpcClientTlsConfig(BaseModel):
    """TLS for the outbound channel.

    Static mode (dynamic=false): credentials come from files; omitted files
    fall back to system CA roots (plain TLS to public endpoints).
    Chế độ tĩnh: đọc cert từ file; không khai file → dùng CA hệ thống.

        grpc:
          clients:
            trust:
              tls:
                enabled: true
                ca_file:   certs/ca.pem      # verify the server
                cert_file: certs/client.crt  # mTLS: present own certificate
                key_file:  certs/client.key

    Dynamic mode (dynamic=true): credentials come from the service's own
    GrpcCertificateProvider registered via configure_grpc_tls() - the same
    identity certificate used by the inbound servers. The channel re-checks
    provider.version() on every call and rebuilds itself when the certificate
    rotates; in-flight calls on the old channel finish gracefully.
    Chế độ động: cert lấy từ GrpcCertificateProvider của chính service
    (đăng ký qua configure_grpc_tls) - cùng cert định danh với server inbound.
    Channel so version mỗi call, cert rotate thì tự rebuild; call đang bay
    trên channel cũ chạy nốt.

        grpc:
          clients:
            trust:
              tls:
                enabled: true
                dynamic: true   # không cần khai file
    """

    enabled: bool = False
    dynamic: bool = False
    ca_file: str | None = None
    cert_file: str | None = None
    key_file: str | None = None
    # Which configure_grpc_tls(server_id=...) provider supplies the certificate
    # in dynamic mode. Defaults to the service's "default" provider; set this
    # only in multi-server setups where this client must use a non-default
    # identity. get_provider() still falls back to "default" if unregistered.
    # Provider cert (configure_grpc_tls) dùng cho dynamic, theo server_id; mặc
    # định "default", chỉ đổi khi multi-server cần định danh khác.
    server_id: str = "default"


class GrpcRetryConfig(BaseModel):
    """Automatic retry for UNARY calls (opt-in, off by default).

        grpc:
          clients:
            trust:
              retry:
                enabled: true
                max_attempts: 3              # total tries incl. the first
                initial_backoff_ms: 100
                max_backoff_ms: 2000
                backoff_multiplier: 2.0
                retryable_status: [UNAVAILABLE]   # gRPC StatusCode names

    Only unary calls are retried - a streaming request/response cannot be
    replayed safely once consumed. The per-attempt deadline still applies
    (each retry gets a fresh deadline_ms budget).

    UNAVAILABLE is the only retry-safe status by default: it usually means the
    request never reached the server. Adding others (e.g. for non-idempotent
    mutations) risks duplicate side effects - opt in deliberately.
    Chỉ retry call unary; stream không replay được. Mỗi lần thử có deadline
    riêng. Mặc định chỉ UNAVAILABLE (request thường chưa tới server); thêm status
    khác có thể gây tác dụng phụ trùng lặp - tự cân nhắc.
    """

    enabled: bool = False
    max_attempts: int = 3
    initial_backoff_ms: int = 100
    max_backoff_ms: int = 2000
    backoff_multiplier: float = 2.0
    retryable_status: list[str] = Field(default_factory=lambda: ["UNAVAILABLE"])


class GrpcClientConfig(BaseModel):
    """One target service, read from grpc.clients.<client_id> in application.yml.

        grpc:
          clients:
            trust:
              host: trust.internal
              port: 9090
              deadline_ms: 3000   # default per-call deadline; 0 disables
    """

    host: str = "localhost"
    port: int
    deadline_ms: int = 5000
    tls: GrpcClientTlsConfig = Field(default_factory=GrpcClientTlsConfig)
    retry: GrpcRetryConfig = Field(default_factory=GrpcRetryConfig)

    @classmethod
    def from_runtime(cls, runtime: RuntimeConfig, client_id: str) -> GrpcClientConfig:
        """Read grpc.clients.<client_id>; fail fast with a clear message when absent."""
        raw = runtime.get("grpc")
        clients = raw.get("clients") if isinstance(raw, dict) else None
        block = clients.get(client_id) if isinstance(clients, dict) else None
        if not isinstance(block, dict):
            raise RuntimeError(
                f"gRPC client '{client_id}' is registered via configure_grpc_clients() "
                f"but application.yml has no 'grpc.clients.{client_id}' block.\n"
                "Add at least:\n"
                f"  grpc:\n    clients:\n      {client_id}:\n        host: <host>\n        port: <port>"
            )
        return cls.model_validate(block)


class _GrpcClientsRegistry:
    """client_id → generated client classes, written by configure_grpc_clients()."""

    def __init__(self) -> None:
        self._clients: dict[str, list[type]] = {}

    def register(self, client_id: str, classes: tuple[type, ...]) -> None:
        self._clients.setdefault(client_id, []).extend(classes)

    def items(self) -> dict[str, list[type]]:
        return {cid: list(classes) for cid, classes in self._clients.items()}

    def reset(self) -> None:
        """Clear all registrations - test cleanup only."""
        self._clients.clear()


grpc_clients_registry = _GrpcClientsRegistry()


def configure_grpc_clients(client_id: str, *client_classes: type) -> None:
    """Register generated client classes to be built and injected by the framework.

    Call once per target service in your config layer (e.g. config/grpc.py).
    At startup the framework reads grpc.clients.<client_id> from application.yml,
    creates one managed XimeGrpcChannel for the target, instantiates each client
    class with it, and PRE-REGISTERS the instances in the DI container - any
    class can then receive them via plain constructor injection.
    Gọi một lần cho mỗi service đích trong config layer. Lúc startup framework
    đọc YAML grpc.clients.<client_id>, tạo XimeGrpcChannel, khởi tạo từng client
    class và PRE-REGISTER instance vào DI container - mọi class chỉ việc khai
    constructor injection như thường.

    Every call carries a default deadline and raises typed errors
    (RemoteCallError / RemoteCallTimeout / RemoteServiceUnavailable).
    Mọi call có deadline mặc định và lỗi typed.

    Example:
        from xime.adapters.grpc import configure_grpc_clients
        from clients.trust import KeyClient, CertClient

        configure_grpc_clients("trust", KeyClient, CertClient)
    """
    if not client_classes:
        raise ValueError(
            f"configure_grpc_clients('{client_id}'): pass at least one client class."
        )
    grpc_clients_registry.register(client_id, client_classes)


class GrpcClientChannels:
    """Holds every managed channel; closes them gracefully at shutdown.

    Pre-registered instances sit FIRST in the lifecycle list, so this
    pre_destroy runs LAST on stop - after user singletons finished their own
    teardown (which may still use the channels).
    Instance pre-register đứng ĐẦU danh sách lifecycle nên pre_destroy này chạy
    CUỐI lúc stop - sau khi singleton của user đã teardown xong.
    """

    def __init__(self, channels: list[XimeGrpcChannel]) -> None:
        self._channels = channels

    @property
    def channels(self) -> list[XimeGrpcChannel]:
        return list(self._channels)

    async def pre_destroy(self) -> None:
        for channel in self._channels:
            await channel.close()


def build_client_instances(runtime: RuntimeConfig) -> dict[type, object]:
    """Build channels + client instances for every registered client_id.

    Called by StartupOrchestrator before the DI container is built; the result
    is fed to container.register_instance() so user classes can depend on the
    client types.
    Được StartupOrchestrator gọi trước khi build container; kết quả đưa vào
    register_instance() để class của user phụ thuộc được vào các client type.
    """
    instances: dict[type, object] = {}
    channels: list[XimeGrpcChannel] = []

    for client_id, classes in grpc_clients_registry.items().items():
        config = GrpcClientConfig.from_runtime(runtime, client_id)
        channel = XimeGrpcChannel(client_id, config)
        channels.append(channel)
        for cls in classes:
            if cls in instances:
                raise RuntimeError(
                    f"gRPC client class '{cls.__name__}' is registered for more "
                    "than one client_id - each class may belong to only one target."
                )
            instances[cls] = cls(channel)

    if channels:
        instances[GrpcClientChannels] = GrpcClientChannels(channels)
    return instances


def wire_dynamic_certificates(resolver) -> None:
    """Attach the registered certificate provider to dynamic-TLS channels.

    Called by StartupOrchestrator AFTER the DI container is built (the provider
    is an ordinary DI singleton) but BEFORE lifecycle hooks run. Wiring only -
    no certificate is read here: the provider's resolver may be populated later
    by a PostConstruct bootstrap; the channel reads it lazily on first call.
    Được orchestrator gọi SAU khi build container (provider là singleton DI)
    nhưng TRƯỚC lifecycle. Chỉ nối dây - không đọc cert ở đây: resolver của
    provider có thể được PostConstruct bootstrap nạp sau; channel đọc lười.

    Fails fast when tls.dynamic is on but no provider is registered or the
    provider class is missing from DI.
    """
    from xime.adapters.grpc.tls._config import grpc_tls_registry

    try:
        holder = resolver(GrpcClientChannels)
    except KeyError:
        return  # no clients built — nothing to wire

    dynamic_channels = [
        ch for ch in holder.channels
        if ch._config.tls.enabled and ch._config.tls.dynamic
    ]
    if not dynamic_channels:
        return

    # Resolve a provider per channel by its configured server_id. Multiple
    # channels sharing a provider class resolve it once (DI singleton anyway).
    # Tra provider theo server_id của từng channel; cùng class thì resolve 1 lần.
    resolved: dict[type, object] = {}
    for channel in dynamic_channels:
        server_id = channel._config.tls.server_id
        provider_class = grpc_tls_registry.get_provider(server_id)
        if provider_class is None:
            raise RuntimeError(
                f"gRPC client '{channel.client_id}' enables tls.dynamic with "
                f"server_id='{server_id}' but no certificate provider is "
                f"registered for it. Call configure_grpc_tls(provider=..., "
                f"server_id='{server_id}') in config/grpc.py."
            )
        if provider_class not in resolved:
            try:
                resolved[provider_class] = resolver(provider_class)
            except KeyError:
                raise RuntimeError(
                    f"Certificate provider '{provider_class.__name__}' "
                    "(configure_grpc_tls) is not in the DI container. Add its "
                    "package to dependency.scan() or dependency.register() in "
                    "config/dependency.py."
                ) from None
        channel.attach_certificate_provider(resolved[provider_class])
