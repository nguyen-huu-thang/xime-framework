from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

# Ba hạng nhân bản. Đây là **dữ liệu**, không phải chú thích: trước 0.8 lý do
# chống trùng nằm trong docstring của từng adapter - framework đọc được nhưng
# không dùng được.
SCALING_REPLICATED: Final[str] = "replicated"
"""N tiến trình chạy N bản giống hệt, kernel chia tải. web, grpc."""

SCALING_SHARDED: Final[str] = "sharded"
"""Mỗi tiến trình một **phần** của việc, không bản nào giống bản nào.

⭐ **Nhân bản cho *dư thừa*, phân mảnh thì KHÔNG.** Một tiến trình web chết thì
ba con còn lại phục vụ tiếp; một tiến trình modbus chết thì **cụm thiết bị của nó
không ai đọc**. Khác biệt về chất, không phải về mức.
"""

SCALING_SINGLETON: Final[str] = "singleton"
"""Chỉ primary chạy. scheduler."""

_SCALINGS: Final[frozenset[str]] = frozenset(
    {SCALING_REPLICATED, SCALING_SHARDED, SCALING_SINGLETON}
)


@runtime_checkable
class Adapter(Protocol):
    """Hợp đồng mọi adapter của Xime phải thoả.

    Đăng ký bằng `app.use(adapter)`; framework `start()` tuần tự rồi `serve()`
    song song sau khi DI đã dựng xong.

    ```python
    class WebAdapter(Adapter, scaling="replicated"):
        ...

    class MqttAdapter(
        Adapter,
        scaling="sharded",
        unique_per_process=("client_id",),
        disjoint_per_process=("topics",),
    ):
        ...
    ```

    **Vòng đời:**

    ```text
    1. app.run() -> app.start()          DI dựng xong, singleton đã tạo
    2. adapter.start(app) TUẦN TỰ        chiếm tài nguyên, TRẢ VỀ khi xong
    3. adapter.serve()    SONG SONG      phục vụ, CHẶN tới khi bị dừng
    4. adapter.stop()     ngược thứ tự đăng ký
    5. app.stop()                        PreDestroy, DI dispose
    ```

    ⭐ Tách `start()` khỏi `serve()` **không ép hình dạng mới lên adapter** - nó
    **thôi che giấu** cấu trúc vốn có ở tầng dưới: gRPC đã có
    `start()` + `wait_for_termination()`, uvicorn đã có `startup()` +
    `main_loop()`, asyncio đã có `start_unix_server()` + `serve_forever()`.

    Ranh giới đó là thứ **cưỡng chế được** ba việc mà một `start()` gộp không làm
    nổi: cha biết khi nào sinh con tiếp theo · lỗi *"chưa phục vụ được"* tách
    khỏi lỗi *"đang phục vụ thì hỏng"* · và `/readyz` có câu trả lời.
    """

    adapter_id: str
    """Định danh của instance này, làm **ba** việc.

    1. Chống đăng ký trùng ở `Application.use()`.
    2. Tra khối cấu hình của riêng nó.
    3. Tầng khoá thứ ba trong `processes:` (`tiến trình -> loại -> id`).

    Việc 3 là việc mới của 0.8, và nó biến chuyện đặt tên từ *"dọn cho đẹp"*
    thành **bắt buộc**: framework phải hỏi adapter *"anh tên gì"* trước khi biết
    đẩy khối cấu hình nào vào. Id còn mềm thì câu đó trả `None`, và lúc đó không
    có gì để làm ngoài đoán.
    """

    # ⚠ `scaling`, `unique_per_process` và `disjoint_per_process` **cố ý KHÔNG
    # khai ở thân Protocol**. Khai ở đây là đưa chúng vào `__protocol_attrs__`,
    # tức `isinstance` bắt đầu đòi cả ba - và lúc đó một adapter thiếu `scaling`
    # bị báo là *"sai hình dạng"* thay vì *"quên khai hạng"*. Hai câu trả lời cho
    # hai bệnh khác nhau, nên chúng phải là hai phép kiểm khác nhau:
    # `isinstance` hỏi **có đúng hình dạng adapter không**, `Application.use()`
    # hỏi tiếp **những giá trị nó khai có dùng được không**.
    #
    # `__init_subclass__` bên dưới vẫn gán cả ba, và `use()` vẫn từ chối adapter
    # không có `scaling`.

    def __init_subclass__(
        cls,
        *,
        scaling: str | None = None,
        unique_per_process: tuple[str, ...] = (),
        disjoint_per_process: tuple[str, ...] = (),
        **kwargs: Any,
    ) -> None:
        """Nhận hạng nhân bản qua **tham số class** (PEP 487).

        Cùng khuôn `Store(name=..., ttl=...)` và `RefData` chốt cùng đợt: cấu
        hình đi vào `__init_subclass__`, **không** thành thuộc tính do app khai,
        nên nó không thể va tên với dữ liệu của app.

        ⛔ **`scaling` BẮT BUỘC, không có mặc định.** Mặc định `replicated` là
        **nguy** (một adapter chưa từng nghĩ tới nhân bản bị nhân bản, và nó hỏng
        **im lặng**); mặc định `singleton` thì app chậm mà không ai biết vì sao.
        Đây là quyết định người viết adapter **phải** đưa ra, và không giá trị nào
        đoán hộ được.

        ⛔ **`replicated` và `singleton` không được khai hai tham số kia** - chúng
        chỉ có nghĩa với `sharded`, và một tham số bị bỏ qua im lặng là chỗ để
        người ta tin vào thứ không xảy ra.
        """
        super().__init_subclass__(**kwargs)
        # Protocol con (nếu ai đó thu hẹp hợp đồng) không phải khai gì.
        if getattr(cls, "_is_protocol", False):
            return

        from xime.core.exception.framework import StartupException

        # Lớp con của một adapter ĐÃ khai thì kế thừa - `class TestWeb(WebAdapter)`
        # không phải nhắc lại `replicated`. Bắt buộc chỉ áp cho adapter **mới**,
        # đúng ca mà luật sinh ra để chặn: một adapter chưa từng nghĩ tới nhân
        # bản bị nhân bản. Ép khai lại chỉ dạy người ta chép một dòng cho qua.
        inherited = getattr(cls, "scaling", None)
        effective = scaling if scaling is not None else inherited
        if effective is None:
            raise StartupException(
                f"\nAdapter Without A scaling Class Argument\n"
                f"  Adapter : {cls.__name__}\n"
                f"  Expected: one of {', '.join(sorted(_SCALINGS))}\n"
                f"  Detail  : how an adapter behaves across processes cannot be "
                f"guessed. Declare it:\n"
                f"\n"
                f"      class {cls.__name__}(Adapter, scaling=\"replicated\"): ..."
            )
        if effective not in _SCALINGS:
            raise StartupException(
                f"\nInvalid scaling\n"
                f"  Adapter : {cls.__name__}\n"
                f"  Value   : {effective!r}\n"
                f"  Expected: one of {', '.join(sorted(_SCALINGS))}"
            )
        if effective != SCALING_SHARDED and (unique_per_process or disjoint_per_process):
            raise StartupException(
                f"\nSharding Rules On A Non-Sharded Adapter\n"
                f"  Adapter: {cls.__name__}\n"
                f"  scaling: {effective}\n"
                f"  Detail : unique_per_process and disjoint_per_process only "
                f"mean something for scaling=\"sharded\". Silently ignoring them "
                f"would let you believe a check runs when it does not."
            )
        cls.scaling = effective
        if scaling is not None:
            # Đổi hạng thì luật phân mảnh của lớp cha hết áp dụng - giữ lại là
            # chạy một phép kiểm cho một hạng không còn tồn tại.
            cls.unique_per_process = tuple(unique_per_process)
            cls.disjoint_per_process = tuple(disjoint_per_process)
        else:
            if unique_per_process:
                cls.unique_per_process = tuple(unique_per_process)
            if disjoint_per_process:
                cls.disjoint_per_process = tuple(disjoint_per_process)

    async def start(self, app: Application) -> None:
        """Chiếm tài nguyên rồi **TRẢ VỀ**. Không phục vụ ở đây.

        Bind cổng, mở kết nối, dựng bảng route. Nhanh, có thể lỗi, và **lỗi lúc
        khởi động thì nên sập cả tiến trình** - chưa phục vụ được thì đứng dậy đi
        tiếp là vô nghĩa.
        """
        ...

    async def serve(self) -> None:
        """Phục vụ, **CHẶN** tới khi `stop()` được gọi.

        Lỗi ném ra từ đây nghĩa là *"đã phục vụ rồi mới hỏng"*, và framework
        **cô lập adapter đó** thay vì kéo cả tiến trình theo.
        """
        ...

    async def stop(self) -> None:
        """Ra hiệu dừng. Phải **idempotent** - có thể bị gọi khi `start()` chưa
        bao giờ hoàn tất."""
        ...
