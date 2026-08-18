from __future__ import annotations

# Subprotocol entry that carries the bearer token, e.g.
#   new WebSocket(url, ["xime.bearer." + token, "xime"])
# The browser cannot set headers on a WebSocket handshake - that is a platform
# limit, not a design choice - so the token has to travel inside something the
# handshake already carries. Sec-WebSocket-Protocol is the industry's answer
# (Kubernetes and Firebase both use it): unlike a query string it does not reach
# proxy access logs, browser history, or the Referer header.
# Trình duyệt KHÔNG đặt được header trên bắt tay WebSocket - đó là giới hạn của
# nền tảng, không phải lựa chọn thiết kế - nên token phải đi trong thứ mà bắt tay
# vốn đã chở. Sec-WebSocket-Protocol là lời giải chuẩn của ngành: khác query
# string, nó không lọt vào log của proxy, lịch sử trình duyệt hay Referer.
BEARER_SUBPROTOCOL_PREFIX = "xime.bearer."

# IANA WebSocket close code registry: 3000 = Unauthorized.
# A close code is the ONLY way a WebSocket handshake can say no - there is no
# response body to put a reason in, which is why JwtAuthMiddleware cannot serve
# this transport and lets websocket scopes pass straight through.
# Mã đóng 3000 = Unauthorized theo sổ đăng ký IANA. Mã đóng là cách DUY NHẤT để
# một bắt tay WebSocket nói không - không có body để đặt lý do vào, và đó là lý
# do JwtAuthMiddleware không phục vụ được transport này.
WS_UNAUTHORIZED = 3000


def split_subprotocols(offered: list[str]) -> tuple[str | None, str | None]:
    """Split offered subprotocols into (token, the protocol to echo back).

    A WebSocket server must echo ONE of the offered subprotocols when it
    accepts, and the token entry is not a real protocol - so the client offers
    two and the server answers with the other one.
    Server phải vọng lại MỘT trong các subprotocol được đề nghị khi accept, mà
    entry chứa token không phải một giao thức thật - nên client đề nghị hai cái
    và server trả lời bằng cái còn lại.

        ["xime.bearer.eyJhbGci...", "xime"]  ->  ("eyJhbGci...", "xime")
        ["xime"]                             ->  (None, "xime")
        []                                   ->  (None, None)

    Only the FIRST bearer entry is read. Two of them is a malformed request, not
    a choice to be made: picking one would mean the server decides which of two
    identities the caller meant.
    Chỉ đọc entry bearer ĐẦU TIÊN. Có hai cái là request hỏng chứ không phải một
    phép chọn: chọn một cái nghĩa là server tự quyết người gọi muốn là ai.

    A JWT is safe to carry here: base64url uses only characters RFC 6455 already
    allows in a subprotocol name, dots included.
    JWT chở được ở đây: base64url chỉ dùng ký tự mà RFC 6455 vốn cho phép trong
    tên subprotocol, kể cả dấu chấm.
    """
    token: str | None = None
    echo: str | None = None
    for entry in offered:
        if entry.startswith(BEARER_SUBPROTOCOL_PREFIX):
            if token is None:
                token = entry[len(BEARER_SUBPROTOCOL_PREFIX):] or None
        elif echo is None:
            echo = entry
    return token, echo


def offered_subprotocols(scope: dict) -> list[str]:
    """Read Sec-WebSocket-Protocol out of an ASGI websocket scope."""
    return list(scope.get("subprotocols") or [])
