from __future__ import annotations

import logging
import os
import shutil
import stat
from pathlib import Path
from typing import Any

from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException

from ._config import LmdbConfig
from ._errors import StoreFullError, StoreUnavailableError
from ._storage import human_size, inspect_storage

_log = logging.getLogger(__name__)


def _sieu_chat(path: Path, dich: int) -> None:
    """Hạ quyền của `path` xuống `dích` nếu nó đang RỘNG HƠN. Không bao giờ nới.

    Chỉ so bit, không so bằng: một tệp đang `0400` thì chặt hơn `0600`, và
    framework không có lý do gì kéo nó nới ra. Phép sửa này chỉ đi một chiều.

    ⭐ Vì sao phải sửa tệp CŨ chứ không chỉ tạo tệp mới cho đúng: bản vá chỉ áp
    cho tệp mới thì mọi cài đặt đang chạy **vẫn hở nguyên sau khi nâng cấp** -
    mà đó mới là chỗ có dữ liệu thật. Không có gì nhắc người vận hành, và kho
    thì cố ý sống qua lần restart nên nó sẽ không tự tạo lại.

    Trên Windows `chmod` gần như không có tác dụng; ở đó hàm này im lặng không
    làm gì, và đó là đúng - quyền POSIX không phải mô hình bảo mật của nó.
    """
    if os.name == "nt":
        return
    try:
        hien = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return
    thua = hien & ~dich
    if not thua:
        return
    try:
        os.chmod(path, hien & dich)
    except OSError as exc:
        _log.warning(
            "store: cannot tighten %s from %s to %s: %s. Anyone able to read "
            "this path can read rate-limit counters and passkey challenges.",
            path, oct(hien), oct(hien & dich), exc,
        )
        return
    _log.info(
        "store: tightened %s from %s to %s (lmdb.file_mode / lmdb.dir_mode). "
        "It was created before this framework version, which did not set a mode.",
        path, oct(hien), oct(hien & dich),
    )

# Name of the marker file that records how many partitions a table was created
# with. See _check_parts() for why it exists.
# Tên file đánh dấu ghi lại bảng được tạo với bao nhiêu phần. Xem _check_parts().
_PARTS_MARKER = ".parts"


def _import_lmdb() -> Any:
    """Import lmdb on first use, with an actionable message when it is absent.

    Lazy on purpose, exactly like the redis / s3 / mail / mqtt starters: an
    application that never scans this package must not pay for a C extension it
    does not use, and must not fail to start because of it.
    Import lười có chủ đích, y hệt các starter redis / s3 / mail / mqtt: app
    không dùng thì không phải trả giá cho một extension C nó không cần, và
    không được vì nó mà không khởi động nổi.
    """
    try:
        import lmdb
    except ImportError:
        raise RuntimeError(
            "The Xime store requires lmdb. Run: pip install 'xime[lmdb]'"
        ) from None
    return lmdb


