from __future__ import annotations

import re
from dataclasses import dataclass

from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException

# 64 MiB per partition file, 1 GiB across the whole store.
# Deliberately modest rather than generous: on Windows an LMDB file is
# allocated for real the moment it is opened, so a roomy default would cost a
# developer machine hundreds of megabytes for an empty store. A VPS operator
# who needs more raises both numbers in one place and sees the total logged at
# startup.
# Cố ý khiêm tốn chứ không rộng tay: trên Windows file LMDB bị cấp phát THẬT
# ngay lúc mở, nên mặc định rộng sẽ ngốn hàng trăm MB trên máy dev cho một kho
# rỗng. Người vận hành VPS cần hơn thì nâng cả hai ở một chỗ, và thấy tổng đang
# cấp trong log lúc khởi động.
DEFAULT_MAP_SIZE = 64 * 1024 * 1024
DEFAULT_TOTAL_MAX = 1024 * 1024 * 1024

_SIZE_UNITS = {
    "": 1,
    "B": 1,
    "K": 1024,
    "KB": 1024,
    "KIB": 1024,
    "M": 1024**2,
    "MB": 1024**2,
    "MIB": 1024**2,
    "G": 1024**3,
    "GB": 1024**3,
    "GIB": 1024**3,
}

_SIZE_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$")


def parse_size(value: object, where: str) -> int:
    """Turn `64MB` / `1 GiB` / `67108864` into a byte count.

    Accepting units is not decoration: a byte count large enough to matter is
    also large enough to mistype, and `67108864` in a YAML file tells a reader
    nothing. Anything unrecognisable stops startup rather than silently
    becoming a default, because a store sized by accident is a store that fills
    up at an hour nobody chose.
    Chấp nhận đơn vị không phải để trang trí: một con số byte đủ lớn để có ý
    nghĩa thì cũng đủ lớn để gõ nhầm, và `67108864` trong YAML không nói gì với
    người đọc. Giá trị không hiểu được thì chặn khởi động chứ không âm thầm rơi
    về mặc định, vì một kho được cấp cỡ do nhầm lẫn là một kho sẽ đầy vào giờ
    không ai chọn.
    """
    if isinstance(value, bool):  # bool is an int subclass - reject it explicitly
        raise StartupException(
            f"\nInvalid Size Value\n"
            f"  Config: {where}\n"
            f"  Value : {value!r}\n"
            f"  Detail: expected a size such as 64MB, 1GiB or a byte count."
        )
    if isinstance(value, int):
        size = value
    elif isinstance(value, str):
        match = _SIZE_PATTERN.match(value)
        unit = match.group(2).upper() if match else None
        if match is None or unit not in _SIZE_UNITS:
            raise StartupException(
                f"\nInvalid Size Value\n"
                f"  Config  : {where}\n"
                f"  Value   : {value!r}\n"
                f"  Expected: a number with an optional unit "
                f"(B, KB, MB, GB), e.g. 64MB"
            )
        size = int(float(match.group(1)) * _SIZE_UNITS[unit])
    else:
        raise StartupException(
            f"\nInvalid Size Value\n"
            f"  Config: {where}\n"
            f"  Value : {value!r}\n"
            f"  Detail: expected a size such as 64MB, 1GiB or a byte count."
        )

    if size <= 0:
        raise StartupException(
            f"\nInvalid Size Value\n"
            f"  Config: {where}\n"
            f"  Value : {value!r}\n"
            f"  Detail: the size must be greater than zero."
        )
    return size


