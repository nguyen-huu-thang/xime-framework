from __future__ import annotations

from xime.core.context import request_context

# Neutral request_context key under which adapters store the verified peer
# identity (e.g. the CN of a client certificate over mTLS). Kept transport- and
# semantics-neutral on purpose: whatever a deployment puts in the CN is what
# arrives here - business code decides how to interpret it.
# Key trung tính lưu danh tính peer đã verify (vd CN client cert qua mTLS). Cố ý
# không gắn cứng ngữ nghĩa: nơi triển khai đặt gì vào CN thì ở đây nhận đúng thứ
# đó, code nghiệp vụ tự diễn giải.
PEER_CN = "peer_cn"

# Neutral request_context key under which adapters store every Subject
# Alternative Name of the peer certificate, exactly as the transport reported
# them. SANs are where deployments carry workload identity (SPIFFE IDs and other
# URI schemes), alongside plain DNS names and IP addresses - and the transport
# does not tag which entry is which, so this key carries all of them, raw and
# uninterpreted. The framework does not know or care what any entry means.
# Key trung tính lưu MỌI SAN của cert peer, đúng như transport thuật lại. SAN là
# chỗ các nơi triển khai chở định danh workload (SPIFFE ID và các scheme URI
# khác), lẫn cùng tên DNS và địa chỉ IP - và transport không gắn nhãn entry nào
# là loại gì, nên key này chở hết, thô và không diễn giải. Framework không biết
# và không cần biết entry nào nghĩa là gì.
PEER_SANS = "peer_sans"


def current_caller() -> str | None:
    """Return the verified peer identity of the current request, or None.

    This is the raw Common Name extracted from a verified client certificate
    (mTLS). It is None when the request did not arrive over mTLS, or when the
    transport cannot supply a peer identity.
    Trả CN thô lấy từ client cert đã verify (mTLS). None khi request không qua
    mTLS hoặc transport không cấp được danh tính peer.

    The framework only provides the mechanism (who called). Authorization - what
    that caller is allowed to do - stays in the application.
    Framework chỉ cấp cơ chế (ai gọi). Authorization vẫn nằm ở ứng dụng.

    Currently populated by the gRPC RequestContextInterceptor. Other transports
    may populate the same PEER_CN key as they gain peer-identity support.
    Hiện được set bởi RequestContextInterceptor của gRPC.
    """
    return request_context.get(PEER_CN)


def current_peer_sans() -> tuple[str, ...] | None:
    """Return every Subject Alternative Name of the peer certificate, or None.

    The tuple holds the SAN entries exactly as the transport reported them, in
    the order it supplied. gRPC hands SANs over as a FLAT, UNTAGGED list, so URI
    entries (SPIFFE IDs and any other scheme), DNS names and IP addresses arrive
    mixed together with nothing marking which is which. Matching the entry you
    care about is therefore yours to do:
    Tuple chứa các entry SAN đúng như transport thuật lại, theo thứ tự nó đưa.
    gRPC trả SAN dạng danh sách PHẲNG, KHÔNG GẮN NHÃN, nên URI (SPIFFE ID hay
    scheme nào khác), tên DNS và địa chỉ IP lẫn vào nhau. Việc khớp entry mình
    cần là việc của bạn:

        LABEL, SCHEME = "URI:", "spiffe://"
        for entry in current_peer_sans() or ():
            # Some tooling prefixes the entry with its SAN type; drop that first.
            # Một số công cụ thêm tiền tố loại SAN vào đầu entry; cắt nó trước.
            value = entry.removeprefix(LABEL)
            if value.startswith(SCHEME):        # anchor at the START
                workload_id = value
                break

    ⚠ Anchor the match at the start (`startswith`) - do NOT search anywhere in
    the entry (`find`/`in`). A SAN entry such as
    `https://example.com/?redirect=spiffe://attacker` contains your scheme
    without being an identity of that scheme, and a substring search would
    happily accept it.
    ⚠ Khớp phải NEO ĐẦU chuỗi (`startswith`), **đừng** tìm ở giữa (`find`/`in`):
    một entry như `https://example.com/?redirect=spiffe://attacker` có chứa
    scheme của bạn mà không phải định danh thuộc scheme đó, và phép tìm chuỗi con
    sẽ nhận nó.

    Returns None when the certificate supplied no SANs, when the request did not
    arrive over mTLS, or when the transport cannot report them. An absent value
    means "nothing was reported", never "reported as empty" - and whether the
    call arrived over mTLS at all is answered by current_caller().
    Trả None khi cert không cấp SAN nào, khi request không qua mTLS, hoặc khi
    transport không thuật lại được. Vắng giá trị nghĩa là "không có gì được
    thuật", không bao giờ là "thuật lại rằng rỗng" - còn câu lời gọi có qua mTLS
    hay không thì current_caller() trả lời.

    Extraction is fail-soft: a malformed or unreadable certificate yields None
    rather than an error, exactly like current_caller(). The framework reports
    what the certificate said and interprets none of it.
    Trích xuất fail-soft: cert dị dạng hoặc không đọc được trả None chứ không nổ,
    y như current_caller(). Framework thuật lại thứ cert khai và không diễn giải
    một chút nào.

    Currently populated by the gRPC RequestContextInterceptor, alongside PEER_CN.
    Hiện được set bởi RequestContextInterceptor của gRPC, cạnh PEER_CN.
    """
    return request_context.get(PEER_SANS)
