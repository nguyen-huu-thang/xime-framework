from __future__ import annotations

from dataclasses import dataclass, field

from ._key_context import KeyContext


@dataclass
class JwtMiddlewareConfig:
    """Configuration for JwtAuthMiddleware.

    key_context : Single static key used to VERIFY incoming tokens.
                  For asymmetric algorithms, provide only public_key_pem.
                  For HMAC, provide secret.
                  Leave it unset when passing key_provider= to configure_jwt():
                  exactly one of the two must be given, and supplying both is a
                  start-up error rather than a silent precedence rule.
                  Bỏ trống khi truyền key_provider= cho configure_jwt(): đúng một
                  trong hai phải có, đưa cả hai là lỗi lúc khởi động chứ không
                  phải một luật ưu tiên ngầm.
    identity_claim : JWT claim mapped to SecurityContext.identity (default: "sub").
    public_paths   : Request paths that bypass JWT authentication entirely.
                     Matched EXACTLY (only a trailing slash is ignored), not by
                     prefix: listing "/docs" does not open "/docs/anything".
                     So khớp CHÍNH XÁC (chỉ bỏ qua dấu / cuối), KHÔNG phải tiền
                     tố: khai "/docs" không mở "/docs/bất-kỳ-gì".
    audience : Expected `aud` claim. When set, the token's audience MUST match
               (PyJWT raises otherwise). When None, the audience is NOT enforced
               and tokens carrying an `aud` claim are still accepted (a multi-
               service platform that shares one signing key SHOULD set this to
               its own service id to reject tokens minted for another service).
               Khi set: bắt buộc khớp aud; khi None: KHÔNG ép aud (vẫn nhận token
               có aud). Platform dùng chung key NÊN set để chặn token của service khác.
    issuer   : Expected `iss` claim. When set, the token's issuer MUST match.
               When None, the issuer is not checked.
               Khi set: bắt buộc khớp iss; None: không kiểm.
    algorithms : Allow-list of accepted `alg` values. This is a CAP, not a
                 selection: the algorithm actually used is the one carried by the
                 key, and a key whose algorithm falls outside this list is
                 refused. Leave it None to accept whatever each key declares.
                 Set it whenever keys arrive from a source you do not control -
                 that is what closes the classic algorithm-confusion attack.
                 Danh sách trắng các `alg` được chấp nhận. Đây là TRẦN, không
                 phải phép chọn: thuật toán dùng thật là thuật toán của chính
                 khoá, và khoá nào có thuật toán ngoài danh sách này thì bị từ
                 chối. Để None là chấp nhận thuật toán mà mỗi khoá tự khai. Nên
                 set khi khoá đến từ nguồn bạn không kiểm soát.
    leeway   : Seconds of tolerance for the time-based claims (exp, nbf, iat).
               Two machines whose clocks differ by a few seconds will otherwise
               reject tokens that were just minted, and the symptom is an
               intermittent 401 that is very hard to trace.
               Số giây dung sai cho các claim thời gian. Hai máy lệch đồng hồ vài
               giây sẽ từ chối token vừa được cấp, và triệu chứng là 401 chập
               chờn rất khó lần ra.
    require  : Claims that MUST be present. Verification of exp/nbf/iat only
               happens when the claim EXISTS, so a token carrying no `exp` at all
               is accepted by default - it never expires. Put "exp" here to
               forbid that.
               Các claim BẮT BUỘC phải có mặt. exp/nbf/iat chỉ được kiểm khi claim
               TỒN TẠI, nên token không mang `exp` mặc định vẫn qua - nó không bao
               giờ hết hạn. Đặt "exp" vào đây để cấm chuyện đó.

    Example usage in config/jwt.py:

        import os
        from xime.starters.jwt import configure_jwt, JwtMiddlewareConfig, KeyContext

        configure_jwt(JwtMiddlewareConfig(
            key_context=KeyContext(
                algorithm="RS256",
                public_key_pem=os.environ["JWT_PUBLIC_KEY"],
            ),
            identity_claim="sub",
            audience="data-service",
            issuer="https://identity.internal",
            public_paths=["/auth/login", "/auth/refresh", "/health"],
            algorithms=["RS256"],
            leeway=30,
            require=["exp"],
        ))

    Or, when the keys rotate and are addressed by `kid` (see JwtKeyProvider):

        configure_jwt(
            JwtMiddlewareConfig(audience="data-service", require=["exp"]),
            key_provider=MyKeyProvider,
        )
    """

    key_context: KeyContext | None = None
    identity_claim: str = "sub"
    public_paths: list[str] = field(default_factory=list)
    audience: str | list[str] | None = None
    issuer: str | None = None
    algorithms: list[str] | None = None
    leeway: float = 0
    require: list[str] = field(default_factory=list)


