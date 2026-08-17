from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr, TypeAdapter, ValidationError

from xime.core.exception.framework import StartupException

# Sentinel used by get() to distinguish "key not found" from value=None.
_NOT_FOUND: Any = object()

# Reuses Pydantic's boolean parsing so a flag read through get_bool() is coerced
# exactly like a flag declared as `enabled: bool` on a typed model above.
# Dùng lại bộ parse boolean của Pydantic để cờ đọc qua get_bool() được ép kiểu y
# hệt cờ khai báo dạng `enabled: bool` trên các model có kiểu ở trên.
_BOOL_ADAPTER = TypeAdapter(bool)

# Key-name fragments whose VALUE is never printed by RuntimeConfig.__repr__.
# Matching by NAME (not by value) is what makes this work for app-level keys the
# framework has never heard of - which is where most secrets live. Module level,
# not a class attribute: a leading underscore inside a Pydantic model becomes a
# ModelPrivateAttr, not a plain tuple.
# Khớp theo TÊN khoá để che được cả khoá do app tự khai. Đặt ở mức module vì
# thuộc tính bắt đầu bằng gạch dưới trong model Pydantic sẽ thành ModelPrivateAttr.
_SENSITIVE_KEY_FRAGMENTS = ("secret", "password", "passwd", "token", "key", "credential")
_MASK = "***"


class ServerTlsConfig(BaseModel):
    """TLS (HTTPS) for the HTTP adapter, off unless certfile/keyfile are set.

    The platform deliberately runs without a gateway or reverse proxy, so each
    service terminates TLS itself. Paths point at PEM files on disk, which is
    what a public CA client such as certbot produces; certificates issued by the
    internal Trust CA are meant for service-to-service mTLS and are NOT trusted
    by browsers, so they do not belong here.
    Platform cố ý không có gateway/reverse proxy nên mỗi service tự kết thúc TLS.
    Đường dẫn trỏ tới file PEM trên đĩa - đúng thứ certbot sinh ra; cert do CA nội
    bộ Trust cấp là để service nhận diện nhau qua mTLS, trình duyệt KHÔNG tin, nên
    không dùng ở đây.

    Leaving everything unset keeps the plain-HTTP behaviour unchanged.
    Để trống toàn bộ thì giữ nguyên hành vi HTTP thuần như cũ.
    """

    certfile: str | None = None
    keyfile: str | None = None
    keyfile_password: str | None = None

    # Client-certificate verification (mTLS over REST). ca_certs is the CA bundle
    # used to verify client certificates; cert_reqs says whether one is demanded.
    # Xác thực client cert (mTLS trên REST). ca_certs là bundle CA để verify cert
    # của client; cert_reqs quyết định có bắt buộc client xuất trình hay không.
    ca_certs: str | None = None

    # Spelled out rather than taking ssl.CERT_* integers: an operator reading
    # `cert_reqs: required` in YAML understands it, `cert_reqs: 2` they do not.
    # Dùng chữ thay vì số ssl.CERT_*: operator đọc `cert_reqs: required` là hiểu,
    # `cert_reqs: 2` thì không.
    cert_reqs: Literal["none", "optional", "required"] | None = None

    ciphers: str | None = None

    @property
    def enabled(self) -> bool:
        """True when TLS is configured at all (mirrors uvicorn's own is_ssl)."""
        return bool(self.certfile or self.keyfile)


class ServerConfig(BaseModel):
    """Network binding for the HTTP adapter."""

    host: str = "0.0.0.0"
    port: int = 8080
    ssl: ServerTlsConfig = Field(default_factory=ServerTlsConfig)


class LoggingConfig(BaseModel):
    """Default root logging applied at bootstrap.

    Without this, Python's root logger defaults to WARNING with no handler, so
    every INFO log the framework and app emit is swallowed — the app appears to
    start silently and is easily mistaken for hung. The framework configures
    root logging only when `enabled` is true AND no handler is already installed
    (so an app that calls logging.basicConfig/dictConfig itself always wins).
    Set `enabled: false` to opt out entirely.

    Không có khối này, root logger mặc định mức WARNING, không handler -> mọi log
    INFO bị nuốt, app tưởng như treo. Framework chỉ cấu hình khi enabled=true VÀ
    root chưa có handler (app tự cấu hình logging luôn được ưu tiên). Đặt
    enabled: false để tắt hẳn.
    """

    enabled: bool = True
    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt: str = "%H:%M:%S"


