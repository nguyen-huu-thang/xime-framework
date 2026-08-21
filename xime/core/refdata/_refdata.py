from __future__ import annotations

import asyncio
import logging
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Final, Generic, TypeVar

from ._arena import RefDataArena
from ._errors import (
    RefDataClosedError,
    RefDataNotReadyError,
    RefDataNotWriterError,
    RefDataTooLargeError,
    RefDataTornError,
)
from ._layout import FLAG_STALE, NEVER_PUBLISHED, NO_WRITER, RefDataLayout
from ._stats import RefDataStats

T = TypeVar("T")

_log = logging.getLogger("xime.refdata")

# 64 KB: đủ cho một tập khoá JWT hay một danh bạ app cỡ vừa, và nhân đôi (hai
# bản) vẫn là 128 KB - không đáng kể ngay cả trên Windows, nơi bộ nhớ chung bị
# cấp phát THẬT lúc khởi động.
DEFAULT_MAX_BYTES: Final[int] = 64 * 1024

# Trần số vòng đọc lặp lại trước khi ném.
#
# ⭐ Trần này **không phải để xử lý ca thường**: có hai bản A/B nên người đọc và
# người ghi gần như không bao giờ đụng nhau, và lặp quá một vòng đã là chuyện
# hiếm. Nó tồn tại vì **không có trần thì một lỗi lạ biến thành request treo vô
# hạn, không log, không triệu chứng**. Có trần thì nó thành một ngoại lệ chỉ
# đúng chỗ.
MAX_SPINS: Final[int] = 100

# Cảnh báo khi bản vừa publish chiếm quá ngần này phần trần.
# ⭐ **Đây là lớp thật sự cứu**, vì nó báo TRƯỚC. Hai lớp còn lại (nổ khi vượt,
# và cờ `stale`) chỉ nói cho biết chuyện đã rồi.
_FULL_WARN_RATIO: Final[float] = 0.8

# Nhịp hỏi lại trong `wait_ready`. Ngắn vì nó chỉ chạy ở tầng khởi động, và mỗi
# vòng là đúng một phép đọc số nguyên trong bộ nhớ chung.
_WAIT_POLL_SECONDS: Final[float] = 0.01

# Tên bảng trở thành tên vùng nhớ chung nên nó phải sống được ở đó.
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_name(name: str, owner: str) -> str:
    if not isinstance(name, str) or not _NAME_PATTERN.match(name) or len(name) > 64:
        raise ValueError(
            f"\nInvalid RefData Name\n"
            f"  Class : {owner}\n"
            f"  Value : {name!r}\n"
            f"  Detail: the name becomes part of a shared-memory name, so it "
            f"must start with a letter or digit, contain only letters, digits, "
            f"dot, dash or underscore, and be at most 64 characters."
        )
    return name


