"""`configure_health()` - hai endpoint sức khoẻ, **mặc định TẮT**.

```python
# config/web.py
from xime.adapters.web import configure_health

configure_health()                                  # /healthz và /readyz
configure_health(healthz="/_alive", readyz=None)    # chỉ một cái, đường dẫn riêng
```

Chủ dự án chốt **phương án B+** ngày 2026-08-20: framework cấp cả **dữ liệu**
(`app.health()`, luôn có) lẫn **endpoint sẵn** (hàm này, phải khai mới có).

| | Đánh giá |
|---|---|
| Framework tự thêm route | Bất ngờ - thêm đường dẫn vào app mà app không khai, và một đường dẫn cố định có thể va với route nghiệp vụ |
| Chỉ cấp dữ liệu, app tự viết | **31 app viết 31 lần**, và viết sai thì không ai biết - đúng cách lỗ hổng A1 (JWT fail-open) đã xảy ra |
| ✅ **Cả hai, cái thứ hai mặc định tắt** | Không bất ngờ, không bắt ai viết lại, và đúng khuôn `configure_*` đã có |

### ⚠ Hai đường dẫn trả lời HAI câu, đừng gộp

| | Câu hỏi | Ai đọc | Đỏ thì họ làm gì |
|---|---|---|---|
| `/healthz` | *"tiến trình này còn dùng được không"* | systemd, k8s | **restart** |
| `/readyz` | *"nhận request mới được không"* | load balancer | **rút khỏi vòng** |

Một adapter hỏng trong khi ba cái còn phục vụ thì LB **nên** rút tiến trình ra,
còn systemd thì **không nên** giết nó - giết là mất luôn log và khả năng gỡ lỗi,
tức đổi *hỏng một phần* lấy *hỏng toàn phần*.

### ⛔ Không xác thực, và đó là quyết định chứ không phải sót

Cả hai đường dẫn nằm trong `public_paths` mặc định của middleware JWT. Chúng phải
trả lời được **khi mọi thứ khác đã hỏng** - kể cả khi không lấy được khoá verify.
Một `/healthz` đòi token là một `/healthz` im lặng đúng lúc cần nhất.

Bù lại, thân phản hồi **không mang gì nhạy cảm**: id và hạng adapter, trạng thái,
và một cờ primary. Không host, không cổng, không phiên bản, không thông điệp lỗi.

⭐ Câu *"nằm trong `public_paths` mặc định"* chỉ đúng cho middleware JWT **của
framework**. Middleware tự viết - hàng rào IP, ghi log, hãm nhịp - thì tự hỏi
`public_health_paths()`; xem docstring của hàm đó.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._registry import registry

if TYPE_CHECKING:
    from fastapi import FastAPI

    from xime.core.bootstrap._health import HealthReport
    from xime.core.bootstrap.application import Application

DEFAULT_HEALTHZ = "/healthz"
DEFAULT_READYZ = "/readyz"


@dataclass(frozen=True)
class HealthConfig:
    healthz: str | None = DEFAULT_HEALTHZ
    readyz: str | None = DEFAULT_READYZ


def configure_health(
    *,
    healthz: str | None = DEFAULT_HEALTHZ,
    readyz: str | None = DEFAULT_READYZ,
    server_id: str = "default",
) -> None:
    """Bật hai endpoint sức khoẻ trên một web server.

    Args:
        healthz: đường dẫn cho câu *"còn dùng được không"*. `None` để tắt.
        readyz: đường dẫn cho câu *"nhận request được không"*. `None` để tắt.
        server_id: server nào, khi ứng dụng có nhiều web adapter.

    ⭐ Đặt chúng trên một **server phụ chỉ nghe `127.0.0.1`** là hình dạng an
    toàn nhất ở prod: người vận hành và systemd tới được, internet thì không.
    """
    registry.set_health(HealthConfig(healthz=healthz, readyz=readyz), server_id)


def public_health_paths(server_id: str = "default") -> tuple[str, ...]:
    """Đường dẫn sức khoẻ đang bật, để middleware TỰ VIẾT cho chúng đi qua.

    Args:
        server_id: server nào, khi ứng dụng có nhiều web adapter.

    Returns:
        Các đường dẫn `configure_health()` đã bật. Chưa khai thì rỗng.

    ### ⛔ Dùng `configure_jwt` thì ĐỪNG gọi hàm này

    Framework **tự** cộng đường sức khoẻ vào `public_paths` trước khi gắn
    middleware JWT (`_adapter.py`, nhánh `_configure_jwt_middleware`). Gọi thêm
    ở đây là chép tay một việc đã có người làm, và bản chép sẽ **lệch** vào
    ngày luật khớp đường dẫn đổi.

    Hàm này dành cho middleware **không phải của framework** - và không chỉ
    middleware xác thực. Hàng rào IP, ghi log truy cập, hãm nhịp, đếm số đo:
    thứ nào cũng có lý do bỏ qua đường sức khoẻ, và những lý do đó **không mất
    đi** khi ứng dụng chuyển sang `configure_jwt`.

    ```python
    from xime.adapters.web import configure_middleware, public_health_paths

    configure_middleware(
        HangRaoIpMiddleware,
        public_paths=[*cau_hinh_rieng, *public_health_paths()],
    )
    ```

    ### ⚠ Phải đọc SAU `configure_health()`

    Nó đọc sổ đăng ký tại thời điểm được gọi, nên gọi trước khi khai thì nhận
    một tuple **rỗng** - và rỗng ở đây trông y hệt *"app này không bật endpoint
    sức khoẻ"*. Hàng rào chặn mất `/healthz` mà không có gì báo, vì middleware
    của bạn từ chối rất gọn gàng.

    Cách tránh: để `configure_health()` ở đầu `config/web.py`, trước mọi lời
    gọi `configure_middleware`.
    """
    config = registry.get_health(server_id)
    if config is None:
        return ()
    return tuple(p for p in (config.healthz, config.readyz) if p)


def add_health_routes(
    fastapi_app: FastAPI, xime_app: Application, server_id: str = "default"
) -> None:
    """Gắn route đã khai. Không khai thì không gắn gì."""
    from fastapi.responses import JSONResponse

    config = registry.get_health(server_id)
    if config is None:
        return

    def _respond(pick: Callable[[HealthReport], bool]) -> JSONResponse:
        # MỘT ảnh chụp cho cả mã trạng thái lẫn thân phản hồi. Gọi `health()` hai
        # lần là mời một phản hồi tự mâu thuẫn: 200 kèm một thân nói `alive:
        # false`, vì một adapter chết đúng khoảng giữa hai lời gọi.
        report = xime_app.health()
        return JSONResponse(report.as_dict(), status_code=200 if pick(report) else 503)

    if config.healthz:
        fastapi_app.add_api_route(
            config.healthz,
            lambda: _respond(lambda r: r.alive),
            methods=["GET"],
            include_in_schema=False,
            name="xime_healthz",
        )
    if config.readyz:
        fastapi_app.add_api_route(
            config.readyz,
            lambda: _respond(lambda r: r.ready),
            methods=["GET"],
            include_in_schema=False,
            name="xime_readyz",
        )