class RuntimeConfig(BaseModel):
    """
    Typed view of application.yml merged with the active env override.

    Framework-level keys (env, server) are parsed into typed fields.
    Application-level keys (database, redis, …) are stored as extra fields
    and accessible via get() with dot-notation.

    Typical creation via bootstrap:
        loader = YamlConfigLoader()
        config = RuntimeConfig.from_dict(loader.load(env=detect_env()))
    """

    model_config = {"extra": "allow"}

    env: str = "development"
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Cached flat dict built once in model_post_init.
    # Avoids re-running model_dump() on every get() call.
    _dump: dict[str, Any] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self._dump = self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeConfig:
        """Build a RuntimeConfig from a raw dict (e.g. from YamlConfigLoader)."""
        return cls.model_validate(data)

    def __repr__(self) -> str:
        """Print the config with secret-looking values masked.

        Pydantic's default repr dumps every field, so a single
        `logger.debug("config=%s", config)` - or an unhandled exception whose
        traceback shows local variables - writes jwt.secret and the database
        password into the log file in clear text. Masking here costs nothing:
        get() is untouched, so code still reads the real values.
        Repr mặc định của Pydantic in mọi field, nên một dòng log debug hay một
        traceback là đủ để đẩy jwt.secret và mật khẩu DB ra file log dạng rõ.
        get() không đổi - code vẫn đọc được giá trị thật.
        """
        return f"{type(self).__name__}({self._redacted(self._dump)!r})"

    __str__ = __repr__

    @classmethod
    def _redacted(cls, value: Any, key: str = "") -> Any:
        lowered = key.lower()
        if key and any(f in lowered for f in _SENSITIVE_KEY_FRAGMENTS):
            # A sensitive NAME holding a dict (e.g. `keys:`) is still walked, so
            # the structure stays readable while the leaves are masked.
            # Tên nhạy cảm mà giá trị là dict thì vẫn duyệt tiếp - giữ được cấu
            # trúc để đọc, chỉ che phần lá.
            if not isinstance(value, dict):
                return _MASK
        if isinstance(value, dict):
            return {k: cls._redacted(v, str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._redacted(item, key) for item in value]
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Access any config value by dot-notation key.

        Examples:
            config.get("env")                 # "production"
            config.get("server.port")          # 8080
            config.get("database.pool_size")   # app-level extra key
            config.get("missing.key", "n/a")   # "n/a"
        """
        parts = key.split(".")
        current: Any = self._dump
        for part in parts:
            if not isinstance(current, dict):
                return default
            current = current.get(part, _NOT_FOUND)
            if current is _NOT_FOUND:
                return default
        return current

    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Access a boolean flag by dot-notation key, with strict coercion.

        Feature flags that live under an untyped block must not be read with a
        bare bool(): YAML quoting is easy to get wrong, and `bool("false")` is
        True, which would silently switch a feature ON when the operator wrote it
        OFF. This accepts what Pydantic accepts for a typed `bool` field ("true"/
        "false", "yes"/"no", "on"/"off", 1/0, case-insensitive) and rejects
        anything else loudly.
        Cờ nằm trong khối không khai kiểu không được đọc bằng bool() trần: viết
        YAML rất dễ nhầm dấu nháy, mà `bool("false")` = True nên tính năng sẽ âm
        thầm BẬT dù operator viết TẮT. Hàm này chấp nhận đúng những gì Pydantic
        chấp nhận cho field `bool` và từ chối phần còn lại một cách ồn ào.

        Raises StartupException on a value that is not a recognisable boolean —
        a misconfigured flag must fail at startup, not behave arbitrarily later.
        Ném StartupException khi giá trị không phải boolean nhận dạng được - cờ
        cấu hình sai phải nổ lúc startup, không được hành xử tuỳ tiện về sau.

        Examples:
            config.get_bool("xime.di.dynamic-binding")        # False when absent
            config.get_bool("features.beta", default=True)
        """
        value = self.get(key, _NOT_FOUND)
        if value is _NOT_FOUND or value is None:
            return default
        try:
            return _BOOL_ADAPTER.validate_python(value)
        except ValidationError as exc:
            raise StartupException(
                f"\nInvalid Boolean Config Value\n"
                f"  Key     : {key}\n"
                f"  Value   : {value!r}\n"
                f"  Expected: a boolean (true/false, yes/no, on/off, 1/0)"
            ) from exc
