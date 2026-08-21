from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PostConstruct(Protocol):
    """
    Implement this Protocol to run initialization logic after all singletons
    have been created and dependencies injected.

    Called by LifecycleManager.start() in topological order -
    a dependency's post_construct() always runs before its dependents.

    Typical uses: warm up caches, open connection pools, validate config,
    register event listeners.

    CONTRACT for partial failure (decided 2026-07-30): pre_destroy() is only
    called for instances whose post_construct() COMPLETED - running it on a
    half-initialised object would raise a second error that buries the first.
    So a post_construct that opens a resource and then fails at a later step
    must close that resource itself before re-raising; it is the only code
    that knows how far it got. For several resources, use
    contextlib.AsyncExitStack with pop_all() on success.
    HỢP ĐỒNG khi hỏng giữa chừng: pre_destroy() chỉ gọi cho instance đã chạy
    XONG post_construct(). Mở tài nguyên rồi hỏng ở bước sau thì chính
    post_construct phải tự đóng trước khi ném tiếp - chỉ nó biết đã mở tới đâu.
    Nhiều tài nguyên thì dùng AsyncExitStack + pop_all() lúc thành công.

    Example:
        class UserService:
            def __init__(self, repository: UserRepository): ...

            async def post_construct(self) -> None:
                await self.repository.ping()
    """

    async def post_construct(self) -> None: ...


@runtime_checkable
class PreDestroy(Protocol):
    """
    Implement this Protocol to run cleanup logic before the application shuts down.

    Called by LifecycleManager.stop() in reverse topological order -
    a dependent's pre_destroy() always runs before its dependencies.

    LifecycleManager.stop() attempts every pre_destroy() even when some fail,
    then raises ExceptionGroup with all collected errors.

    Typical uses: flush queues, close connections, release locks, save state.

    Example:
        class CacheService:
            async def pre_destroy(self) -> None:
                await self.client.close()
    """

    async def pre_destroy(self) -> None: ...


@runtime_checkable
class RunOnce(Protocol):
    """Chạy **MỘT lần cho cả cụm**, ở primary, trước khi bất cứ ai phục vụ.

    Ô thứ tư của bảng hai trục - và là ô duy nhất trước 0.8 không có nhà, nên nó
    ở nhờ trong `post_construct` và vì thế chạy ở **mọi** tiến trình:

    | | Mọi tiến trình | **Một lần cho cả cụm** |
    |---|---|---|
    | **Chạy một lần rồi thôi** | `post_construct()` | **`run_once()`** |
    | **Chạy mãi** | `Adapter.start()` | `scaling="singleton"` |

    Ví dụ đúng chỗ: lấy khoá ký lần đầu rồi `publish` vào `RefData`, chạy
    migration, tiêu thụ vé bootstrap cert. Ba việc đó **không được** làm bốn lần
    trong một cụm bốn tiến trình.

    ```python
    class KeyRefreshJob:
        async def post_construct(self) -> None:   # mọi tiến trình, NHẸ
            ...
        async def run_once(self) -> None:         # MỘT lần cho cả cụm
            await self._refdata.publish(await self._trust.fetch_keys())
    ```

    **Vị trí trong vòng đời:**

    ```text
    CHA:  sinh PRIMARY
    PRIM: attach vùng nhớ -> dựng DI -> post_construct -> RUN_ONCE -> báo cha xong
    CHA:  nhận báo xong -> sinh các con còn lại
    CON:  attach -> dựng DI -> post_construct -> (BỎ QUA run_once) -> adapter start
    ```

    **Hai ràng buộc, khai kèm vì chúng không hiển nhiên:**

    1. **`run_once()` phải LẶP LẠI ĐƯỢC.** Primary chết giữa chừng thì con được
       thăng cấp chạy lại nó. Cha biết đã hoàn tất chưa (nó chờ tín hiệu *"xong"*),
       nên quy tắc là: **chưa nhận tín hiệu thì con thăng cấp chạy lại**.
    2. **Không có cặp huỷ.** `post_construct` có `pre_destroy`; `run_once` **cố ý
       không**. Ba ca thật ở trên đều không có gì để dọn, và thêm một hook huỷ chỉ
       để cho cân xứng là thêm thứ không ai dùng.

    ⛔ **Đừng hiện thực nó bằng một job "chạy một lần" của scheduler.** Lý do là
    **thời điểm**: `run_once` phải xong *trước khi bất cứ ai phục vụ*, còn
    scheduler là adapter nên nó start *sau*. Job một-lần của scheduler nghĩa là
    *chạy một lần vào một thời điểm*; `run_once` nghĩa là *chạy một lần, và mọi
    thứ khác đợi nó*.

    ⚠ Ứng dụng một tiến trình **là** cả cụm, nên `run_once()` vẫn chạy ở đó -
    không có nhánh nào để quên.

    ⚠⚠ **"CỤM" Ở ĐÂY LÀ NHÓM TIẾN TRÌNH CỦA MỘT `share_load()`, TỨC MỘT MÁY -
    KHÔNG PHẢI CẢ HỆ THỐNG CỦA BẠN.**

    Cha sinh con bằng `multiprocessing` và trông chúng bằng `waitpid`; cả hai
    thứ đó dừng ở ranh giới một máy (một container). Nên:

    | Triển khai | `run_once()` chạy mấy lần |
    |---|---|
    | 1 máy, `count: 4` | **1** |
    | 3 pod k8s, mỗi pod `count: 4` | **3** - mỗi pod một lần |
    | 3 container Docker | **3** |

    ⛔ Hệ quả phải nhớ: **đừng đặt migration cơ sở dữ liệu vào đây nếu bạn chạy
    nhiều bản sao**. Ba pod cùng khởi động là ba lần migrate chạy song song, và
    `run_once` không có gì ngăn được - nó không biết pod kia tồn tại.

    ✅ Cần *"một lần cho toàn hệ thống"* thì đó là bài toán khác hẳn và framework
    **không** giải: nó cần một khoá mà mọi máy cùng thấy (`CacheService` +
    `SET NX`, khoá advisory của database, hoặc một Job riêng của k8s chạy trước
    Deployment). Xem `docs/{vn,en}/starters.md`.
    """

    async def run_once(self) -> None: ...
