from __future__ import annotations


class _GrpcTlsRegistry:
    """Holds certificate provider classes registered via configure_grpc_tls().

    Keyed by server_id. A provider registered under "default" applies to ALL
    gRPC servers of the application unless a server_id-specific registration
    overrides it (e.g. a public server using a public-CA provider while
    internal servers use the Trust-issued certificate).
    Khóa theo server_id. Provider đăng ký dưới "default" áp dụng cho MỌI server
    gRPC trừ khi có đăng ký riêng theo server_id override (vd server public
    dùng cert public CA, server internal dùng cert do Trust cấp).
    """

    def __init__(self) -> None:
        self._providers: dict[str, type] = {}

    def set_provider(self, provider: type, server_id: str = "default") -> None:
        self._providers[server_id] = provider

    def get_provider(self, server_id: str) -> type | None:
        # Per-server registration wins; "default" acts as the catch-all.
        # Đăng ký theo server cụ thể thắng; "default" là fallback chung.
        specific = self._providers.get(server_id)
        if specific is not None:
            return specific
        return self._providers.get("default")

    def reset(self) -> None:
        """Clear all registrations - test cleanup only.

        Xóa toàn bộ đăng ký - chỉ dùng dọn dẹp trong test.
        """
        self._providers.clear()


grpc_tls_registry = _GrpcTlsRegistry()


def configure_grpc_tls(provider: type, server_id: str = "default") -> None:
    """Register a dynamic certificate provider for gRPC server TLS/mTLS.

    Call once in your config layer (e.g. config/grpc.py). Whether TLS is on
    at all stays an operator decision in application.yml (grpc.tls.enabled /
    grpc.servers.<id>.tls.enabled); this call decides WHERE certificates come
    from when it is on.
    Gọi một lần trong config layer (vd config/grpc.py). Bật/tắt TLS vẫn là
    quyết định của operator trong application.yml; hàm này quyết định cert
    TỪ ĐÂU RA khi TLS bật.

    With a provider registered, the adapter serves with dynamic credentials:
    every new TLS handshake re-reads the provider, so certificate rotation
    needs no restart and never interrupts established sessions.
    Có provider, adapter dùng dynamic credentials: mỗi handshake mới đọc lại
    provider, rotate cert không cần restart và không cắt phiên đang mở.

    Without a provider, TLS falls back to static files (grpc.tls.cert_file/
    key_file/ca_file in application.yml).
    Không có provider, TLS fallback về đọc file tĩnh trong application.yml.

    The provider argument is a CLASS, resolved from the DI container at
    adapter startup - add it to dependency.scan()/register() packages.
    Tham số provider là CLASS, được resolve từ DI container lúc adapter start.

    Example:
        from xime.adapters.grpc import configure_grpc_tls

        configure_grpc_tls(provider=TrustGrpcCertificateProvider)
        configure_grpc_tls(provider=PublicCaProvider, server_id="public")
    """
    grpc_tls_registry.set_provider(provider, server_id)
