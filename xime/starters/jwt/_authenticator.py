from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from xime.core.exception.framework import AuthenticationException

from ._config import JwtMiddlewareConfig
from ._key_context import KeyContext
from ._provider import JwtKeyProvider
from ._pyjwt import pyjwt
from ._verifier import JwtTokenVerifier

_log = logging.getLogger("xime.jwt")


class JwtAuthenticator:
    """Turns a raw token into verified claims. Transport-agnostic on purpose.

    Extracted from JwtAuthMiddleware in 0.7.2 so the WebSocket path can reuse it
    instead of growing a second answer to "what counts as a valid token". Two
    copies of that answer means two places to change when a knob is added, and
    the one nobody remembers is the one that rots.
    Tách khỏi JwtAuthMiddleware ở 0.7.2 để đường WebSocket dùng lại, thay vì mọc
    thêm một lời đáp thứ hai cho câu "thế nào là token hợp lệ". Hai bản của câu
    trả lời đó là hai chỗ phải sửa khi thêm knob, và cái không ai nhớ sẽ mục.

    It knows nothing about HTTP or WebSocket: it neither reads a request nor
    writes a response, so each transport keeps its own way of saying no - a 401
    for HTTP, a close frame for WebSocket.
    Nó không biết gì về HTTP hay WebSocket: không đọc request, không ghi
    response, nên mỗi transport giữ cách từ chối của riêng mình.
    """

    def __init__(
        self,
        config: JwtMiddlewareConfig,
        *,
        key_provider: JwtKeyProvider | None = None,
        verifier: JwtTokenVerifier | None = None,
    ) -> None:
        self._config = config
        self._provider = key_provider
        if verifier is not None:
            self._verifier = verifier
        else:
            from ._verifier import PyJwtTokenVerifier

            self._verifier = PyJwtTokenVerifier()

    @property
    def config(self) -> JwtMiddlewareConfig:
        return self._config

    def verify(self, token: str) -> dict[str, Any]:
        """Verify against every key that answers to the token's `kid`.

        More than one candidate is normal while an issuer rotates: the old key
        and the new one are both valid, and only trying them tells which signed
        this token.
        Nhiều hơn một khoá ứng viên là bình thường trong lúc issuer xoay khoá.
        """
        first_error: AuthenticationException | None = None
        for key in self.candidate_keys(token):
            try:
                return self._verifier.verify(
                    token,
                    key,
                    audience=self._config.audience,
                    issuer=self._config.issuer,
                    algorithms=self._config.algorithms,
                    leeway=self._config.leeway,
                    require=self._config.require,
                )
            except AuthenticationException as exc:
                # Report the FIRST failure, not the last: keys() returns
                # candidates in the order they should be tried, so the first is
                # the one the provider considers most likely to be right, and its
                # reason is the most useful thing to tell the caller.
                # Báo lỗi ĐẦU TIÊN chứ không phải cuối: keys() trả khoá theo thứ
                # tự nên thử, nên cái đầu là cái provider cho là khả dĩ nhất.
                if first_error is None:
                    first_error = exc
        raise first_error or AuthenticationException("Unknown signing key")

    def candidate_keys(self, token: str) -> Sequence[KeyContext]:
        if self._provider is None:
            # Startup validation guarantees a static key exists when there is no
            # provider, so this is not an optional dereference in practice.
            # Kiểm lúc khởi động đã bảo đảm có khoá tĩnh khi không có provider.
            static = self._config.key_context
            return (static,) if static is not None else ()

        kid = self.read_kid(token)
        try:
            candidates = self._provider.keys(kid)
        except Exception:
            # keys() is contractually forbidden from raising. If it does anyway,
            # fail closed rather than turning an attacker-supplied `kid` into a
            # 500 - but log it loudly, because it is a bug in the provider and
            # silence would let it live forever behind a plain 401.
            # keys() bị hợp đồng cấm ném lỗi. Nếu vẫn ném thì đóng cửa lại thay vì
            # biến một `kid` do kẻ tấn công đặt thành lỗi 500 - nhưng phải log to.
            _log.exception("JwtKeyProvider.keys() raised; rejecting the request")
            raise AuthenticationException("Unknown signing key") from None

        if not candidates:
            raise AuthenticationException("Unknown signing key")
        return candidates

    @staticmethod
    def read_kid(token: str) -> str | None:
        """Read the `kid` header without a key, and refuse anything but a string.

        The header is JSON chosen by whoever sent the token, so `kid` can arrive
        as a number, a list or an object. Every PyJWT in the supported range
        (checked at the 2.8 floor) already refuses those, so the isinstance check
        below is not load-bearing against PyJWT - it is here because
        JwtKeyProvider.keys() is annotated `str | None`, and a promise made to
        application developers should be kept by the code that makes it rather
        than by a third-party library that happens to agree today. Without it, a
        provider doing a plain dict lookup would meet an unhashable key.
        Header là JSON do bên gửi token chọn, nên `kid` có thể tới dưới dạng số,
        mảng hay object. Mọi bản PyJWT trong dải hỗ trợ đều đã từ chối sẵn, nên
        phép kiểm isinstance dưới đây không phải lớp chắn trước PyJWT - nó ở đây
        vì JwtKeyProvider.keys() khai kiểu `str | None`, và một lời hứa với người
        viết ứng dụng nên do chính chỗ hứa giữ.
        """
        try:
            header = pyjwt().get_unverified_header(token)
        except Exception:
            raise AuthenticationException("Invalid token: malformed header") from None

        kid = header.get("kid")
        if kid is None:
            return None
        if not isinstance(kid, str):
            raise AuthenticationException("Invalid token: malformed header")
        return kid
