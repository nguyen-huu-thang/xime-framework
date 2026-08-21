from __future__ import annotations

import re
import struct
import time
import weakref
import zlib
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Final, Generic, TypeVar

from ._env import LmdbEnvironment, is_map_full, is_map_resized
from ._errors import StoreError, StoreUnavailableError

T = TypeVar("T")

# TTL meaning "this entry never expires by itself".
# Positive infinity rather than a sentinel object because it needs no special
# case anywhere: `time.time() + NEVER` is still NEVER, and the "has it expired"
# comparison stays a single float compare.
# ⚠ NEVER is NOT the same as `ttl=None` at a call site, which means "use the
# table default" - two situations that make the caller do different things, so
# they are two different values.
# TTL nghĩa "bản ghi này không tự hết hạn". Dùng vô cực chứ không phải một
# sentinel vì nó không cần nhánh đặc biệt ở đâu cả.
# ⚠ NEVER KHÁC `ttl=None` ở lời gọi (nghĩa là "dùng mặc định của bảng").
NEVER: Final[float] = float("inf")

# One hour. A table that is never declared with a ttl still expires, because a
# store with no eviction and an unbounded table is a guaranteed leak - only a
# slow one. Opting out is possible, it just has to be written down (ttl=NEVER).
# Một tiếng. Bảng không khai ttl vẫn hết hạn, vì một kho không đuổi cộng một
# bảng không hạn là rò rỉ chắc chắn, chỉ là chậm. Thoát ra được, nhưng phải
# viết ra (ttl=NEVER).
DEFAULT_TTL: Final[float] = 3600.0

# Length of the absolute expiry stamp that prefixes every stored value.
_STAMP = struct.Struct("<d")
_STAMP_SIZE: Final[int] = _STAMP.size

# A table name becomes a directory name, so it must not be able to escape the
# configured store root.
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# How many times an operation is retried after the map was resized or filled.
# Small on purpose: each retry follows a real event (another process grew the
# file, or this one doubled it), and a loop that keeps finding new reasons is a
# symptom, not something to sit through.
_MAX_ATTEMPTS: Final[int] = 4


class _StoreRegistry:
    """Every Store instance built in THIS process, for the cleanup job to walk.

    Weak references on purpose: a Store is a DI singleton that lives as long as
    the process does, so the registry never needs to keep one alive, and a test
    that builds a dozen throwaway tables must not leak them.
    Tham chiếu yếu có chủ đích: Store là singleton DI sống suốt đời tiến trình
    nên registry không cần giữ nó sống, và một test dựng chục bảng tạm thì
    không được rò.

    This is a per-process read-only view of what the DI container already built,
    not shared state: every process rebuilds it identically from its own
    container, so it is not a debt against the parallelisation rule.
    Đây là bản sao đọc theo tiến trình của thứ DI container vốn đã dựng, không
    phải trạng thái chia sẻ: mọi tiến trình dựng lại y hệt từ container của
    chính nó, nên nó không phải nợ của luật song song hoá.
    """

    def __init__(self) -> None:
        self._instances: weakref.WeakSet[Store[Any]] = weakref.WeakSet()

    def add(self, store: Store[Any]) -> None:
        self._instances.add(store)

    def stores(self) -> list[Store[Any]]:
        """Snapshot of the live tables, sorted by name so sweeps are repeatable."""
        return sorted(self._instances, key=lambda s: s.name)

    def reset(self) -> None:
        """Forget every registered table. For tests - production never calls it."""
        self._instances.clear()


store_registry = _StoreRegistry()


def _validate_name(name: str, owner: str) -> str:
    if not isinstance(name, str) or not _NAME_PATTERN.match(name):
        raise StoreError(
            f"\nInvalid Store Name\n"
            f"  Class : {owner}\n"
            f"  Value : {name!r}\n"
            f"  Detail: the name becomes a directory under lmdb.path, so it must "
            f"start with a letter or digit and contain only letters, digits, "
            f"dot, dash or underscore."
        )
    return name


def _validate_ttl(ttl: float, owner: str) -> float:
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or ttl <= 0:
        raise StoreError(
            f"\nInvalid Store TTL\n"
            f"  Class   : {owner}\n"
            f"  Value   : {ttl!r}\n"
            f"  Expected: a positive number of seconds, or NEVER."
        )
    return float(ttl)


def _validate_parts(parts: int, owner: str) -> int:
    if isinstance(parts, bool) or not isinstance(parts, int) or parts < 1:
        raise StoreError(
            f"\nInvalid Store Partition Count\n"
            f"  Class   : {owner}\n"
            f"  Value   : {parts!r}\n"
            f"  Expected: an integer >= 1."
        )
    return parts


