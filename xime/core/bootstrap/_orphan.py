"""Con không được sống lâu hơn cha.

`_supervisor.py` đã khai đây là kết cục tệ nhất, ngay trong docstring của
`_install_signal_handlers`:

> *"cha chết ngay còn con **sống tiếp mồ côi** - vẫn giữ cổng, vẫn phục vụ, và
> không ai dựng lại chúng nữa. Đúng thứ tệ nhất: hệ thống trông như đã tắt mà
> thực ra chưa."*

Nhưng lớp phòng thủ ở đó là **bắt tín hiệu**, nên nó chỉ che được cái chết
*lịch sự* của cha: `SIGINT`, `SIGTERM`, `SIGBREAK`. Ba đường còn lại thì không
ai bắt được, và cả ba đều xảy ra thật:

| Cha chết kiểu gì | Bắt được? |
|---|---|
| `Ctrl+C`, `systemd stop`, `taskkill` (không `/F`) | ✅ handler chạy, cha tắt cả đàn |
| `SIGKILL`, `Stop-Process -Force`, `taskkill /F` | ⛔ **không ai bắt được** |
| Cha sập vì lỗi trong chính nó | ⛔ |
| Máy hết RAM và kernel giết cha | ⛔ |

Nên module này lấp phần còn lại từ **phía con**: con canh cha, và cha chết thì
con tự đi.

### ⭐ Vì sao đây là việc của con chứ không phải của cha

Cha không làm được. Mọi cơ chế đặt ở cha đều phải **chạy sau khi cha đã chết**,
mà một tiến trình đã chết thì không chạy gì nữa. Đây là bất đối xứng cố hữu:
người duy nhất còn sống để hành động là con.

### ⭐⭐ Nó KHÔNG cần một cơ chế mới - `multiprocessing` đã có sẵn

`multiprocessing.parent_process()` trả về một `_ParentProcess` mang **sentinel
của cha**, và `join()` trên đó chặn tới đúng lúc cha thoát. Đây là hạ tầng của
thư viện chuẩn, có từ Python 3.8, và nó hoạt động trên **cả hai** nền tảng bằng
hai cơ chế khác nhau:

| | Sentinel là gì | Nổ khi |
|---|---|---|
| Linux | một đầu ống thừa kế lúc spawn | cha chết -> mọi handle đóng -> EOF |
| Windows | `HANDLE` tới chính tiến trình cha | cha thoát -> object được báo hiệu |

Đo thật trên Windows 11 ngày 2026-08-23: `Stop-Process -Force` lên cha thì
`parent.join()` ở con trả về, và con thoát. **Không thêm vùng nhớ chung nào,
không thêm khoá cấu hình nào, không thêm tên công khai nào.**

⚠ Vì vậy đừng thay nó bằng bảng nhịp ở `_watchdog.py`: bảng nhịp nằm trong bộ
nhớ chung, mà bộ nhớ chung **không biến mất khi cha chết** - nó chỉ đứng yên.
Đứng yên và *"cha đang bận"* trông giống hệt nhau, còn sentinel thì không.

### Vì sao phải là THREAD, dù `_watchdog.py` cấm thread

Hai chỗ nghe giống nhau mà đo hai thứ ngược nhau, nên luật cũng ngược nhau:

| | Vỗ nhịp (`_watchdog.py`) | Canh cha (**ở đây**) |
|---|---|---|
| Đo gì | *event loop của tôi còn quay không* | *cha tôi còn sống không* |
| Thread thì sao | ⛔ **hỏng** - vỗ đều trong khi loop đã treo | ✅ **đúng** - phải chạy được **kể cả khi** loop treo |

Con mồ côi mà loop đang treo là ca **tệ nhất trong các ca tệ**: nó giữ cổng và
không phục vụ nổi ai. Đặt phép canh này lên loop là để đúng ca đó thoát được.

### Hai bước, và bước hai không lịch sự

Thoát êm trước (huỷ task chính -> `_run_async` dọn adapter và DI như một lần
tắt bình thường), nhưng có **hạn chót**. Quá hạn thì `os._exit()`.

Thô, và cố ý: tới được đó nghĩa là loop không chạy nữa, mà thứ duy nhất còn
đáng làm là **trả lại cổng**. Một lần tắt êm bị treo vô hạn thì vẫn là một con
mồ côi giữ cổng - đúng thứ module này sinh ra để xoá.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import sys
import threading
from typing import Any, Final

_log = logging.getLogger("xime.bootstrap")

#: Cho vòng tắt êm bao lâu trước khi cắt. Rộng hơn `_SHUTDOWN_GRACE` của cha
#: (10 giây) vì ở đây không còn ai đứng sau để dọn hộ nữa.
EXIT_GRACE_SECONDS: Final[float] = 15.0

#: Mã thoát khi phải cắt. 3 là quy ước "shutdown khẩn" quen thuộc, và quan
#: trọng hơn: nó **khác 0**, nên một lần cắt không bao giờ bị đọc thành một
#: lần tắt bình thường.
EXIT_CODE: Final[int] = 3


class OrphanGuard:
    """Canh cha ở một thread riêng; cha chết thì đưa tiến trình này đi theo."""

    def __init__(self, *, grace: float = EXIT_GRACE_SECONDS) -> None:
        self._grace = grace
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()

    def start(self) -> None:
        """Bắt đầu canh. Không có cha thì im lặng không làm gì.

        Không-có-cha là đường vào hợp lệ, không phải lỗi: chạy tay một tiến
        trình để gỡ lỗi, chạy trong test, chạy dưới một trình giám sát khác.
        """
        if self._thread is not None:
            return
        parent = multiprocessing.parent_process()
        if parent is None:
            return
        try:
            loop = asyncio.get_running_loop()
            task = asyncio.current_task()
        except RuntimeError:
            # Không có loop: không có gì để huỷ êm, và cũng chưa phục vụ ai.
            return
        if task is None:
            return
        self._thread = threading.Thread(
            target=self._wait,
            args=(parent, loop, task),
            name="xime-orphan-guard",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Thôi canh. Gọi lúc tắt êm, TRƯỚC khi cha có thể biến mất."""
        self._stopping.set()
        self._thread = None

    # ------------------------------------------------------------------

    def _wait(
        self,
        parent: Any,
        loop: asyncio.AbstractEventLoop,
        task: asyncio.Task[Any],
    ) -> None:
        # Chặn tới khi cha thoát. Không quét vòng, không đánh thức CPU.
        parent.join()
        if self._stopping.is_set():
            # Cha chết SAU khi mình đã bắt đầu tắt: đúng thứ tự của một lần tắt
            # bình thường, không có gì để báo.
            return
        _log.critical(
            "orphan guard: the supervisor (pid %s) is gone - this process is "
            "now an orphan holding a shared socket, so it is shutting down. "
            "Nothing will restart it; restart the cluster from main.py.",
            parent.pid,
        )
        # Hẹn giờ cắt TRƯỚC khi xin tắt êm: xin trước rồi hẹn sau thì một loop
        # đã treo không bao giờ chạy tới dòng hẹn giờ.
        killer = threading.Timer(self._grace, self._cut)
        killer.name = "xime-orphan-cut"
        killer.daemon = True
        killer.start()
        if not self._raise_stop_signal():
            # Không gửi được tín hiệu: huỷ task chính là đường lui. Ồn hơn -
            # uvicorn in ra một `CancelledError` của vòng lifespan - nhưng nó
            # vẫn dọn adapter và vẫn trả cổng.
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                # Loop đã đóng: không còn gì để tắt êm, để hạn chót lo.
                pass

    @staticmethod
    def _raise_stop_signal() -> bool:
        """Tự gửi cho mình đúng tín hiệu mà một lần tắt bình thường dùng.

        ⭐ Đây là lý do nó tốt hơn `task.cancel()`: nó **không mở một đường tắt
        thứ hai**. Cha tắt êm cũng gửi `SIGTERM`, uvicorn bắt nó trong
        `capture_signals()` và đặt `should_exit`, rồi `serve()` trả về theo
        đúng đường nó vẫn trả về. Con mồ côi vì vậy tắt **giống hệt** một con
        được cha bảo tắt - cùng một đường code, cùng một thứ tự dọn.

        Huỷ task thì khác: nó ném `CancelledError` vào giữa vòng lifespan của
        starlette, và uvicorn log nguyên một traceback mức `ERROR`. Việc dọn
        vẫn đúng, nhưng ngay dưới dòng `CRITICAL` vừa in thì một traceback đọc
        như *"tắt hỏng"*, trong khi nó đang tắt đúng.

        ⚠⚠ **Hai nền tảng, hai lệnh khác nhau, và đổi chỗ chúng thì hỏng im
        lặng.** Đây không phải chuyện khẩu vị:

        | | Dùng gì | Vì sao KHÔNG dùng cái kia |
        |---|---|---|
        | POSIX | `os.kill(getpid(), SIGTERM)` | `raise_signal()` gọi `raise()` của C, và `raise()` gửi cho **chính thread đang gọi** - tức thread canh này. Cờ được đặt, nhưng `epoll_wait` của thread chính **không bị ngắt**, nên handler của uvicorn có thể không chạy tới lúc hết hạn. Gửi cho *tiến trình* thì kernel giao cho thread không chặn tín hiệu, `EINTR` ngắt vòng chờ, handler chạy ngay |
        | Windows | `signal.raise_signal(SIGTERM)` | `os.kill()` ở đây **không** gửi tín hiệu - nó gọi thẳng `TerminateProcess`, tức giết ngay, mất sạch phần dọn êm. Đúng thứ hàm này sinh ra để tránh |

        Trả `False` khi không gửi được, để bên gọi dùng đường lui.
        """
        import signal

        try:
            if sys.platform == "win32":
                signal.raise_signal(signal.SIGTERM)
            else:
                os.kill(os.getpid(), signal.SIGTERM)
        except Exception:  # noqa: BLE001 - còn hạn chót lo phần còn lại
            return False
        return True

    def _cut(self) -> None:
        _log.critical(
            "orphan guard: graceful shutdown did not finish in %.0fs - exiting "
            "the hard way to release the port",
            self._grace,
        )
        # `os._exit`: không chạy handler `atexit`, không đợi thread nào. Tới
        # được đây nghĩa là đường tử tế đã thử và đã hỏng.
        os._exit(EXIT_CODE)
