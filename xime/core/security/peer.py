from __future__ import annotations

from xime.core.context import request_context

# Neutral request_context key under which adapters store the verified peer
# identity (e.g. the CN of a client certificate over mTLS). Kept transport- and
# semantics-neutral on purpose: the value may be a service id OR an application
# identity (owner_app_identity_id) — business code decides how to interpret it.
# Key trung tính lưu danh tính peer đã verify (vd CN client cert qua mTLS). Cố ý
# không gắn cứng ngữ nghĩa: giá trị có thể là service id HOẶC định danh ứng dụng.
PEER_CN = "peer_cn"


def current_caller() -> str | None:
    """Return the verified peer identity of the current request, or None.

    This is the raw Common Name extracted from a verified client certificate
    (mTLS). It is None when the request did not arrive over mTLS, or when the
    transport cannot supply a peer identity.
    Trả CN thô lấy từ client cert đã verify (mTLS). None khi request không qua
    mTLS hoặc transport không cấp được danh tính peer.

    The framework only provides the mechanism (who called). Authorization — what
    that caller is allowed to do — stays in the application.
    Framework chỉ cấp cơ chế (ai gọi). Authorization vẫn nằm ở ứng dụng.

    Currently populated by the gRPC RequestContextInterceptor. Other transports
    may populate the same PEER_CN key as they gain peer-identity support.
    Hiện được set bởi RequestContextInterceptor của gRPC.
    """
    return request_context.get(PEER_CN)