class LmdbEnvironment:
    """Owns every LMDB file the process has opened, and the memory budget.

    One instance per process, registered in DI by scanning
    "xime.starters.lmdb". Store subclasses receive it through their inherited
    constructor, so application code never touches lmdb directly.
    Một instance cho mỗi tiến trình, vào DI khi scan "xime.starters.lmdb".
    Subclass của Store nhận nó qua constructor thừa kế, nên code ứng dụng không
    bao giờ chạm thẳng vào lmdb.

    Environments are opened LAZILY, on the first read or write of a table. Two
    reasons, and both are rules rather than preferences: an LMDB environment
    does not survive fork (each process must open its own), and post_construct
    is forbidden from claiming resources so that a process which never uses a
    table never opens its file.
    Environment mở LƯỜI, ở lần đọc/ghi đầu tiên của một bảng. Hai lý do, đều là
    luật chứ không phải sở thích: environment LMDB không sống sót qua fork (mỗi
    tiến trình phải tự mở), và post_construct bị cấm chiếm tài nguyên, nên tiến
    trình nào không dùng một bảng thì không mở file của bảng đó.
    """

    def __init__(self, runtime: RuntimeConfig) -> None:
        self._config = LmdbConfig.resolve(runtime)
        # Keyed by the partition file path, so two tables never share an entry.
        self._envs: dict[str, Any] = {}
        self._sizes: dict[str, int] = {}
        self._checked_tables: set[str] = set()
        self._announce_location()

    def _announce_location(self) -> None:
        """Nói kho đang nằm trên cái gì, và chặn nếu `total_max` là lời hứa giả.

        ⚠ Chạy trong `__init__` chứ không chờ lần mở đầu tiên: đây là **đo**,
        không phải **chiếm** - `disk_usage()` và `/proc/mounts` không tạo gì,
        không mở gì, nên nó không phạm luật "không chiếm tài nguyên lúc dựng
        DI". Đổi lại, một máy cấu hình sai chết **lúc khởi động** thay vì lúc
        bảng đầu tiên đầy, và hai thời điểm đó cách nhau hàng tuần.

        Dòng log tồn tại vì *"kho ở `/dev/shm/app-store`"* mang **hai nghĩa**
        (mất khi reboot / sống qua reboot) mà không gì tách ra - đúng luật 03.
        """
        report = inspect_storage(self._config.path)
        free = (
            human_size(report.free_bytes) if report.free_bytes is not None else "unknown"
        )
        _log.info(
            "store: %s (%s) - %s free, total_max=%s",
            self._config.path,
            report.label,
            free,
            human_size(self._config.total_max),
        )

        if report.free_bytes is None or self._config.total_max <= report.free_bytes:
            return

        # `total_max` là lời hứa "kho được phép chiếm bấy nhiêu". Hệ tệp không
        # giữ nổi thì lời hứa đó là giả, và trên tmpfs nó **không vỡ bằng chậm
        # đi mà bằng OOM kill cả tiến trình** - VPS thường không có swap. Chặn
        # ở đây tốn một dòng YAML; để nó chạy tiếp tốn một lần chết lúc 3 giờ
        # sáng, ở một tiến trình không ai ngờ tới.
        raise StartupException(
            "\nStore Budget Exceeds The Filesystem\n"
            f"  Config    : lmdb.total_max = {human_size(self._config.total_max)}\n"
            f"  Path      : {self._config.path}\n"
            f"  Filesystem: {report.measured_at} ({report.label})\n"
            f"  Free      : {free}\n"
            "  Detail    : total_max promises the store may grow to that size. "
            "This filesystem cannot honour it"
            + (
                ", and on RAM-backed storage the promise breaks as an OOM kill "
                "of the whole process, not as a slowdown.\n"
                if report.ram_backed
                else ".\n"
            )
            + "  Fix       : lower lmdb.total_max, or give the store a larger "
            "filesystem\n"
            "              (systemd: RuntimeDirectorySize= · Docker: --shm-size)."
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def config(self) -> LmdbConfig:
        return self._config

    def allocated_bytes(self) -> int:
        """Total map size currently reserved across every open partition."""
        return sum(self._sizes.values())

    # ------------------------------------------------------------------
    # Opening
    # ------------------------------------------------------------------

    def env_for(self, table: str, part: int, parts: int) -> Any:
        """Return the LMDB environment holding `part` of `table`, opening it if needed."""
        key = self._file_path(table, part)
        env = self._envs.get(key)
        if env is not None:
            return env

        if table not in self._checked_tables:
            self._check_parts(table, parts)
            self._checked_tables.add(table)

        return self._open(key)

    def _file_path(self, table: str, part: int) -> str:
        return str(Path(self._config.path) / table / f"{part}.mdb")

    def _open(self, file_path: str) -> Any:
        lmdb = _import_lmdb()
        size = self._config.map_size
        self._reserve(file_path, size)
        thu_muc = Path(file_path).parent
        thu_muc.mkdir(mode=self._config.dir_mode, parents=True, exist_ok=True)
        # `mode=` của mkdir bị umask che VÀ không tác động tới thư mục đã tồn
        # tại, nên chmod tường minh - cùng lý do như localfs.
        _sieu_chat(thu_muc, self._config.dir_mode)
        try:
            # subdir=False keeps one partition in one file, which is what makes
            # "N files per table" readable on disk. sync/metasync off: this
            # store holds data that is allowed to vanish on reboot (see the
            # self-test in the Store docstring), so paying for durability would
            # buy something nobody asked for.
            # subdir=False giữ mỗi phần trong một file - đó là thứ làm cho "N
            # file mỗi bảng" nhìn được trên đĩa. sync/metasync tắt: kho này giữ
            # dữ liệu được phép mất khi máy khởi động lại, nên trả giá cho tính
            # bền là mua thứ không ai đặt.
            env = lmdb.open(
                file_path,
                subdir=False,
                map_size=size,
                sync=False,
                metasync=False,
                max_dbs=0,
                lock=True,
                # Without this, python-lmdb defaults to 0o755 and the file lands
                # at 0644 - world readable, in a directory the docs point at
                # /dev/shm (mode 1777). Measured, audit 0.8 finding C1.
                # Thiếu dòng này thì python-lmdb lấy mặc định 0o755 và tệp ra
                # 0644 - ai cũng đọc được, trong thư mục mà tài liệu trỏ tới
                # /dev/shm (mode 1777). Đo được, phát hiện C1 của kiểm toán 0.8.
                mode=self._config.file_mode,
            )
        except lmdb.Error as exc:
            self._sizes.pop(file_path, None)
            raise StoreUnavailableError(f"cannot open store file {file_path}: {exc}") from exc

        # Tệp do bản framework CŨ tạo vẫn mang quyền cũ - `mode=` chỉ áp cho
        # lần tạo. Hạ chúng xuống, kể cả tệp khoá đi kèm.
        _sieu_chat(Path(file_path), self._config.file_mode)
        _sieu_chat(Path(file_path + "-lock"), self._config.file_mode)

        self._envs[file_path] = env
        _log.debug(
            "store: opened %s (map_size=%d B, total allocated=%d B)",
            file_path,
            size,
            self.allocated_bytes(),
        )
        return env

    def _check_parts(self, table: str, parts: int) -> None:
        """Drop the table if it was created with a different partition count.

        A key lives in the file `crc32(key) % parts` selects, so changing
        `parts` between two runs puts every existing key in the wrong file. The
        symptom would be `get()` returning None more often than usual - which
        looks exactly like a cold cache, and would never be traced back to
        here. Losing the table once is the cheap half of that trade.
        Một khoá nằm ở file do `crc32(key) % parts` chọn, nên đổi `parts` giữa
        hai lần chạy là đặt mọi khoá cũ vào sai file. Triệu chứng sẽ là `get()`
        trả None nhiều hơn bình thường - trông y hệt một cache lạnh, và không
        ai lần ngược về được tới đây. Mất bảng một lần là nửa rẻ của đánh đổi.
        """
        table_dir = Path(self._config.path) / table
        marker = table_dir / _PARTS_MARKER

        recorded: int | None = None
        if marker.is_file():
            try:
                recorded = int(marker.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                recorded = None  # unreadable marker is treated as a mismatch

        if recorded == parts:
            # Đường thoát sớm này là đường ĐI QUA MỖI LẦN MỞ trong đời sống
            # bình thường của một kho - marker chỉ được ghi lại khi `parts`
            # đổi, tức gần như không bao giờ. Nên nếu chỉ hạ quyền ở nhánh ghi
            # thì marker của kho cũ **không bao giờ được sửa**. Đo được
            # 2026-08-21: mọi tệp khác về 0600 còn `.parts` ở lại 0644.
            _sieu_chat(marker, self._config.file_mode)
            return

        if table_dir.exists() and recorded != parts:
            if recorded is not None or any(table_dir.iterdir()):
                _log.warning(
                    "store: table %r was created with parts=%s but the code now "
                    "declares parts=%d - dropping and recreating it. Every key "
                    "of this table is lost once.",
                    table,
                    recorded if recorded is not None else "unknown",
                    parts,
                )
                # ⛔ ĐỔI TÊN rồi mới xoá, không xoá tại chỗ.
                #
                # Đổi `parts` là sự kiện lúc TRIỂN KHAI, tức đúng lúc N tiến
                # trình cùng khởi động và cùng chạy đoạn này. Xoá tại chỗ thì
                # tiến trình A có thể đang xoá trong khi B đã tạo file mới bên
                # trong cùng thư mục - và `ignore_errors=True` nuốt trọn mọi va
                # chạm nên **không có triệu chứng nào**. Phát hiện T6 của kiểm
                # toán 0.8.
                #
                # `os.rename` trên cùng một hệ tệp là nguyên tử: đúng MỘT tiến
                # trình đổi được tên, những tiến trình còn lại nhận
                # `FileNotFoundError` và đi tiếp để tạo thư mục mới. Sau lúc
                # đó, mọi file mới sinh ra đều nằm trong thư mục MỚI.
                cu = table_dir.with_name(f"{table_dir.name}.cu-{os.getpid()}")
                try:
                    os.rename(table_dir, cu)
                except FileNotFoundError:
                    pass  # tiến trình khác vừa dọn - đúng ý, đi tiếp
                except OSError as exc:
                    raise StartupException(
                        f"\nCannot Recreate Store Table\n"
                        f"  Table : {table}\n"
                        f"  Path  : {table_dir}\n"
                        f"  Detail: {exc}\n"
                        f"  Fix   : the table must be dropped because `parts` "
                        f"changed, but this process cannot move the old "
                        f"directory out of the way. Stop every process using "
                        f"this store and remove the directory by hand."
                    ) from exc
                else:
                    shutil.rmtree(cu, ignore_errors=True)

        table_dir.mkdir(mode=self._config.dir_mode, parents=True, exist_ok=True)
        _sieu_chat(table_dir, self._config.dir_mode)
        # `write_text` mở bằng 0o666 & ~umask -> 0644. Mở tường minh với quyền
        # đích ngay từ đầu, không chmod sau: chmod sau để hở một cửa sổ mà
        # tiến trình khác đọc được.
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, self._config.file_mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(str(parts))
        _sieu_chat(marker, self._config.file_mode)

    # ------------------------------------------------------------------
    # Growing
    # ------------------------------------------------------------------

    def _reserve(self, file_path: str, new_size: int) -> None:
        """Account `new_size` for `file_path`, refusing to cross `lmdb.total_max`."""
        current = self._sizes.get(file_path, 0)
        projected = self.allocated_bytes() - current + new_size
        if projected > self._config.total_max:
            _log.critical(
                "store: refusing to allocate %d B for %s - the store would hold "
                "%d B, over the lmdb.total_max limit of %d B. Raise "
                "lmdb.total_max, or reduce lmdb.map_size / the number of parts.",
                new_size,
                file_path,
                projected,
                self._config.total_max,
            )
            raise StoreFullError(
                f"store is full: allocating {new_size} B for {file_path} would "
                f"bring the total to {projected} B, over lmdb.total_max="
                f"{self._config.total_max} B"
            )
        self._sizes[file_path] = new_size

    def grow(self, env: Any, file_path: str) -> None:
        """Double the map size of one partition after a MapFullError.

        Doubling is logged at WARNING every time: the store never evicts, so a
        file that keeps growing is telling you either that `lmdb.map_size` was
        declared too small or that entries are being written faster than their
        TTL retires them. Both deserve a look, and neither is visible otherwise.
        Mỗi lần nới đều log WARNING: kho này không bao giờ tự nhường chỗ, nên
        một file cứ phình lên là dấu hiệu hoặc `lmdb.map_size` khai quá nhỏ,
        hoặc tốc độ ghi vượt tốc độ hết hạn. Cả hai đều đáng nhìn, và không có
        cách nào khác để thấy.
        """
        lmdb = _import_lmdb()
        current = self._sizes.get(file_path, self._config.map_size)
        new_size = current * 2
        self._reserve(file_path, new_size)
        try:
            env.set_mapsize(new_size)
        except lmdb.Error as exc:
            self._sizes[file_path] = current
            raise StoreUnavailableError(f"cannot grow store file {file_path}: {exc}") from exc
        _log.warning(
            "store: grew %s from %d B to %d B (total allocated=%d B of %d B)",
            file_path,
            current,
            new_size,
            self.allocated_bytes(),
            self._config.total_max,
        )

    def adopt_external_size(self, env: Any, file_path: str) -> None:
        """Re-map after another process grew this file (MapResizedError).

        set_mapsize(0) means "take whatever size the file says it is now",
        which is the documented recovery for this error. It must be reachable
        from every entry point into the store, reads included: the error is
        raised by whichever transaction happens to span the moment another
        process grew the file, and reads are the majority of transactions.
        set_mapsize(0) nghĩa là "lấy đúng cỡ file đang khai", đó là cách phục
        hồi chuẩn cho lỗi này. Nó phải với tới được từ MỌI đường vào kho, kể cả
        đường đọc: lỗi này ném ra ở bất cứ giao dịch nào tình cờ bắc qua thời
        điểm tiến trình khác nới file, mà đọc mới là phần đông giao dịch.
        """
        lmdb = _import_lmdb()
        try:
            env.set_mapsize(0)
        except lmdb.Error as exc:
            raise StoreUnavailableError(
                f"cannot re-map store file {file_path} after an external resize: {exc}"
            ) from exc
        info = env.info()
        self._sizes[file_path] = int(info["map_size"])
        _log.info(
            "store: re-mapped %s to %d B after another process grew it",
            file_path,
            self._sizes[file_path],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def pre_destroy(self) -> None:
        """Close every open environment. Safe to call when none were opened."""
        for file_path, env in list(self._envs.items()):
            try:
                env.close()
            except Exception:
                # Teardown stays best-effort, but a failure is never hidden:
                # a file that would not close is worth a line in the log.
                _log.exception("store: error while closing %s", file_path)
        self._envs.clear()
        self._sizes.clear()
        self._checked_tables.clear()


def is_map_full(exc: BaseException) -> bool:
    """True when `exc` is LMDB's "this file has no room left" error."""
    lmdb = _import_lmdb()
    return isinstance(exc, lmdb.MapFullError)


def is_map_resized(exc: BaseException) -> bool:
    """True when `exc` means another process grew the file under us."""
    lmdb = _import_lmdb()
    return isinstance(exc, lmdb.MapResizedError)