def _validate_max_bytes(value: int, owner: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(
            f"\nInvalid RefData max_bytes\n"
            f"  Class   : {owner}\n"
            f"  Value   : {value!r}\n"
            f"  Expected: a positive integer number of bytes.\n"
            f"  Detail  : the shared block is 2 x max_bytes plus a header, "
            f"because two versions are kept so a reader never sees a half "
            f"written one."
        )
    return value


class RefData(Generic[T], ABC):
    """Dữ liệu tham chiếu dùng chung giữa các tiến trình của một ứng dụng.

    Dành cho thứ **có nguồn bền vững**: khoá JWT lấy từ Trust, danh bạ app,
    cấu hình đã phân giải. Đọc rất nhiều, ghi rất hiếm, và mỗi lần ghi là
    **thay trọn gói**. Mất thì nạp lại được.

    Khai một bảng bằng cách kế thừa và truyền cấu hình bằng **THAM SỐ CLASS**,
    để cấu hình không bao giờ nằm chung không gian tên với thứ ứng dụng thêm
    vào thân class:

        class JwtKeyRefData(RefData[JwtKeySet], name="jwt-keys", max_bytes=65536):
            def encode(self, value: JwtKeySet) -> bytes:
                return msgpack.packb(value.to_dict())

            def decode(self, raw: memoryview) -> JwtKeySet:
                return JwtKeySet.from_dict(msgpack.unpackb(raw))

    Rồi khai nó ở `config/` để tiến trình gốc cấp được vùng nhớ **trước khi**
    dựng DI:

        # config/refdata.py
        from xime.core.refdata import configure_refdata

        from app.refdata.jwt_keys import JwtKeyRefData

        configure_refdata([JwtKeyRefData])

    Sau đó inject thẳng, có kiểu:

        class TrustKeyProvider:
            def __init__(self, keys: JwtKeyRefData) -> None:
                self._keys = keys

            def resolve(self, kid: str | None) -> Sequence[KeyContext]:
                return self._keys.read_or_fail().resolve(kid)

    ### Ba luật phải nhớ

    | | |
    |---|---|
    | **`publish()` CHỈ primary** | Cơ chế hai bản chỉ đúng với đúng một người ghi. Tiến trình khác gọi thì **nổ** |
    | **`read()` trả `None` = CHƯA SẴN SÀNG** | Khác hẳn *tập rỗng*. Đợi thì đợi ở tầng khởi động bằng `wait_ready()`, ⛔ **`read()` không tự chờ** - chờ trong `read()` là treo request |
    | ⚠ **Object trả về là DÙNG CHUNG, không được sửa** | Sửa nó là sửa bản của mọi người trong tiến trình này. Framework **không chặn** - cùng ranh giới đã chốt cho `read_only()` ở 0.6.3: chặn được thì phải trả phí runtime cho mọi lời đọc |

    ⚠ **Đừng override `__init__`**: bản thừa kế nhận `RefDataArena` từ DI, và
    lớp con thay nó là mất chỗ nối dây đó.
    """

    # Điền bởi `__init_subclass__` từ tham số class. Khai ở đây chỉ để công cụ
    # kiểm kiểu và người đọc nhìn thấy chúng.
    max_bytes: int = DEFAULT_MAX_BYTES

    @property
    @abstractmethod
    def name(self) -> str:
        """Tên bảng, truyền bằng tham số class. Cũng là tên vùng nhớ chung."""

    def __init_subclass__(
        cls,
        *,
        name: str | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        if name is None:
            # Lớp trung gian (một lớp nền dùng chung của ứng dụng) không khai
            # tên thì vẫn abstract - cùng cơ chế bắt được một bảng thật sự quên
            # khai tên, và bắt nó bằng cách **không cho vào DI** chứ không phải
            # bằng một dòng cảnh báo.
            return
        cls.name = _validate_name(name, cls.__name__)  # type: ignore[assignment]
        cls.max_bytes = _validate_max_bytes(max_bytes, cls.__name__)

    def __init__(self, arena: RefDataArena) -> None:
        self._arena = arena
        self._layout = RefDataLayout(self.max_bytes)
        self._block = arena.block(self.name)
        self._view: memoryview | None = self._block.buf
        arena.track(self)
        # Cache L1 trong RAM riêng của tiến trình, khoá bằng SỐ ĐỜI.
        self._cached: T | None = None
        self._cached_generation = NEVER_PUBLISHED
        # `_warned_full` cố ý VẪN là thuộc tính instance: nó chỉ là chốt chống
        # lặp log, và chỉ primary mới chạy tới nhánh đặt nó. Một primary mới
        # được thăng cấp cảnh báo lại một lần là ĐÚNG, không phải thừa.
        self._warned_full = False

    # ------------------------------------------------------------------
    # Tuần tự hoá - lớp con override
    # ------------------------------------------------------------------

    def encode(self, value: T) -> bytes:
        """Biến giá trị thành bytes. Mặc định: giá trị đã là bytes sẵn."""
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"{type(self).__name__}.encode received {type(value).__name__}, "
                f"but the plain RefData only handles bytes. Declare the table as "
                f"RefData[{type(value).__name__}] and implement encode()/decode()."
            )
        return bytes(value)

    def decode(self, raw: memoryview) -> T:
        """Biến bytes đã lưu thành giá trị.

        ⚠ `raw` là **bản chép riêng của lượt đọc này**, không phải view vào bộ
        nhớ chung: `read()` chép ra trước rồi mới xác nhận số đời, vì xác nhận
        sau khi đã decode thì có lúc decode phải bản đang bị ghi đè.
        """
        return bytes(raw)  # type: ignore[return-value]

    def encode_segments(self, value: T) -> Sequence[bytes]:
        """Cắt bản mới thành các đoạn. Mặc định: **một đoạn**.

        ⏭ v1 chỉ dùng một đoạn, nhưng hình dạng được khai từ v1 theo đúng chốt
        của thiết kế: nếu v1 làm một vùng liền thì ngày cần nhiều đoạn là đổi
        cấu trúc vùng nhớ, tức đổi cách **mọi** tiến trình đọc.
        """
        return (self.encode(value),)

    def decode_segments(self, chunks: Sequence[memoryview]) -> T:
        """Ghép các đoạn thành giá trị. Mặc định: một đoạn thì gọi `decode()`.

        ⭐ Lớp con nào có nhiều đoạn phải **đọc theo dòng** (`msgpack` có
        `unpacker.feed(chunk)`), đừng nối các đoạn lại trước: nối thành một
        `bytes` liền là **một lần copy toàn bộ** - vứt đi chính thứ việc chia
        đoạn đang cố giữ.
        """
        if len(chunks) == 1:
            return self.decode(chunks[0])
        raise NotImplementedError(
            f"{type(self).__name__} published {len(chunks)} segments but does "
            f"not override decode_segments(). Feed the chunks to a streaming "
            f"decoder instead of joining them."
        )

    # ------------------------------------------------------------------
    # Đọc
    # ------------------------------------------------------------------

    def read(self) -> T | None:
        """Bản đang dùng, hoặc `None` khi **chưa ai publish lần nào**.

        ⚠ `None` mang **đúng một** nghĩa - *chưa sẵn sàng*. Một bản đã publish
        mà nội dung rỗng thì trả về **object rỗng**, không phải `None`. Lẫn hai
        thứ đó là mở ra một cửa sổ lúc khởi động mà request xác thực bị **từ
        chối oan, hoặc tệ hơn là được cho qua**.

        ⚠ Object trả về **dùng chung trong tiến trình, không được sửa**.

        ⭐ Đường thường lệ chạy 99,99% số lần là **một phép so số nguyên**: số
        đời chưa đổi thì trả thẳng object trong cache, không đọc dữ liệu, không
        decode, không copy.
        """
        layout, view = self._layout, self._require_view()
        for _ in range(MAX_SPINS):
            first = layout.read_generation(view)
            if first == NEVER_PUBLISHED:
                return None
            if first == self._cached_generation:
                return self._cached  # <- đường thường lệ, một phép so
            slot = layout.read_pointer(view)
            segments = layout.read_segments(view)
            # Chép ra TRƯỚC khi xác nhận số đời. Xác nhận sau khi đã decode thì
            # có lúc phải decode một ô đang bị ghi đè, và lỗi đó ra dưới dạng
            # một exception msgpack ngẫu nhiên vài tháng một lần.
            chunk = bytes(layout.slot_view(view, slot))
            if layout.read_generation(view) != first:
                continue  # người ghi vừa đổi bản giữa chừng - đọc lại
            if segments != 1:
                raise RefDataTornError(
                    f"refdata {self.name!r} reports {segments} segments but "
                    f"this version of Xime writes exactly one."
                )
            value = self.decode_segments((memoryview(chunk),))
            self._cached = value
            self._cached_generation = first
            return value
        raise RefDataTornError(
            f"refdata {self.name!r}: gave up after {MAX_SPINS} attempts to read "
            f"a consistent version. With two slots a reader and a writer should "
            f"almost never collide, so this points at a writer stuck mid-publish."
        )

    def read_or_fail(self) -> T:
        """Như `read()`, nhưng chưa có bản nào thì **ném**.

        Dùng ở chỗ mà *chưa sẵn sàng* là lỗi thật sự - ví dụ trong một handler
        chạy sau khi tầng khởi động đã `wait_ready()`. Đúng cặp
        `find()` / `find_or_fail()` của `CrudRepository`.
        """
        value = self.read()
        if value is None:
            raise RefDataNotReadyError(
                f"refdata {self.name!r} has no version yet - nobody has called "
                f"publish(). Wait for it at startup with "
                f"await {type(self).__name__}.wait_ready(timeout), or handle "
                f"the None branch of read()."
            )
        return value

    @property
    def generation(self) -> int:
        """Số đời hiện tại. **0 nghĩa là chưa ai publish lần nào.**"""
        return self._layout.read_generation(self._require_view())

    async def wait_ready(self, timeout: float) -> T:
        """Chờ tới khi có bản đầu tiên, rồi trả nó về.

        ⛔ **`read()` cố ý KHÔNG tự chờ** - chờ trong `read()` là treo một
        request. Chỗ đúng để gọi hàm này là **tầng khởi động**: tiến trình chưa
        nhận request cho tới khi những bảng bắt buộc đã sẵn sàng.

        ⚠ **`timeout` bắt buộc, không có mặc định vô hạn.** Primary có thể chết
        trước khi kịp publish, và chờ vô hạn là treo cả tiến trình mà không ai
        biết vì sao.

        📌 Nó **hỏi lại theo nhịp** chứ không chờ một tín hiệu: mỗi vòng là một
        phép đọc số nguyên trong bộ nhớ chung, và nó chỉ chạy ở tầng khởi động
        nên độ trễ tối đa là một nhịp. Đổi lại, nó **không phụ thuộc thứ tự
        khởi động của bất cứ thành phần nào khác** - một chốt chặn không nên
        dựa vào một thành phần có thể chưa kịp chạy.
        """
        deadline = time.monotonic() + timeout
        while True:
            value = self.read()
            if value is not None:
                return value
            if time.monotonic() >= deadline:
                raise RefDataNotReadyError(
                    f"refdata {self.name!r} was still empty after {timeout:g}s. "
                    f"The primary process publishes it; check that it started "
                    f"and that publishing did not fail (see stats().stale)."
                )
            await asyncio.sleep(_WAIT_POLL_SECONDS)

    # ------------------------------------------------------------------
    # Ghi
    # ------------------------------------------------------------------

    async def publish(self, value: T) -> int:
        """Thay trọn gói bản đang dùng. **Chỉ primary gọi được.**

        Trả về số đời mới.

        Bất biến ở đây là một câu, không phải sáu bước:

        > **Mọi thứ mô tả bản mới phải hiện ra TRƯỚC khi số đời tăng.**

        Người đọc dùng **số đời** để xác nhận nó đọc được một bản nhất quán,
        nên tăng số đời trước khi con trỏ, độ dài và số đoạn đã đúng là mời
        người đọc tin vào một bản chưa xong.

        ⚠ Vượt trần thì **ném và giữ nguyên bản cũ**: một bản cũ đúng còn hơn
        một bản mới rách.
        """
        if not self._arena.primary:
            raise RefDataNotWriterError(
                f"refdata {self.name!r}: publish() was called from a "
                f"non-primary process. Two writers filling the spare slot at "
                f"the same time corrupt it silently, so only the primary "
                f"publishes; every process reads."
            )
        # `encode` trong executor: msgpack một dict lớn tốn mili giây, và nó
        # hiếm nên chi phí chuyển tầng không đáng kể. Phần memcpy thì chạy
        # thẳng - nó nhanh hơn cả một lần chuyển tầng.
        segments = await asyncio.to_thread(self.encode_segments, value)
        return self._write(segments)

    def _write(self, segments: Sequence[bytes]) -> int:
        layout, view = self._layout, self._require_view()
        if len(segments) != 1:
            raise RefDataTooLargeError(
                f"refdata {self.name!r}: encode_segments() returned "
                f"{len(segments)} segments, but this version of Xime writes "
                f"exactly one. Raise max_bytes instead."
            )
        payload = segments[0]
        if len(payload) > self.max_bytes:
            layout.set_flag(view, FLAG_STALE, True)
            _log.critical(
                "refdata %r: a new version of %d bytes does not fit in the "
                "declared max_bytes=%d, so THE WHOLE CLUSTER KEEPS USING THE "
                "OLD ONE and no request will fail until something depends on "
                "the new one. Raise max_bytes.",
                self.name,
                len(payload),
                self.max_bytes,
            )
            raise RefDataTooLargeError(
                f"refdata {self.name!r}: {len(payload)} bytes exceeds the "
                f"declared max_bytes={self.max_bytes}. The previous version is "
                f"untouched and still served."
            )

        target = 1 - layout.read_pointer(view)
        layout.write_slot(view, target, payload)
        layout.write_length(view, target, len(payload))
        layout.write_segments(view, len(segments))
        layout.write_written_at(view, time.monotonic_ns())
        layout.write_writer(view, self._arena.index)
        layout.write_pointer(view, target)  # 1 byte, nguyên tử
        generation = layout.read_generation(view) + 1
        layout.write_generation(view, generation)  # <- SAU CÙNG

        layout.set_flag(view, FLAG_STALE, False)
        self._warn_if_nearly_full(len(payload))
        return generation

    def _warn_if_nearly_full(self, used: int) -> None:
        ratio = used / self.max_bytes
        if ratio >= _FULL_WARN_RATIO and not self._warned_full:
            self._warned_full = True
            _log.warning(
                "refdata %r is at %.0f%% of its declared max_bytes=%d. This is "
                "the layer that actually saves you: once a version does not "
                "fit, the cluster silently keeps serving the old one.",
                self.name,
                ratio * 100,
                self.max_bytes,
            )
        elif ratio < _FULL_WARN_RATIO:
            self._warned_full = False

    # ------------------------------------------------------------------
    # Quan sát
    # ------------------------------------------------------------------

    def stats(self) -> RefDataStats:
        """Ảnh chụp **gần đúng** - nó đọc trong lúc người khác có thể đang ghi."""
        layout, view = self._layout, self._require_view()
        generation = layout.read_generation(view)
        written_at = layout.read_written_at(view)
        writer = layout.read_writer(view)
        return RefDataStats(
            name=self.name,
            generation=generation,
            served_generation=self._cached_generation,
            written_at_ms=(
                None
                if generation == NEVER_PUBLISHED or written_at == 0
                else (time.monotonic_ns() - written_at) // 1_000_000
            ),
            used_bytes=layout.read_length(view, layout.read_pointer(view)),
            limit_bytes=self.max_bytes,
            segments=layout.read_segments(view),
            writer=None if writer == NO_WRITER else writer,
            # Đọc từ VÙNG NHỚ CHUNG, không đọc thuộc tính instance: mọi tiến
            # trình phải trả lời được câu "dữ liệu tôi đang phục vụ có cũ
            # không", kể cả tiến trình không phải primary.
            stale=bool(layout.read_flags(view) & FLAG_STALE),
        )

    # ------------------------------------------------------------------
    # Nội bộ
    # ------------------------------------------------------------------

    def _require_view(self) -> memoryview:
        if self._view is None:
            raise RefDataClosedError(
                f"refdata {self.name!r} was released because the arena is "
                f"closed - the application is shutting down, or a test kept a "
                f"table alive past the fixture that owns its memory."
            )
        return self._view

    def release(self) -> None:
        """Buông vùng nhớ chung. **Framework gọi lúc tắt máy.**

        ⚠ **Đo lại 2026-08-20: nó KHÔNG phải để tránh `BufferError`.** Giả
        thiết ban đầu là *"`SharedMemory.close()` ném khi còn view chưa thả"*;
        thử thật thì `close()` chạy êm, vì `self._view` chính là buffer của
        `SharedMemory` chứ không phải một **lát cắt** của nó - và chỉ lát cắt
        mới tính là export. `read()` thì chép ra rồi buông lát cắt ngay trong
        cùng một biểu thức, nên không bao giờ có lát cắt sống sót.

        Lý do thật, và nó vẫn đáng giữ: **thông báo lỗi**. Không buông thì gọi
        `read()` sau khi tắt cho một `ValueError: operation forbidden on
        released memoryview` - đúng loại lỗi không ai lần ra được nguyên nhân.
        Buông rồi thì nó nói thẳng là arena đã đóng.
        """
        self._view = None
        self._cached = None
        self._cached_generation = NEVER_PUBLISHED