@dataclass(frozen=True)
class LmdbConfig:
    """Operational settings for the store, read from `lmdb:` in YAML.

    ⚠ Khối mang tên BACKEND (`lmdb:`), không mang tên khái niệm (`store:`), và
    đó là quyết định có cân nhắc - chốt 2026-08-20 sau khi đã thử chiều ngược
    lại rồi bỏ:

    - `store:` đứng cạnh `storage:` (kho file/blob) trong cùng một file YAML,
      **khác nhau hai chữ cái mà là hai hệ thống con không liên quan gì nhau**.
      Tệ hơn bẫy `process`/`processes`: hai cái kia là cùng một khái niệm ở hai
      số lượng, nhầm thì lạc sang thứ gần bên.
    - `storage:` tách `storage.local` / `storage.s3` **vì nó có Protocol và
      nhiều backend**. `Store` thì cố ý KHÔNG có Protocol và chỉ một backend,
      nên không có tầng khái niệm nào để lơ lửng bên trên.
    - `redis:` đã là một khối mang tên backend cho một kho KV khác. `lmdb:`
      nhất quán với nó.

    Only three keys, and all three are things an operator genuinely knows:
    where the store lives, how big one file starts, and how much memory the
    whole store may take. Everything else about a table - its name, its TTL,
    how many files it is split across - belongs to the developer and is
    declared as class parameters on the Store subclass.
    Chỉ ba khoá, và cả ba đều là thứ người vận hành thật sự biết: kho nằm ở
    đâu, một file bắt đầu ở cỡ nào, và cả kho được phép chiếm bao nhiêu bộ nhớ.
    Mọi thứ khác của một bảng - tên, hạn, chia mấy file - thuộc về lập trình
    viên và khai bằng tham số class trên subclass của Store.
    """

    path: str
    map_size: int = DEFAULT_MAP_SIZE
    total_max: int = DEFAULT_TOTAL_MAX

    @classmethod
    def resolve(cls, runtime: RuntimeConfig) -> LmdbConfig:
        """Build the config from `store.*`, failing fast on a missing path.

        `path` has NO default on purpose. This machine runs 31 Xime codebases
        side by side, and unlike the bus - whose shared-memory names carry a
        random per-run id - the store deliberately survives a restart, so its
        name has to be stable. A stable default would therefore be the SAME
        directory for every application on the box: two services would share
        one rate limiter and one deduplication table, each overwriting keys the
        other believes it owns, with nothing to hint at it. Refusing to guess
        costs one line of YAML and removes that failure mode entirely.
        `path` cố ý KHÔNG có mặc định. Máy này chạy 31 codebase Xime cạnh nhau,
        và khác với bus (tên vùng nhớ mang mã lần chạy ngẫu nhiên), kho cố ý
        sống qua lần restart nên tên phải ổn định. Một mặc định ổn định vì vậy
        sẽ là CÙNG MỘT thư mục cho mọi app trên máy: hai service dùng chung một
        bảng hãm nhịp và một bảng chống lặp, mỗi bên đè khoá mà bên kia tin là
        của mình, không dấu hiệu nào. Từ chối đoán tốn một dòng YAML và xoá hẳn
        cách hỏng đó.
        """
        raw = runtime.get("lmdb")
        if not isinstance(raw, dict):
            raw = {}

        path = raw.get("path")
        if not isinstance(path, str) or not path.strip():
            raise StartupException(
                "\nMissing LMDB Store Path\n"
                "  Config: lmdb.path\n"
                "  Detail: the inter-process store needs a directory of its own, "
                "and the framework will not pick one for you: several Xime "
                "services share this machine, and a shared default directory "
                "would silently mix their tables.\n"
                "  Fix   : add to application.yml, e.g.\n"
                "            lmdb:\n"
                "              path: /dev/shm/<your-service>-store   # Linux: RAM\n"
                "              path: runtime/store                   # Windows dev\n"
                "  Or    : run `xime config --print` to see every key and its default."
            )

        return cls(
            path=path.strip(),
            map_size=parse_size(raw.get("map_size", DEFAULT_MAP_SIZE), "lmdb.map_size"),
            total_max=parse_size(raw.get("total_max", DEFAULT_TOTAL_MAX), "lmdb.total_max"),
        )
