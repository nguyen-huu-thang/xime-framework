"""Hạ tầng dùng chung mà cha cấp trước khi sinh con, và trao xuống cho con.

```text
CHA:  bind socket  ->  CẤP VÙNG NHỚ CHUNG  ->  sinh con (kèm SharedHandle)
CON:                   ATTACH vùng nhớ     ->  import config, dựng DI
```

Ba thứ đi chung một chuyến, vì cả ba đều phải có **trước khi** con tồn tại:

| | |
|---|---|
| **`RefData`** | bảng tham chiếu, con `attach` theo mã lần chạy |
| **`ProcessLink`** | bus, cộng **kênh điều khiển `__xime__`** cha dùng để nói với con |
| **Nhịp watchdog** | một ô 8 byte cho mỗi tiến trình |

⭐ **Cấp trước khi dựng DI, và đó là bắt buộc chứ không phải tối ưu:** vùng nhớ
chung phải có **một người cấp trước**, mà tiến trình gốc thì **không dựng DI**.
Nó chỉ có class trong tay, nên `name` và `max_bytes` phải đọc được từ class -
đó là lý do chúng là **tham số class** và là lý do `configure_refdata()` tồn
tại thay vì chỉ `dependency.scan`.

### ⭐ Đánh số: con là `0..N-1` theo thứ tự cấu hình, **cha là `N`**

Một con được dựng lại **giữ nguyên** chỉ số của nó, vì chỉ số đến từ thứ tự khai
trong `processes:` chứ không phải thứ tự sinh. Suy từ thứ tự sinh thì con dựng
lại nhận một chỉ số khác, và `nguoi_ghi` trong bảng hoá ra trỏ vào một tiến trình
không còn tồn tại.

Cha lấy ô **cuối cùng** thay vì ô 0 vì nó là người đến sau về mặt khái niệm: cụm
có `N` chỗ làm việc, cộng một chỗ cho người trông. Đặt cha ở 0 thì mọi chỉ số con
lệch một so với thứ tự cấu hình, và cái lệch một đó phải nhớ ở năm chỗ.

### Vì sao `SharedHandle` đi bằng ĐỐI SỐ, không bằng biến môi trường

`XIME_PROCESS_ID` đi bằng biến môi trường vì con cần biết nó **trước mọi lệnh
import** (`config/` chạy trước khi framework giành lại quyền điều khiển). Mã
lần chạy thì khác: nó chỉ cần lúc **attach**, sau khi import xong. Và đối số có
hai cái được mà biến môi trường không có:

| | |
|---|---|
| Chở được thứ không phải chuỗi | **semaphore của bus** không đi qua biến môi trường được |
| **Vắng mặt mang đúng một nghĩa** | *"không có cha"* - và đó là ca chạy tay một tiến trình để gỡ lỗi. Biến môi trường thì sót lại từ lần chạy trước được |

Ô thứ nhất từ giả thuyết thành sự thật ở giai đoạn 6: `ProcessLink.bells` là một
tuple `multiprocessing.Semaphore`, và nó chỉ qua được ranh giới tiến trình khi đi
trong `Process(args=...)`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiprocessing import synchronize

    from xime.core.link import ChannelSpec, ProcessLink
    from xime.core.refdata import RefDataArena

    from ._watchdog import Heartbeats

_log = logging.getLogger("xime.bootstrap")


@dataclass(frozen=True)
class SharedHandle:
    """Thứ cha trao cho một tiến trình con để gắn vào hạ tầng dùng chung.

    Là một dataclass chứ không phải sáu đối số rời để giai đoạn sau thêm được
    thứ mới mà **không đổi chữ ký** của `run_as_worker` lần nữa. Nó đã trả công
    ngay ở giai đoạn 6: ba trường mới, không đụng vào đường gọi.

    Attributes:
        refdata_run_id: mã lần chạy của kho tham chiếu, `None` khi ứng dụng
            không khai bảng nào.
        index: chỉ số của tiến trình này trong cụm - `0..N-1` theo đúng thứ tự
            khai trong `processes:`. Cha giữ `N`.
        slots: tổng số ô của cụm, tức `N + 1`. Con cần nó để dựng đúng bố cục
            vùng nhớ chung (bố cục phụ thuộc số tiến trình).
        link_id: mã lần chạy của bus, `None` khi cha không cấp được.
        link_bells: chuông của mọi ô, theo đúng thứ tự chỉ số.
        beat_run_id: mã lần chạy của bảng nhịp watchdog.
        primary: tiến trình này có giữ vai primary lúc khởi động không.
            ⭐ **Cha quyết, không phải cấu hình.** Cấu hình chỉ nói ai *bắt đầu*
            với vai đó; sau lần thăng cấp đầu tiên thì cha là nguồn sự thật duy
            nhất, vì chỉ nó biết ai còn sống. Thiếu trường này thì một primary
            đã chết, được dựng lại, quay về **vẫn tin mình là primary** trong khi
            cha đã trao vai cho người khác - hai primary cùng chạy job nền, và
            không gì báo.
    """

    refdata_run_id: str | None = None
    index: int = 0
    slots: int = 1
    primary: bool = False
    link_id: str | None = None
    link_bells: tuple[synchronize.Semaphore, ...] = ()
    beat_run_id: str | None = None
    channels: dict[str, ChannelSpec] = field(default_factory=dict)


class SharedMemoryOwner:
    """Những vùng nhớ chung mà **cha** cấp và giữ sống suốt lần chạy.

    ⚠ Cha phải **giữ** chúng, không chỉ tạo rồi buông: trên Windows vùng nhớ
    biến mất khi handle cuối cùng đóng, nên buông sớm là con thứ hai không
    attach được nữa - và nó hỏng đúng lúc một con bị dựng lại, tức lâu sau khi
    mọi thứ trông đã chạy tốt.
    """

    def __init__(
        self,
        refdata: RefDataArena | None,
        link: ProcessLink | None = None,
        beats: Heartbeats | None = None,
        *,
        slots: int = 1,
        supervisor_index: int = 0,
        beat_run_id: str | None = None,
    ) -> None:
        self._refdata = refdata
        self._link = link
        self._beats = beats
        self._slots = slots
        self._supervisor_index = supervisor_index
        self._beat_run_id = beat_run_id

    @property
    def link(self) -> ProcessLink | None:
        """Bus của cha. Cha dùng nó làm **kênh điều khiển**, không dùng DI."""
        return self._link

    @property
    def beats(self) -> Heartbeats | None:
        return self._beats

    @property
    def supervisor_index(self) -> int:
        return self._supervisor_index

    def handle_for(self, index: int, *, primary: bool = False) -> SharedHandle:
        from xime.core.link import link_registry

        return SharedHandle(
            refdata_run_id=self._refdata.run_id if self._refdata else None,
            index=index,
            primary=primary,
            slots=self._slots,
            link_id=self._link.link_id if self._link else None,
            link_bells=self._link.bells if self._link else (),
            beat_run_id=self._beat_run_id if self._beats else None,
            channels=link_registry.channels() if self._link else {},
        )

    def close(self) -> None:
        # Dọn theo thứ tự ngược với lúc cấp, và **mỗi cái một `try`**: một vùng
        # nhớ không trả được không được phép chặn hai vùng còn lại.
        for label, closer in (
            ("beats", self._beats),
            ("link", self._link),
            ("refdata", self._refdata),
        ):
            if closer is None:
                continue
            try:
                closer.close()
            except Exception:  # noqa: BLE001 - dọn dẹp phải best-effort
                _log.warning("supervisor: could not release %s", label, exc_info=True)
        self._beats = None
        self._link = None
        self._refdata = None


def allocate_shared_memory(child_count: int) -> SharedMemoryOwner:
    """Cấp mọi hạ tầng dùng chung cho cả cụm. **Chỉ tiến trình gốc gọi.**

    `child_count` là số con, nên cụm có `child_count + 1` ô - cha giữ ô cuối.

    ⚠ Không khai bảng `RefData` nào thì **không cấp** vùng nào cho nó, và đó
    không phải một tối ưu vụn: trên Windows bộ nhớ chung bị **cấp phát thật**
    ngay lúc tạo, nên cấp cho một thứ không ai dùng là mất RAM thật suốt cả lần
    chạy.

    ⭐ Bus thì **luôn cấp**, kể cả khi ứng dụng không khai kênh nào: kênh nội bộ
    `__xime__` là chốt chặn thăng cấp primary, và một chốt chặn không được phụ
    thuộc một thành phần **tuỳ chọn** - nó sẽ vắng mặt đúng lúc cần nhất.
    """
    from xime.core.link import ProcessLink, link_registry
    from xime.core.refdata import RefDataArena, refdata_registry, specs_of

    from ._watchdog import Heartbeats

    slots = child_count + 1
    supervisor_index = child_count

    arena: RefDataArena | None = None
    classes = refdata_registry.classes()
    if classes:
        specs = specs_of(classes)  # type: ignore[arg-type]
        # Cha cấp nhưng **không phải người ghi**: primary là một tiến trình CON.
        arena = RefDataArena.create(specs, index=supervisor_index, primary=False)
        _log.info(
            "refdata: allocated %d table(s) for run %s: %s",
            len(specs),
            arena.run_id,
            ", ".join(spec.name for spec in specs),
        )

    link: ProcessLink | None = None
    beats: Heartbeats | None = None
    try:
        # Cha giữ ô CUỐI, không phải ô 0 - xem ghi chú đánh số ở đầu file.
        link = ProcessLink.create(
            link_registry.channels(), slots, index=supervisor_index
        )
        _log.info(
            "link: allocated %d channel(s) for run %s across %d slot(s)",
            len(link_registry.channels()),
            link.link_id,
            slots,
        )
        beats = Heartbeats.create(link.link_id, slots)
    except BaseException:
        if link is not None:
            link.close()
        if arena is not None:
            arena.close()
        raise

    return SharedMemoryOwner(
        arena,
        link,
        beats,
        slots=slots,
        supervisor_index=supervisor_index,
        beat_run_id=link.link_id,
    )