class _JwtRegistry:
    def __init__(self) -> None:
        self._config: JwtMiddlewareConfig | None = None
        self._key_provider: type | None = None
        self._verifier: type | None = None

    def set(
        self,
        config: JwtMiddlewareConfig,
        key_provider: type | None = None,
        verifier: type | None = None,
    ) -> None:
        self._config = config
        self._key_provider = key_provider
        self._verifier = verifier

    def get(self) -> JwtMiddlewareConfig | None:
        return self._config

    def get_key_provider(self) -> type | None:
        return self._key_provider

    def get_verifier(self) -> type | None:
        return self._verifier

    def reset(self) -> None:
        """Clear the registration - test cleanup only."""
        self._config = None
        self._key_provider = None
        self._verifier = None


# Module-level singleton - read by WebAdapter.build() to add JwtAuthMiddleware.
jwt_registry = _JwtRegistry()


def configure_jwt(
    config: JwtMiddlewareConfig,
    *,
    key_provider: type | None = None,
    verifier: type | None = None,
) -> None:
    """Register JWT middleware configuration.

    Call this once in your config layer (e.g. config/jwt.py).
    WebAdapter.build_app() reads this registry and adds JwtAuthMiddleware automatically.

    This follows the same explicit-call pattern as configure_openapi():
    the developer opts in by calling this function - no auto-scan magic.

    Args:
        config: Everything the middleware validates - claims, paths, tolerances.
        key_provider: A CLASS implementing JwtKeyProvider, resolved from the DI
            container when the app is built, for deployments whose verification
            keys rotate and are addressed by `kid`. Mirrors
            configure_grpc_tls(provider=...). Add it to
            dependency.scan()/register() so the container can build it.
            Một CLASS hiện thực JwtKeyProvider, được resolve từ DI container lúc
            dựng app, cho triển khai có khoá xoay và định địa chỉ bằng `kid`.
        verifier: A CLASS implementing JwtTokenVerifier, for the rare case of
            replacing the verification library itself. Named here rather than
            picked up from a dependency.bind(): the middleware is built by the
            adapter, not by the container, so a binding alone would not reach it
            and the substitution would appear to work while changing nothing.
            Một CLASS hiện thực JwtTokenVerifier, cho ca hiếm là thay hẳn thư
            viện verify. Khai ở đây chứ không nhặt từ dependency.bind(): middleware
            do adapter dựng chứ không do container dựng, nên chỉ bind thì không
            tới được nó và phép thay thế trông như chạy trong khi không đổi gì.

    Exactly one key source must be given: either config.key_context (one static
    key) or key_provider (many keys, by kid). Neither, or both, fails at
    start-up. Neither is refused on purpose - the alternative is an application
    that boots without authentication and looks perfectly healthy while every
    endpoint is open.
    Bắt buộc đúng MỘT nguồn khoá: hoặc config.key_context (một khoá tĩnh) hoặc
    key_provider (nhiều khoá, theo kid). Không có cái nào, hoặc có cả hai, đều
    hỏng lúc khởi động. Không có cái nào bị từ chối là CÓ CHỦ Ý - đường còn lại
    là một ứng dụng khởi động không có xác thực, trông hoàn toàn khoẻ mạnh trong
    khi mọi endpoint đều mở.
    """
    jwt_registry.set(config, key_provider, verifier)
