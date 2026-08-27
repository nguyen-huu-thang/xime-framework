"""Bề mặt cấu hình của framework, mô tả một lần cho **ba** lệnh dùng chung.

```text
_config_spec.py
      ├─ xime config --print   -> YAML có chú thích, ra stdout
      ├─ xime check config     -> đối chiếu file của app, bắt khoá gõ sai
      └─ xime init             -> cây thư mục + file cơ bản
```

⚠⚠ **Một bản mô tả viết tay cũng già đi** - đúng loài lỗi mà file cấu hình sinh
sẵn mắc phải, chỉ lùi lên một tầng. Nên ở đây có hai lớp chống:

| Lớp | Làm gì |
|---|---|
| **Suy từ pydantic** | Khối nào đã có model (`server`, `grpc`, `logging`) thì đọc thẳng `model_fields`: mặc định và kiểu **không thể lệch** với code đọc chúng |
| **Test canh** | `runtime.get("<khối>")` trong `xime/` mà không có mặt ở đây thì test đỏ |

⭐ **`complete` là công tắc chống kêu oan.** Chỉ khối nào tự khai đã liệt kê đủ
khoá mới được `xime check config` báo *"khoá lạ"*. Một bản mô tả thiếu mà lại đi
tố khoá hợp lệ là phép dò sẽ bị tắt trong tuần đầu, và lúc đó nó không bắt được
gì nữa.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Hình dạng
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Key:
    """Một khoá lá trong `application.yml`."""

    name: str
    default: Any = None
    doc: str = ""

    required: bool = False
    """Framework **không đoán** giá trị này - thiếu là chặn khởi động."""

    placeholder: str | None = None
    """Giá trị `xime init` ghi ra. `{project}` được thay bằng tên dự án.

    ⭐ Chỉ khoá `required` mới cần: đó đúng là tập *"framework không mặc định
    được, nên phải nằm trong file"*. Mọi khoá khác đi ra dưới dạng chú thích để
    mặc định của framework vẫn chảy tới app cũ khi nâng cấp.
    """

    children: tuple[Key, ...] = ()


@dataclass(frozen=True)
class Block:
    """Một khối gốc trong `application.yml`."""

    name: str
    doc: str

    model: str | None = None
    """`"module:Class"` của một pydantic model - suy khoá từ đó thay vì viết tay."""

    keys: tuple[Key, ...] = field(default_factory=tuple)

    complete: bool = False
    """Danh sách khoá đã đủ, nên `check config` được phép báo khoá lạ."""

    init_keys: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)
    """Khoá mà **`xime init` mở sẵn** dù framework có mặc định cho nó.

    Dạng `(tên, giá trị YAML, chú thích)`. Khác `Key.required` ở một điểm cốt
    lõi: `required` nghĩa là *framework KHÔNG đoán được* - thiếu là chặn khởi
    động. Còn đây nghĩa là *framework đoán được, nhưng một dự án MỚI nên bắt
    đầu từ một giá trị khác*.

    Có mặt để giải đúng một chuyện: dự án `xime init` sinh ra nghe trên
    `0.0.0.0` ngay lần chạy đầu, và file cấu hình có ba dòng chú thích cẩn thận
    về TLS rồi in `host: "0.0.0.0"` **không một chữ** nói nó nghĩa là *"máy khác
    trong mạng gọi tới được"*. Phát hiện T13 của kiểm toán 0.8.

    ⚠ Chỉ tác động tới file `xime init` GHI RA. `xime config --print` vẫn in
    mặc định thật của framework, và **31 ứng dụng hiện có không đổi hành vi** -
    chúng không chạy lại trình tạo.
    """

    needs: str | None = None
    """Extra phải cài để khối này có nghĩa, ví dụ `xime[lmdb]`."""

    see: str | None = None
    """Trang tài liệu nói kỹ hơn."""


@dataclass(frozen=True)
class ResolvedBlock:
    """Một khối đã phân giải xong, hoặc lý do không phân giải được."""

    block: Block
    keys: tuple[Key, ...]
    unavailable: str | None = None
    """⭐ Kết cục thứ ba: *"chưa đọc được"* tách hẳn khỏi *"không có khoá nào"*."""


# ---------------------------------------------------------------------------
# Suy khoá từ pydantic
# ---------------------------------------------------------------------------


def _from_model(dotted: str) -> tuple[Key, ...]:
    module_name, _, class_name = dotted.partition(":")
    module = importlib.import_module(module_name)
    return _fields_of(getattr(module, class_name))


def _fields_of(model: Any) -> tuple[Key, ...]:
    from pydantic import BaseModel

    out: list[Key] = []
    for name, info in model.model_fields.items():
        annotation = info.annotation
        nested = (
            isinstance(annotation, type)
            and issubclass(annotation, BaseModel)
            and annotation is not model
        )
        if nested:
            out.append(Key(name, doc=info.description or "", children=_fields_of(annotation)))
            continue
        default = info.default
        if default is Ellipsis:  # pydantic dùng `...` cho trường bắt buộc
            out.append(Key(name, doc=info.description or "", required=True))
            continue
        out.append(Key(name, default=default, doc=info.description or ""))
    return tuple(out)


def resolve(block: Block) -> ResolvedBlock:
    """Lấy danh sách khoá của một khối, không bao giờ ném ra ngoài.

    ⚠ Import lười và bắt lỗi rộng có chủ ý: `grpc`, `mqtt`, `opcua` nằm sau các
    extra, và một máy chưa cài `xime[opcua]` vẫn phải chạy được `xime config
    --print`. Nhưng *"không import được"* **không** được in ra như *"khối này
    rỗng"* - nó đi vào `unavailable`.
    """
    if block.model is None:
        return ResolvedBlock(block, block.keys)
    try:
        return ResolvedBlock(block, _from_model(block.model))
    except Exception as exc:  # noqa: BLE001 - thiếu extra là chuyện bình thường
        return ResolvedBlock(block, (), unavailable=f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Bề mặt
# ---------------------------------------------------------------------------

SPEC: tuple[Block, ...] = (
    Block(
        name="logging",
        doc=(
            "Root logging applied at bootstrap. Without this block the root\n"
            "logger sits at WARNING with no handler, so every INFO line is\n"
            "swallowed and a healthy app looks hung. An app that configures\n"
            "logging itself always wins."
        ),
        model="xime.core.config.runtime:LoggingConfig",
        complete=True,
    ),
    Block(
        name="server",
        doc=(
            "Network binding for the HTTP adapter. An empty `ssl` block means\n"
            "plain HTTP. The certificate must come from a public CA (certbot):\n"
            "browsers do not trust an internal CA."
        ),
        model="xime.adapters.web._server_config:WebServerConfig",
        complete=True,
        see="docs/configuration.md",
        init_keys=(
            (
                "host",
                '"127.0.0.1"',
                "127.0.0.1 = only this machine can reach the app.\n"
                'The framework default is "0.0.0.0", which means EVERY network\n'
                "interface - anyone who can route to this machine can call it.\n"
                "That is the right answer inside a container and the wrong one\n"
                "on a laptop or a shared box. `xime init` starts you on the\n"
                "narrow side; widen it deliberately.",
            ),
        ),
    ),
    Block(
        name="grpc",
        doc=(
            "Port and mTLS for the gRPC server.\n"
            "NOTE: this block also carries the gRPC CLIENT SDK settings\n"
            "(`grpc.clients`), read by a different module, so the list below is\n"
            "not the whole story."
        ),
        model="xime.adapters.grpc._config:GrpcServerConfig",
        see="docs/grpc-codefirst.md",
    ),
    Block(
        name="cors",
        doc=(
            "CORS for the web adapter. Only has an effect when config/*.py calls\n"
            "`configure_cors()` without arguments - explicit arguments win."
        ),
        keys=(
            Key("allow_origins", default="[]"),
            Key("allow_origin_regex", default=None),
            Key("allow_methods", default='["GET"]'),
            Key("allow_headers", default="[]"),
            Key("expose_headers", default="[]"),
            Key("allow_credentials", default=False),
            Key("max_age", default=600),
        ),
        complete=True,
        see="docs/routing.md",
    ),
    Block(
        name="lmdb",
        doc=(
            "Inter-process store for state with NO durable source: rate limits,\n"
            "passkey challenges, replay protection. Scope: ONE machine.\n"
            "The block is named after the backend rather than `store:` on\n"
            "purpose - `store` would sit next to `storage` (the file/blob store)\n"
            "and two unrelated subsystems would differ by two letters."
        ),
        keys=(
            Key(
                "path",
                required=True,
                placeholder="/dev/shm/{project}-store",
                doc=(
                    "A directory of its own. There is NO default: several Xime\n"
                    "services share one machine, and a fixed default would be the\n"
                    "SAME directory for all of them - two services overwriting each\n"
                    "other's tables, silently.\n"
                    "On Linux, put it on tmpfs (`/dev/shm/...`, or `/run/<service>`\n"
                    "via systemd RuntimeDirectory=) and the store lives in RAM.\n"
                    "WARNING: on tmpfs the contents are LOST on reboot."
                ),
            ),
            Key(
                "map_size",
                default="64MB",
                doc="Ceiling for ONE partition file. A full partition doubles itself.",
            ),
            Key(
                "total_max",
                default="1GiB",
                doc=(
                    "Ceiling for the WHOLE store. Exceeding the free space of the\n"
                    "target filesystem stops startup: on tmpfs that promise breaks\n"
                    "as an OOM kill, not as a slowdown."
                ),
            ),
            Key(
                "file_mode",
                default='"0600"',
                doc="Quote it, as with socket.permission. POSIX only.",
            ),
            Key(
                "dir_mode",
                default='"0700"',
                doc="Quote it, same reason. POSIX only.",
            ),
        ),
        complete=True,
        needs="xime[lmdb]",
        see="docs/store.md",
    ),
    Block(
        name="socket",
        doc=(
            "Unix domain socket adapter. POSIX only.\n"
            "NOTE: the socket PATH is not set here. It comes from\n"
            "`process.socket.<server_id>.path`, or is derived as\n"
            "<dir>/<server_id>.sock. A `socket.path` key would be read\n"
            "by nobody."
        ),
        keys=(
            Key(
                "dir",
                doc=(
                    "Base directory for auto-named *.sock files.\n"
                    "Left out, the first writable default dir is used."
                ),
            ),
            Key(
                "permission",
                default='"0600"',
                doc="Quote it: YAML reads an unquoted 0600 as decimal 600.",
            ),
            Key("owner", default=None, doc="chown to this user, by name."),
            Key("group", default=None, doc="chown to this group, by name."),
            Key("allowed_uids", default="[]", doc="SO_PEERCRED allowlist. [] means any UID."),
            Key("session_timeout", default=30.0, doc="Seconds; an idle session is dropped."),
            Key(
                "max_chunk_size",
                default=1024 * 1024,
                doc="Bytes; a larger chunk is refused.",
            ),
            Key(
                "recv_queue_size",
                default=16,
                doc="Buffered chunks per session before backpressure.",
            ),
        ),
        complete=True,
        see="docs/socket-adapter.md",
    ),
    Block(
        name="xime",
        doc="Switches belonging to the framework itself.",
        keys=(
            Key(
                "dev",
                default=False,
                doc="On: this is a development environment. Serves the API docs.",
            ),
            Key(
                "di",
                children=(
                    Key(
                        "dynamic-binding",
                        default=False,
                        doc="On: one interface may bind several impls, swappable at runtime.",
                    ),
                ),
            ),
        ),
        complete=True,
        see="docs/architecture.md",
        init_keys=(
            (
                "dev",
                "true",
                "One switch for every development-only surface. Today it decides\n"
                "whether /docs, /redoc and /openapi.json are served at all.\n"
                "The framework default is false, so a deployment that never sets it\n"
                "serves no API documentation. That is deliberate: a schema is a\n"
                "complete map of the API and should not be readable by whoever can\n"
                "reach the port.\n"
                "This file is your own machine's (.gitignore keeps it out of git);\n"
                "the copy you deploy from should leave this off."
            ),
        ),
    ),
    # ------------------------------------------------------------------
    # Khối do starter/adapter đọc, CHƯA liệt kê đủ khoá ở đây.
    # ⚠ `complete=False` nên `check config` không tố khoá lạ trong chúng - thà
    # bỏ sót còn hơn kêu oan một khoá hợp lệ.
    # ------------------------------------------------------------------
    Block(
        name="database",
        doc="SQLAlchemy starter: connection string and pool.",
        keys=(
            Key(
                "url",
                required=True,
                placeholder="postgresql+asyncpg://user:pass@localhost/{project}",
            ),
        ),
        see="docs/starters.md",
    ),
    Block(
        name="redis",
        doc=(
            "Redis backend for CacheService - the one place meant for state that\n"
            "SEVERAL MACHINES must share. Everything the framework provides\n"
            "itself (RefData, Store, ProcessLink) is one machine, always."
        ),
        keys=(
            Key(
                "url",
                required=True,
                placeholder="redis://localhost:6379/0",
                doc="Only read when the application scans xime.starters.redis.",
            ),
            Key("max_connections", default=10),
        ),
        complete=True,
        needs="xime[redis]",
        see="docs/starters.md",
    ),
    Block(
        name="mail",
        doc="SMTP backend for MailService.",
        needs="xime[mail]",
        see="docs/starters.md",
    ),
    Block(name="jwt", doc="JWT authentication.", needs="xime[jwt]", see="docs/starters.md"),
    Block(
        name="storage",
        doc="File/blob store: `storage.local` or `storage.s3`.",
        see="docs/file-storage.md",
    ),
    Block(name="mqtt", doc="MQTT client.", needs="xime[mqtt]", see="docs/mqtt.md"),
    Block(name="modbus", doc="Modbus TCP.", needs="xime[modbus]", see="docs/modbus.md"),
    Block(name="opcua", doc="OPC UA.", needs="xime[opcua]", see="docs/opcua.md"),
    Block(
        name="processes",
        doc=(
            "Split the application across processes. Only meaningful when\n"
            "main.py calls `share_load()`, and a mismatch between the two is a\n"
            "startup error. For one process with several ports use `process:`."
        ),
        see="docs/multi-process.md",
    ),
    Block(
        name="process",
        doc=(
            "One process with several ports. This is the shape for the common\n"
            "case: a single process serving HTTP and gRPC at once. Use\n"
            "`processes:` (plural) to split the application across several."
        ),
        see="docs/multi-process.md",
    ),
)

BY_NAME: dict[str, Block] = {b.name: b for b in SPEC}