class Store(Generic[T], ABC):
    """An inter-process table on LMDB, for state with no durable source.

    Declare one by subclassing and passing its configuration as CLASS
    PARAMETERS, so configuration never shares a namespace with whatever the
    application adds to the body:

        class WebhookDedup(Store, name="webhook-dedup", ttl=86400):
            '''Bytes in, bytes out - the default.'''

        class PasskeyChallenge(Store[Challenge], name="passkey-challenge", ttl=300):
            def encode(self, value: Challenge) -> bytes: ...
            def decode(self, raw: memoryview) -> Challenge: ...

    Subclasses reach DI through `dependency.scan("app.infrastructure.store")`
    and are injected like a repository. The base classes stay abstract because
    `name` is an abstract property, so forgetting to declare `name` means the
    class never reaches DI - it fails at startup instead of quietly running as
    an unnamed table.
    Subclass vào DI qua `dependency.scan(...)` và được inject như một
    repository. Lớp nền vẫn abstract vì `name` là abstract property, nên quên
    khai `name` là class không vào DI - nổ lúc khởi động chứ không âm thầm chạy
    với một bảng không tên.

    ⚠ SELF-TEST before putting anything here: the store lives on tmpfs, so ask
    "the machine reboots and this table is empty - does the application still
    behave correctly?". If not, it belongs in a database. The word "database"
    inside the name LMDB is the single most common reason people get this wrong.
    ⚠ CÂU TỰ KIỂM trước khi đặt bất cứ gì vào đây: kho nằm trên tmpfs, nên hãy
    hỏi "máy khởi động lại, bảng này rỗng trơn - app có còn chạy đúng không?".
    Không thì nó thuộc database. Chữ "database" trong tên LMDB là lý do phổ
    biến nhất khiến người ta nhầm chỗ này.

    ⚠ Do not override __init__: the inherited one receives LmdbEnvironment from
    DI, and a subclass that replaces it loses that wiring.
    ⚠ Đừng override __init__: bản thừa kế nhận LmdbEnvironment từ DI.
    """

    # Filled in by __init_subclass__ from the class parameters. Declared here
    # only so type checkers and readers can see them.
    ttl: float = DEFAULT_TTL
    parts: int = 1

    @property
    @abstractmethod
    def name(self) -> str:
        """Table name, given as a class parameter. Also the directory name."""

    def __init_subclass__(
        cls,
        *,
        name: str | None = None,
        ttl: float = DEFAULT_TTL,
        parts: int = 1,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        if name is None:
            # An intermediate base (CounterStore itself, or an application's own
            # shared base) declares no name and stays abstract. That is the same
            # mechanism that catches a concrete table which forgot to declare one.
            # Lớp trung gian không khai name thì vẫn abstract - cùng cơ chế bắt
            # được một bảng thật sự quên khai tên.
            return
        cls.name = _validate_name(name, cls.__name__)  # type: ignore[assignment]
        cls.ttl = _validate_ttl(ttl, cls.__name__)
        cls.parts = _validate_parts(parts, cls.__name__)

    def __init__(self, env: LmdbEnvironment) -> None:
        self._env = env
        store_registry.add(self)

    # ------------------------------------------------------------------
    # Serialisation - overridden by Store[T] subclasses
    # ------------------------------------------------------------------

    def encode(self, value: T) -> bytes:
        """Turn a value into the bytes stored. Default: the value already is bytes."""
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise StoreError(
                f"{type(self).__name__}.encode received {type(value).__name__}, "
                f"but the plain Store only handles bytes. Declare the table as "
                f"Store[{type(value).__name__}] and implement encode()/decode()."
            )
        return bytes(value)

    def decode(self, raw: memoryview) -> T:
        """Turn stored bytes back into a value.

        `raw` is a view into the LMDB map and is only valid inside the read
        transaction the framework opens around this call, so an implementation
        must consume it here rather than keep it.
        `raw` là view vào vùng nhớ LMDB, chỉ hợp lệ bên trong giao dịch đọc mà
        framework mở quanh lời gọi này, nên implementation phải dùng ngay chứ
        không được giữ lại.
        """
        return bytes(raw)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, key: str) -> T | None:
        """Return the value under `key`, or None when absent or expired.

        Reading never touches the expiry stamp. That is not a detail: if a read
        refreshed the TTL then every read would be a WRITE, which would throw
        away the exact property LMDB was chosen for - readers never block and
        never take a lock - and turn a read-heavy table into a queue behind one
        write lock.
        Đọc không bao giờ đụng tới hạn. Đó không phải chi tiết: nếu đọc mà gia
        hạn thì mọi lần đọc thành một lần GHI, vứt đi đúng thứ đã chọn LMDB vì
        nó - người đọc không chặn ai, không giữ khoá - và biến một bảng đọc
        nhiều thành hàng đợi sau một khoá ghi.
        """
        raw_key = self._raw_key(key)

        def read(txn: Any) -> T | None:
            stored = txn.get(raw_key)
            if stored is None:
                return None
            if self._expired(stored):
                return None
            return self.decode(memoryview(stored)[_STAMP_SIZE:])

        return self._run(key, write=False, operation=read)

    async def set(self, key: str, value: T, ttl: float | None = None) -> None:
        """Store `value` under `key`, replacing any existing entry and its expiry.

        The expiry is an absolute instant, so a write REPLACES the old deadline
        instead of extending it: an entry with 10 seconds left, written with
        ttl=300, expires 300 seconds from now, not 310. Redis behaves the same
        way, so nobody has to learn a second rule.
        Hạn là một mốc tuyệt đối, nên lần ghi THAY hạn cũ chứ không cộng dồn.
        """
        payload = self.encode(value)
        raw_key = self._raw_key(key)
        blob = _STAMP.pack(self._deadline(ttl)) + payload

        def write(txn: Any) -> None:
            txn.put(raw_key, blob)

        self._run(key, write=True, operation=write)

    async def delete(self, key: str) -> None:
        """Remove `key`. Deleting a key that is not there is not an error."""
        raw_key = self._raw_key(key)

        def write(txn: Any) -> None:
            txn.delete(raw_key)

        self._run(key, write=True, operation=write)

    async def set_if_absent(self, key: str, value: T, ttl: float | None = None) -> bool:
        """Claim `key` only if it is free, returning True when this call claimed it.

        Atomic: LMDB gives one writer per file at a time, so two processes
        racing for the same key produce exactly one True. An entry that exists
        but has expired counts as free.
        Nguyên tử: LMDB cho đúng một người ghi trên mỗi file tại một thời điểm,
        nên hai tiến trình tranh cùng một khoá thì đúng một bên nhận True. Bản
        ghi tồn tại nhưng đã hết hạn được tính là trống.
        """
        payload = self.encode(value)
        raw_key = self._raw_key(key)
        blob = _STAMP.pack(self._deadline(ttl)) + payload

        def write(txn: Any) -> bool:
            stored = txn.get(raw_key)
            if stored is not None and not self._expired(stored):
                return False
            txn.put(raw_key, blob)
            return True

        return self._run(key, write=True, operation=write)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _raw_key(self, key: str) -> bytes:
        if not isinstance(key, str) or not key:
            raise StoreError(
                f"{type(self).__name__}: key must be a non-empty string, got {key!r}"
            )
        return key.encode("utf-8")

    def _partition(self, key: str) -> int:
        """Pick the file holding `key`.

        crc32, never hash(): Python randomises hash() per process, so four
        processes would compute four different files for the same key, each
        reading and writing consistently by its own logic, with nothing to
        report. That failure only appears once there are several processes -
        which is to say, never on a one-process development machine.
        crc32, KHÔNG BAO GIỜ hash(): Python ngẫu nhiên hoá hash() theo từng
        tiến trình, nên bốn tiến trình tính ra bốn file khác nhau cho cùng một
        khoá, mỗi tiến trình đọc ghi nhất quán theo logic của chính nó, không
        gì báo. Lỗi đó chỉ hiện khi có nhiều tiến trình, tức không bao giờ hiện
        trên máy dev một tiến trình.
        """
        if self.parts == 1:
            return 0
        return zlib.crc32(key.encode("utf-8")) % self.parts

    def _deadline(self, ttl: float | None) -> float:
        effective = self.ttl if ttl is None else _validate_ttl(ttl, type(self).__name__)
        return time.time() + effective

    @staticmethod
    def _expired(stored: Any) -> bool:
        deadline = _STAMP.unpack_from(stored, 0)[0]
        return deadline <= time.time()

    def _run(self, key: str, *, write: bool, operation: Callable[[Any], Any]) -> Any:
        """Run one transaction, recovering from the two resize errors.

        Both recoveries are retries rather than failures because both follow a
        legitimate event: another process grew the file (MapResized), or this
        file has no room and the store is allowed to double it (MapFull).
        Everything else from lmdb becomes StoreUnavailableError, so application
        code never imports lmdb to catch anything.
        Cả hai đều là thử lại chứ không phải lỗi, vì cả hai đi sau một sự kiện
        hợp lệ. Mọi thứ khác từ lmdb thành StoreUnavailableError, nên code ứng
        dụng không bao giờ phải import lmdb để bắt lỗi.
        """
        part = self._partition(key)
        table = self.name
        env = self._env.env_for(table, part, self.parts)
        file_path = self._env._file_path(table, part)  # noqa: SLF001 - same package

        last: BaseException | None = None
        for _ in range(_MAX_ATTEMPTS):
            try:
                # buffers=True hands back memoryviews instead of copies, which
                # is what lets decode() slice past the stamp without copying
                # the payload. The view dies with the transaction, hence
                # decode() being called inside it.
                # buffers=True trả memoryview thay vì bản sao - nhờ đó decode()
                # cắt qua phần header mà không copy payload. View chết cùng
                # giao dịch, nên decode() được gọi bên trong nó.
                with env.begin(write=write, buffers=True) as txn:
                    return operation(txn)
            except Exception as exc:  # noqa: BLE001 - narrowed immediately below
                last = exc
                if is_map_resized(exc):
                    self._env.adopt_external_size(env, file_path)
                    continue
                if write and is_map_full(exc):
                    self._env.grow(env, file_path)
                    continue
                if isinstance(exc, StoreError):
                    raise
                raise StoreUnavailableError(
                    f"store operation failed on table {table!r} "
                    f"(file {file_path}): {exc}"
                ) from exc

        raise StoreUnavailableError(
            f"store operation on table {table!r} did not settle after "
            f"{_MAX_ATTEMPTS} attempts (file {file_path}): {last}"
        )


