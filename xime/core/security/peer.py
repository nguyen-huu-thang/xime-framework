from __future__ import annotations

from xime.core.context import request_context

# Neutral request_context key under which adapters store the verified peer
# identity (e.g. the CN of a client certificate over mTLS). Kept transport- and
# semantics-neutral on purpose: the value may be a service id OR an application
# identity (owner_app_identity_id) — business code decides how to interpret it.
# Key trung tính lưu danh tính peer đã verify (vd CN client cert qua mTLS). Cố ý
# không gắn cứng ngữ nghĩa: giá trị có thể là service id HOẶC định danh ứng dụng.
PEER_CN = "peer_cn"

# Neutral request_context key under which adapters store the identity of the
# APPLICATION that owns the calling process, when the peer certificate carries
# one. A single application may run many processes: each process gets its own
# certificate (its own CN), but they all share one application identity, so this
# key answers "which application called", while PEER_CN answers "which process".
# Key trung tính lưu định danh APPLICATION sở hữu tiến trình gọi, khi cert peer
# có mang. Một app có nhiều tiến trình: mỗi tiến trình một cert (CN riêng) nhưng
# chung một định danh app - key này trả lời "app nào gọi", PEER_CN trả lời
# "tiến trình nào gọi".
PEER_APP_ID = "peer_app_id"


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


def current_app_id() -> str | None:
    """Return the identity of the application that owns the caller, or None.

    This is the raw value carried by the peer certificate as a URI Subject
    Alternative Name of the form `xime-app://<identity>`, with the scheme
    stripped. It is None when the request did not arrive over mTLS, when the
    certificate belongs to a process that is not part of an application (e.g. a
    platform service), or when the transport cannot supply a peer identity.
    Giá trị thô cert peer mang trong SAN URI dạng `xime-app://<identity>`, đã cắt
    scheme. None khi request không qua mTLS, khi cert thuộc tiến trình không nằm
    trong app nào (vd service nền tảng), hoặc transport không cấp được.

    Extraction is fail-soft: a malformed or unreadable certificate yields None
    rather than an error, exactly like current_caller(). The framework only
    supplies the raw fact; deciding whether an application exists and what it may
    do stays in the application.
    Trích xuất fail-soft: cert dị dạng hoặc không đọc được trả None chứ không nổ,
    y như current_caller(). Framework chỉ cấp sự thật thô; việc app đó có tồn tại
    không và được làm gì vẫn thuộc ứng dụng.

    Currently populated by the gRPC RequestContextInterceptor, alongside PEER_CN.
    Hiện được set bởi RequestContextInterceptor của gRPC, cạnh PEER_CN.
    """
    return request_context.get(PEER_APP_ID)
