from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ._key_context import KeyContext


@runtime_checkable
class JwtKeyProvider(Protocol):
    """Source of the keys used to VERIFY incoming tokens, addressed by `kid`.

    A single static key cannot survive key rotation: while an issuer switches
    keys, tokens signed by the old one are still valid and tokens signed by the
    new one are already arriving, so a verifier must hold several keys at once
    and pick per token. `kid` (RFC 7515 section 4.1.4) is the standard way to
    say which - the framework reads it from the token header, which needs no
    key, and hands it to this provider.
    Một khoá tĩnh không sống qua được lúc xoay khoá: trong lúc issuer đổi khoá
    thì token ký bằng khoá cũ vẫn còn hạn còn token ký bằng khoá mới đã tới, nên
    bên verify phải giữ nhiều khoá cùng lúc và chọn theo từng token. `kid` là
    cách chuẩn để nói khoá nào - framework đọc nó từ header token (không cần
    khoá) rồi đưa xuống provider này.

    Implementations live in application code: a JWKS endpoint, an internal key
    service, a directory of PEM files. The framework never learns where the keys
    come from - it hands over a `kid` and takes back candidates.
    Implementation nằm ở code ứng dụng. Framework không bao giờ biết khoá từ đâu.

    Contract:
    - keys() MUST be an in-memory read - NEVER a network call. It runs on every
      authenticated request.
      keys() BẮT BUỘC đọc bộ nhớ - KHÔNG BAO GIỜ gọi mạng. Nó chạy ở mọi request
      đã xác thực.
    - Keeping those keys fresh is entirely yours. The framework does not fetch,
      does not schedule, and does not cache: it asks and it believes the answer.
      Việc giữ cho khoá luôn mới hoàn toàn thuộc về bạn. Framework không lấy,
      không hẹn giờ, không cache: nó hỏi và tin câu trả lời.
    - Returning an empty sequence means "I do not know this kid", and the request
      is rejected with 401. It is not an error, and it is not retried.
      Trả về dãy rỗng nghĩa là "tôi không biết kid này", request bị từ chối 401.
      Đó không phải lỗi, và không được thử lại.

    Rotation and staleness are therefore your policy to set. A provider that
    refreshes every five minutes will reject tokens bearing a brand new `kid` for
    up to five minutes; one that also refreshes when it meets an unknown `kid`
    will not, at the cost of a call it must rate-limit itself.
    Vì vậy chính sách xoay khoá và độ cũ là của bạn. Provider làm tươi mỗi năm
    phút sẽ từ chối token mang `kid` vừa ra trong tối đa năm phút; provider có
    làm tươi khi gặp `kid` lạ thì không, đổi lại phải tự hãm nhịp lời gọi đó.

    Multiple processes: keys() is called in EVERY process that serves requests,
    so each process reads whatever view it happens to hold. Whether those views
    are separate per-process caches or one shared store is your decision, and the
    framework is indifferent to it - it never writes, so there is nothing for it
    to coordinate.
    Nhiều tiến trình: keys() được gọi ở MỌI tiến trình phục vụ request, nên mỗi
    tiến trình đọc đúng bản nó đang giữ. Các bản đó là cache riêng từng tiến
    trình hay một kho dùng chung là quyết định của bạn; framework không quan tâm
    vì nó không bao giờ ghi, nên không có gì để nó phải điều phối.

    Register in your config layer, alongside the middleware configuration:

        from xime.starters.jwt import configure_jwt, JwtMiddlewareConfig

        configure_jwt(
            JwtMiddlewareConfig(audience="my-service", public_paths=["/health"]),
            key_provider=MyKeyProvider,
        )

    The key_provider argument is a CLASS, resolved from the DI container when the
    web adapter builds the app - add it to dependency.scan()/register().
    Tham số key_provider là một CLASS, được resolve từ DI container lúc web
    adapter dựng app.

    Example:

        class JwksKeyProvider:
            def __init__(self) -> None:
                self._by_kid: dict[str, KeyContext] = {}

            async def load(self) -> None:          # your own refresh, your own schedule
                for entry in await fetch_jwks():
                    self._by_kid[entry.kid] = KeyContext(
                        algorithm=entry.alg,
                        public_key_pem=entry.pem,
                        key_id=entry.kid,
                    )

            def keys(self, kid: str | None) -> Sequence[KeyContext]:
                if kid is None:
                    return ()
                found = self._by_kid.get(kid)
                return (found,) if found else ()

    Note on shape: the sibling GrpcCertificateProvider carries a second method,
    version(), because rebuilding TLS credentials is expensive and must be
    skipped while the certificate is unchanged. Reading a dictionary is not
    expensive, so this Protocol deliberately stays at one method.
    Ghi chú về hình dạng: GrpcCertificateProvider cùng họ có thêm method
    version() vì dựng lại TLS credentials rất đắt nên phải bỏ qua khi cert chưa
    đổi. Đọc một dict thì không đắt, nên Protocol này cố ý chỉ có một method.
    """

    def keys(self, kid: str | None) -> Sequence[KeyContext]:
        """Verification keys that answer to this `kid`, read from memory.

        Args:
            kid: The `kid` header of the incoming token, or None when the token
                 carries no `kid` at all. RFC 7515 makes the header OPTIONAL, so
                 None is a legitimate value and not a malformed token: what it
                 means is your policy. A deployment with one signing key may
                 return that key; a deployment that requires every token to name
                 its key returns ().
                 `kid` của token đến, hoặc None khi token không mang `kid`. RFC
                 7515 nói header này TUỲ CHỌN nên None là giá trị hợp lệ chứ
                 không phải token hỏng: nó nghĩa là gì là chính sách của bạn.

        Returns:
            Candidate keys, in the order they should be tried. Empty means the
            kid is unknown and the request will be rejected. Returning more than
            one is allowed - the framework tries each until a signature verifies,
            which is what makes an overlapping rotation seamless.
            Khoá ứng viên, theo thứ tự nên thử. Rỗng nghĩa là không biết kid này
            và request sẽ bị từ chối. Trả về nhiều khoá là hợp lệ - framework thử
            lần lượt tới khi có chữ ký khớp, và đó là thứ làm cho một lần xoay
            khoá gối đầu diễn ra liền mạch.

        Must not raise, must not block, must not perform I/O.
        Không được ném lỗi, không được chặn, không được làm I/O.
        """
        ...
