"""
Markers cho option của middleware - cho phép `configure_middleware()` /
`configure_cors()` khai báo những giá trị chỉ biết được lúc runtime (sau khi DI
container đã dựng xong), thay vì buộc ứng dụng subclass WebAdapter để tự gọi
`xime_app.get(...)`.

Marker for middleware options - lets configure_middleware()/configure_cors()
declare values only known at runtime (DI service instances, runtime config),
resolved at build_app() time instead of forcing apps to subclass WebAdapter.

Hai marker:
  - Inject(SomeType)       → lấy singleton SomeType từ DI container.
  - FromConfig("a.b", def) → đọc giá trị từ RuntimeConfig theo dot-notation.

Ví dụ trong config/web.py:

    from xime.adapters.web import configure_middleware, Inject, FromConfig

    configure_middleware(
        JwtMiddleware,
        auth_svc=Inject(AuthenticationService),
        user_svc=Inject(UserService),
        blacklist_svc=Inject(BlacklistTokenService),
    )
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application


class Inject:
    """Marker: resolve this option from the DI container at build time.

    Marker: phân giải option này từ DI container lúc build_app.
    """

    __slots__ = ("type",)

    def __init__(self, type: type) -> None:
        self.type = type

    def __repr__(self) -> str:
        name = getattr(self.type, "__name__", self.type)
        return f"Inject({name})"


class FromConfig:
    """Marker: resolve this option from RuntimeConfig (dot-notation) at build time.

    A missing key resolves to `default` (None when not given) - there is no
    "required key" mode; validate required config in the middleware itself.
    Marker: phân giải option này từ RuntimeConfig (dot-notation) lúc build_app.
    Thiếu key thì trả `default` (None nếu không truyền) - không có chế độ "bắt
    buộc"; hãy validate config bắt buộc trong chính middleware.
    """

    __slots__ = ("key", "default")

    def __init__(self, key: str, default: Any = None) -> None:
        self.key = key
        self.default = default

    def __repr__(self) -> str:
        return f"FromConfig({self.key!r}, default={self.default!r})"


def resolve_options(
    options: dict[str, Any],
    app: Application,
) -> dict[str, Any]:
    """Trả về bản sao của options với mọi marker Inject/FromConfig đã được phân giải.

    Chỉ phân giải giá trị ở tầng trên cùng của dict (không đệ quy vào list/dict
    lồng nhau) - đủ cho mọi tham số middleware hiện có và giữ hành vi dễ đoán.
    Giá trị không phải marker được giữ nguyên.
    """
    from xime.core.config.runtime import RuntimeConfig

    runtime: RuntimeConfig | None = None
    resolved: dict[str, Any] = {}
    for name, value in options.items():
        if isinstance(value, Inject):
            try:
                resolved[name] = app.get(value.type)
            except KeyError:
                type_name = getattr(value.type, "__name__", value.type)
                raise RuntimeError(
                    f"configure_middleware: cannot inject option '{name}' - "
                    f"{type_name} is not registered in the DI container. "
                    f"Add its package to dependency.scan() / register() in "
                    f"config/dependency.py."
                ) from None
        elif isinstance(value, FromConfig):
            if runtime is None:
                runtime = app.get(RuntimeConfig)  # type: ignore[assignment]
            resolved[name] = runtime.get(value.key, value.default)
        else:
            resolved[name] = value
    return resolved