class CounterStore(Store[int]):
    """A Store of integers, with an atomic increment.

    `incr` is declared here rather than on Store for a reason worth keeping:
    incrementing only means something for numbers, and putting it on a generic
    Store would be a contract promising more than it can keep for every other
    type. The type also lives in the base class name, so `get()` is typed
    `int | None` with no type parameter to write.
    `incr` đặt ở đây chứ không đặt trên Store vì một lý do đáng giữ: tăng chỉ
    có nghĩa với số, đặt nó lên một Store chung là hợp đồng hứa nhiều hơn thứ
    nó giữ được cho mọi kiểu khác.
    """

    def encode(self, value: int) -> bytes:
        if isinstance(value, bool) or not isinstance(value, int):
            raise StoreError(
                f"{type(self).__name__} stores integers, got {type(value).__name__}"
            )
        return value.to_bytes(8, "little", signed=True)

    def decode(self, raw: memoryview) -> int:
        return int.from_bytes(raw, "little", signed=True)

    async def incr(self, key: str, by: int = 1, ttl: float | None = None) -> int:
        """Add `by` to `key` and return the new value, atomically.

        A missing or expired entry counts as zero, so the first call returns
        `by`. Like every other write, this RESETS the expiry.
        Bản ghi chưa có hoặc đã hết hạn được tính là 0, nên lần gọi đầu trả về
        `by`. Như mọi lần ghi khác, lời gọi này ĐẶT LẠI hạn.

        ⚠ Do not keep counting while the caller is already locked out: since a
        write resets the expiry, every extra attempt would push the deadline
        further away and the lock would last forever. Check the threshold and
        return BEFORE calling incr - the login example in the documentation
        does exactly that, and it is not incidental.
        ⚠ Đừng đếm tiếp khi người dùng đang bị khoá: vì ghi là đặt lại hạn, mỗi
        lần thử thêm sẽ đẩy hạn ra xa và khoá kéo dài vô hạn. Kiểm ngưỡng và
        thoát TRƯỚC khi gọi incr.
        """
        if isinstance(by, bool) or not isinstance(by, int):
            raise StoreError(f"{type(self).__name__}.incr: `by` must be an int, got {by!r}")

        raw_key = self._raw_key(key)
        deadline = self._deadline(ttl)

        def write(txn: Any) -> int:
            stored = txn.get(raw_key)
            current = 0
            if stored is not None and not self._expired(stored):
                current = self.decode(memoryview(stored)[_STAMP_SIZE:])
            updated = current + by
            txn.put(raw_key, _STAMP.pack(deadline) + self.encode(updated))
            return updated

        return self._run(key, write=True, operation=write)
