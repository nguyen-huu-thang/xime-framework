"""Trạng thái sức khoẻ của một tiến trình - **dữ liệu**, chưa phải endpoint.

Chủ dự án chốt phương án **B+** ngày 2026-08-20: framework cấp cả hai, và cái
thứ hai **mặc định TẮT**.

| | |
|---|---|
| **Dữ liệu** | `app.health()` - luôn có, không phải khai gì |
| **Endpoint sẵn** | `configure_health()` của web adapter - **phải khai mới có** |

Vì sao không tự thêm route: thêm một đường dẫn vào app mà app không khai là bất
ngờ, và một đường dẫn cố định có thể va với route nghiệp vụ. Vì sao không chỉ cấp
dữ liệu: 31 app viết 31 lần, và viết sai thì không ai biết - đúng cách lỗ hổng
A1 (JWT fail-open) đã xảy ra.

### ⚠ `/healthz` và `/readyz` trả lời HAI câu khác nhau

| | Câu hỏi | Ai đọc | Đỏ thì họ làm gì |
|---|---|---|---|
| `/healthz` | *"tiến trình này còn dùng được không"* | systemd, k8s | **restart** |
| `/readyz` | *"nhận request mới được không"* | load balancer | **rút khỏi vòng** |

Gộp hai thứ này là một ca kinh điển của [luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md):
một adapter hỏng trong khi ba cái còn phục vụ thì LB nên rút tiến trình ra, nhưng
systemd **không** nên giết nó - giết là mất luôn log và khả năng gỡ lỗi.

### ⭐ Con phụ vẫn XANH khi cụm thiếu primary

Chốt 2026-08-19, và nó là chỗ dễ trả lời ngược nhất. `/readyz` hỏi *"nhận request
mới được không"* - mà con phụ **vẫn nhận được** dù cụm không có primary; thứ mất
là **job nền**, không phải khả năng phục vụ.

> Trả lời ngược lại thì LB **rút hết con** và cụm chết hoàn toàn vì một job nền
> không chạy - đúng ngược nguyên tắc *"mất job nền còn hơn mất khả năng phục vụ"*
> của chống domino.

Nên adapter hạng đơn nhất đang chờ ở một con phụ nằm ở trạng thái `standby`, và
`standby` **không** làm `ready` đỏ. Thông tin *"cụm đang không có primary"* vẫn
thấy được - qua `primary` trong chính báo cáo này và qua đường ra của cha.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Adapter đang chạy `serve()` bình thường.
SERVING: Final[str] = "serving"

#: Adapter đã `serve()` rồi hỏng, và bị **cô lập** - anh em vẫn chạy.
ISOLATED: Final[str] = "isolated"

#: Adapter hạng đơn nhất ở một tiến trình **không phải primary**. Chưa `start()`,
#: và đó là đúng - nó chờ được thăng cấp. ⚠ **Không phải một lỗi.**
STANDBY: Final[str] = "standby"


@dataclass(frozen=True)
class AdapterHealth:
    adapter_id: str
    kind: str
    state: str


@dataclass(frozen=True)
class HealthReport:
    """Ảnh chụp trạng thái của **tiến trình này**, không phải của cả cụm.

    Cha là chỗ duy nhất nhìn được cả cụm, và đường ra của cha thì đang hoãn -
    khai rõ ở đây để không ai đọc `primary=False` thành *"cụm không có primary"*.
    """

    primary: bool
    adapters: tuple[AdapterHealth, ...]

    @property
    def alive(self) -> bool:
        """Tiến trình còn dùng được không - câu của `/healthz`.

        Đỏ khi **mọi** adapter đã khai đều hỏng. Còn đúng một cái phục vụ thì
        vẫn xanh: giết một tiến trình phục vụ được một phần là đổi *hỏng một
        phần* lấy *hỏng toàn phần*.

        ⚠ Một tiến trình chỉ giữ adapter `standby` (con phụ của một app chỉ có
        scheduler) là **xanh**: nó không phục vụ gì, nhưng nó cũng không hỏng gì,
        và restart nó không làm ai khá hơn.
        """
        return not self.adapters or any(
            a.state != ISOLATED for a in self.adapters
        )

    @property
    def ready(self) -> bool:
        """Nhận request mới được không - câu của `/readyz`.

        Chặt hơn `alive`: **một** adapter bị cô lập là đủ để rút tiến trình khỏi
        vòng, vì LB không biết request nào sẽ rơi vào adapter nào.
        """
        return all(a.state != ISOLATED for a in self.adapters)

    def as_dict(self) -> dict[str, object]:
        return {
            "alive": self.alive,
            "ready": self.ready,
            "primary": self.primary,
            "adapters": [
                {"id": a.adapter_id, "kind": a.kind, "state": a.state}
                for a in self.adapters
            ],
        }
