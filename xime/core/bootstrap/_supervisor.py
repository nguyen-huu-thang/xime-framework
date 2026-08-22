"""Tiến trình cha: giữ tài nguyên dùng chung NẾU CÓ, sinh con, trông con.

```text
Người vận hành gõ:  python -m app.main        (không đối số, không env)
│
├─ import config                → registry được điền
├─ app = Application()          → object rỗng, chưa mở gì
├─ app.add_config(config)
├─ app.use(...)                 → object adapter, CHƯA start, chưa chiếm cổng
│
└─ if __name__ == "__main__":  app.share_load().run()
   │
   └─ không có XIME_PROCESS_ID  →  "tôi là cha"
      ├─ kiểm cấu hình
      ├─ bind() + listen() những địa chỉ dùng chung (nếu có)
      ├─ sinh từng con: env XIME_PROCESS_ID=<id>, kèm socket đã bind
      └─ vòng lặp giám sát: con chết thì dựng lại, Ctrl+C thì tắt theo thứ tự
         KHÔNG accept() · KHÔNG dựng DI · KHÔNG chạy code nghiệp vụ
```

Con chạy **lại chính `main.py`** với `XIME_PROCESS_ID` đã đặt. Lý do chọn vậy
thay vì một entry point riêng của framework: **một đường khởi động duy nhất**.
Hai đường là hai chỗ để trôi lệch, và loại lệch đó *không có triệu chứng* - ai
đó thêm một `configure_middleware()` vào `main.py`, cha có, con không, và ba
tiến trình phục vụ thiếu một middleware xác thực mà không gì báo.

⚠ Cha **không được chết**: con chết thì không ai dựng lại, `Ctrl+C` không có chỗ
điều phối thứ tự tắt.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import time
from collections.abc import Iterable, Mapping
from multiprocessing import connection as mp_connection
from typing import TYPE_CHECKING, Any

from xime.core._mp import MP_CONTEXT
from xime.core.bootstrap import _control
from xime.core.bootstrap._loop import uvloop_factory
from xime.core.bootstrap._processes import (
    PROCESS_ID_ENV,
    EndpointSpec,
    ProcessTopology,
    topology_error,
)
from xime.core.bootstrap._sdnotify import SystemdNotifier
from xime.core.bootstrap._shared import (
    SharedHandle,
    SharedMemoryOwner,
    allocate_shared_memory,
)
from xime.core.bootstrap._slot import (
    SHARE_INHERIT,
    SHARE_NONE,
    SHARE_REUSEPORT,
    AdapterSlot,
    adapter_id_of,
    adapter_kind_of,
    describe,
    share_strategy_of,
)
from xime.core.bootstrap._watchdog import (
    SILENCE_SECONDS,
    STARTUP_GRACE_SECONDS,
)
from xime.core.link import INTERNAL_CHANNEL, sweep_orphans

if TYPE_CHECKING:
    from xime.core.bootstrap.adapter import Adapter
    from xime.core.bootstrap.application import Application

_log = logging.getLogger("xime.bootstrap")

# Cùng giá trị uvicorn dùng mặc định. Cha bind hộ nên con không đặt được số này,
# và một backlog quá nhỏ chỉ lộ ra dưới tải - đúng lúc khó đo nhất.
_BACKLOG = 2048

# Khoá tra socket kế thừa: `(loại, id adapter)` trong phạm vi một tiến trình.
SocketMap = dict[tuple[str, str], socket.socket]

# Con chết ngay lập tức rồi được dựng lại ngay lập tức là một vòng lặp nóng đốt
# trọn một nhân và ghi log không ai đọc kịp. Chặn domino thật (N lần trong T
# giây thì dừng THĂNG CẤP) thuộc giai đoạn 6; đây chỉ là cái phanh tay.
_RESPAWN_DELAY = 1.0

# Hãm luỹ tiến khi một con chết đi chết lại. Không có nó thì một con chết ngay
# lúc khởi động (cấu hình sai, cổng riêng bị chiếm, migration hỏng) sinh ra
# **mỗi giây một lần spawn** - mà một lần spawn là import lại ~721 module,
# ~83 MB RSS, ngốn khoảng một giây CPU. Đốt trọn một nhân, không ngưỡng, không
# leo thang, và dòng log vẫn là một câu WARNING giống hệt nhau lặp mãi. Phát
# hiện T7 của kiểm toán 0.8.
#
# ⭐ Lời hứa "luôn dựng lại" GIỮ NGUYÊN - đây là hãm nhịp, không phải từ bỏ.
# Một cụm hỏng vì cấu hình phải tự phục hồi ngay khi cấu hình được sửa, nên
# không có ngưỡng nào làm nó ngừng thử.
_RESPAWN_DELAY_MAX = 30.0

# Sống được quá ngần này thì coi như con đã khởi động thành công, và bộ hãm của
# nó về 0. Chọn theo STARTUP_GRACE_SECONDS: một con qua được cửa đó là một con
# đã phục vụ, không phải một con đang giãy.
_RESPAWN_RESET_AFTER = 60.0

# Từ lần thứ này trở đi thì log lên CRITICAL: lặp lại một WARNING giống hệt nhau
# là cách chắc chắn nhất để không ai đọc nó nữa.
_RESPAWN_LOUD_AFTER = 10

# Thời gian chờ con tự tắt sau Ctrl+C trước khi cha ép.
_SHUTDOWN_GRACE = 10.0

# Chống domino: quá `N` lần thăng cấp trong `T` giây thì DỪNG CẤP VAI PRIMARY.
#
# ⚠ **Hai công tắc riêng, đừng gộp:** *dựng lại con đã chết* thì **vẫn làm** (cụm
# phải giữ khả năng phục vụ), chỉ *cấp vai primary* mới dừng. Mất job nền còn hơn
# mất khả năng phục vụ.
#
# Ca nó chặn: primary chết **vì chính job của nó** (cert hỏng làm `CertRotationJob`
# crash) -> thăng cấp B -> B chạy job đó -> B chết -> hết cả đàn trong vài giây.
_PROMOTION_LIMIT = 3
_PROMOTION_WINDOW = 60.0

# Cha đợi primary báo `run_once()` xong rồi mới sinh những con còn lại. Quá hạn
# thì **đi tiếp kèm cảnh báo**, không đứng mãi: một cụm không phục vụ gì tệ hơn
# một cụm chưa chạy xong migration, và người vận hành đọc được dòng cảnh báo.
_RUN_ONCE_WAIT = 60.0


# ----------------------------------------------------------------------
# Phép kiểm cần biết `main.py` khai gì
# ----------------------------------------------------------------------


def validate_against_adapters(
    topology: ProcessTopology,
    adapters: Iterable[Adapter],
    *,
    share_load: bool = True,
) -> None:
    """Bốn phép kiểm lúc khởi động, phần cần danh sách adapter.

    Phép kiểm 1 (`primary`) và phần cấu trúc của phép kiểm 4 nằm ở
    `parse_topology()`; ở đây là phần còn lại.
    """
    adapters = list(adapters)
    _reject_unknown_endpoints(topology, adapters)
    _reject_adapters_nobody_runs(topology, adapters)
    _reject_unsupported_sharing(topology, adapters)
    _reject_bad_sharding(topology, adapters)
    _reject_singleton_in_many_processes(topology, adapters)
    if share_load:
        _reject_sharded_under_share_load(adapters)


def _index(adapters: Iterable[Adapter]) -> dict[tuple[str, str], Adapter]:
    return {(adapter_kind_of(a), adapter_id_of(a)): a for a in adapters}


def _reject_unknown_endpoints(
    topology: ProcessTopology, adapters: list[Adapter]
) -> None:
    """Phép kiểm 2: tên trong cấu hình mà `main.py` không khai.

    Chắc chắn là gõ sai, vì cấu hình không tự sinh ra năng lực. Nó bắt được thứ
    mô hình cũ không bắt được: gõ `web: publik` thay vì `public` thì hôm nay là
    một server im lặng không có controller nào.
    """
    known = _index(adapters)
    unknown = [key for key in topology.declared_keys if key not in known]
    if not unknown:
        return
    listed = ", ".join(f"{kind}.{aid}" for kind, aid in unknown)
    available = (
        ", ".join(sorted(f"{kind}.{aid}" for kind, aid in known))
        or "(none - main.py registered no adapter)"
    )
    raise topology_error(
        "processes Declares An Unknown Endpoint",
        f"Declared in YAML: {listed}",
        f"Declared in code: {available}",
        "Detail: configuration selects among the doors main.py opened; it "
        "cannot create one. Check the spelling, or add the adapter via "
        "app.use(...).",
    )


def _reject_adapters_nobody_runs(
    topology: ProcessTopology, adapters: list[Adapter]
) -> None:
    """Adapter khai trong `main.py` mà **không khối nào** nhắc tới.

    Khác phép kiểm 3: *khối này không có* là cách lọc hợp lệ (ma trận thưa của
    fieldbus). *Không khối nào có* thì không phải lọc - không ai cố ý khai một
    cửa rồi không mở nó ở đâu cả, và hậu quả là một loại việc **không ai làm mà
    không ai biết**.
    """
    declared = set(topology.declared_keys)
    orphans = [
        describe(a) for a in adapters if (adapter_kind_of(a), adapter_id_of(a)) not in declared
    ]
    if not orphans:
        return
    raise topology_error(
        "Adapter Runs In No Process",
        f"Adapter(s): {', '.join(orphans)}",
        f"Processes : {', '.join(topology.ids)}",
        "Detail    : main.py registered these adapters but no processes block "
        "mentions them, so they would never start anywhere. Add them to a "
        "block, or remove the app.use(...) line.",
    )


def _reject_unsupported_sharing(
    topology: ProcessTopology, adapters: list[Adapter]
) -> None:
    """`shared: true` chỉ có nghĩa khi adapter biết cách dùng chung một địa chỉ.

    Và `SO_REUSEPORT` **không có trên Windows**, nên cấu hình đó phải nổ ở cha,
    lúc khởi động. Không có phép kiểm này thì tiến trình thứ hai nổ bằng
    `WinError 10048` giữa lúc chạy, và người đọc lỗi đó không có đường nào lần
    ra nguyên nhân thật.
    """
    known = _index(adapters)
    for block in topology.blocks:
        for spec in block.endpoints.values():
            if not spec.shared:
                continue
            adapter = known[spec.key]
            strategy = share_strategy_of(adapter)
            where = f"processes.{block.process_id}.{spec.kind}.{spec.adapter_id}"
            if strategy == SHARE_NONE:
                raise topology_error(
                    "Adapter Cannot Share An Address",
                    f"Config : {where}.shared",
                    f"Adapter: {type(adapter).__name__}",
                    "Detail : this adapter does not declare how it shares a "
                    "listening address (class attribute `share_port_by`). Give "
                    "each process its own address.",
                )
            if strategy == SHARE_REUSEPORT and sys.platform == "win32":
                raise topology_error(
                    "shared Is Not Available On Windows",
                    f"Config : {where}.shared",
                    f"Adapter: {type(adapter).__name__}",
                    "Detail : this adapter shares a port through SO_REUSEPORT, "
                    "which Windows does not have. Give each process its own "
                    "port here; the other adapters still run multi-process.",
                )


def _reject_sharded_under_share_load(adapters: list[Adapter]) -> None:
    """Adapter hạng phân mảnh chưa chia tải được ở 0.8 - thi công ở 0.8.1.

    ⚠ Phép kiểm này ở **framework**, không ở adapter. Trước đó mỗi adapter tự
    ném trong `assign_slot()`, nhưng từ khi mọi adapter luôn nhận một ô thì cách
    đó chặn luôn cả nhánh **một tiến trình**, nơi chúng chạy hoàn toàn bình
    thường. Cái phải chặn là *chia tải*, không phải *nhận cấu hình*.
    """
    from xime.core.bootstrap.adapter import SCALING_SHARDED

    sharded = [describe(a) for a in adapters if getattr(a, "scaling", None) == SCALING_SHARDED]
    if not sharded:
        return
    raise topology_error(
        "Sharded Adapters Under share_load Are Not Supported Yet",
        f"Adapter(s): {', '.join(sharded)}",
        "Detail    : these adapters are sharded, not replicated - each process "
        "must own a different slice (a set of devices, a set of topics), and "
        "two processes driving one device double the load on real hardware. "
        "That configuration shape is designed but lands in 0.8.1. Until then, "
        "run this application as a single process (no share_load()).",
    )


def _reject_bad_sharding(
    topology: ProcessTopology, adapters: list[Adapter]
) -> None:
    """Hai phép kiểm của hạng **phân mảnh**, đọc từ DỮ LIỆU chứ không từ docstring.

    Trước 0.8 lý do chống trùng nằm trong docstring của `MqttAdapter` - cả một
    đoạn giải thích vì sao hai adapter cùng `client_id` sẽ đánh nhau trong vòng
    lặp reconnect. Framework **đọc được nhưng không dùng được**.

    ⭐ Hai phép kiểm này **khác hẳn nhau**, và MQTT cần cả hai cùng lúc - đó là
    bằng chứng tách đúng:

    | | Kiểm gì | Vì sao |
    |---|---|---|
    | `unique_per_process` | giá trị ở hai khối **phải KHÁC NHAU** | hai tiến trình cùng `client_id` thì broker đá phiên cũ ra |
    | `disjoint_per_process` | tập giá trị **không được GIAO NHAU** | hai tiến trình cùng nghe một topic thì mỗi message xử lý hai lần |

    *"Khác nhau"* áp cho một **giá trị đơn**; *"không giao nhau"* áp cho một
    **tập**. Ép chung một phép kiểm là hoặc bỏ sót một loại, hoặc viết một phép
    kiểm mơ hồ mà không ai biết nó đang kiểm gì.
    """
    known = _index(adapters)
    for key, adapter in known.items():
        specs = [
            (block.process_id, block.endpoints[key])
            for block in topology.blocks
            if key in block.endpoints
        ]
        if len(specs) < 2:
            continue
        for field in getattr(adapter, "unique_per_process", ()):
            _reject_repeated_value(key, field, specs)
        for field in getattr(adapter, "disjoint_per_process", ()):
            _reject_overlapping_set(key, field, specs)


def _reject_repeated_value(
    key: tuple[str, str], field: str, specs: list[tuple[str, EndpointSpec]]
) -> None:
    seen: dict[Any, str] = {}
    for process_id, spec in specs:
        value = spec.options.get(field)
        if value is None:
            continue
        if value in seen:
            raise topology_error(
                "Sharded Adapter Repeats A Value Across Processes",
                f"Adapter  : {key[0]}.{key[1]}",
                f"Key      : {field}",
                f"Value    : {value!r}",
                f"Processes: {seen[value]}, {process_id}",
                "Detail   : this adapter declares the key as "
                "unique_per_process, so every process must configure a "
                "different value.",
            )
        seen[value] = process_id


def _reject_overlapping_set(
    key: tuple[str, str], field: str, specs: list[tuple[str, EndpointSpec]]
) -> None:
    owner: dict[Any, str] = {}
    for process_id, spec in specs:
        raw = spec.options.get(field)
        if raw is None:
            continue
        values = raw if isinstance(raw, (list, tuple, set)) else [raw]
        for value in values:
            if value in owner:
                raise topology_error(
                    "Sharded Adapter Overlaps Across Processes",
                    f"Adapter  : {key[0]}.{key[1]}",
                    f"Key      : {field}",
                    f"Value    : {value!r}",
                    f"Processes: {owner[value]}, {process_id}",
                    "Detail   : this adapter declares the key as "
                    "disjoint_per_process, so the sets configured in two "
                    "processes must not overlap - otherwise the same work is "
                    "done twice.",
                )
            owner[value] = process_id


def _reject_singleton_in_many_processes(
    topology: ProcessTopology, adapters: list[Adapter]
) -> None:
    """Adapter hạng **đơn nhất** chỉ chạy ở primary, nên khai nó ở khối khác là
    một lời hứa framework không giữ.

    Không nổ thì người vận hành đọc cấu hình và tin rằng scheduler chạy ở cả bốn
    tiến trình, trong khi nó chỉ chạy ở một. Cấu hình nói một đằng, hành vi một
    nẻo, và **không gì báo**.
    """
    from xime.core.bootstrap.adapter import SCALING_SINGLETON

    primary = topology.primary_id
    for key, adapter in _index(adapters).items():
        if getattr(adapter, "scaling", None) != SCALING_SINGLETON:
            continue
        elsewhere = [
            block.process_id
            for block in topology.blocks
            if key in block.endpoints and block.process_id != primary
        ]
        if elsewhere:
            raise topology_error(
                "Singleton Adapter Declared Outside primary",
                f"Adapter  : {key[0]}.{key[1]}",
                f"Processes: {', '.join(elsewhere)}",
                f"Primary  : {primary}",
                "Detail   : a singleton adapter only ever starts in the primary "
                "process, so declaring it elsewhere promises something the "
                "framework will not do.",
            )


# ----------------------------------------------------------------------
# Cha: bind những địa chỉ dùng chung
# ----------------------------------------------------------------------


def _bind_tcp(spec: EndpointSpec) -> socket.socket:
    host = spec.host if spec.host is not None else "0.0.0.0"
    assert spec.port is not None
    infos = socket.getaddrinfo(
        host, spec.port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE
    )
    family, socktype, proto, _, sockaddr = infos[0]
    sock = socket.socket(family, socktype, proto)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(sockaddr)
    except OSError as exc:
        sock.close()
        raise topology_error(
            "Cannot Bind A Shared Port",
            f"Address: {host}:{spec.port}",
            f"Detail : {exc}",
        ) from exc
    sock.listen(_BACKLOG)
    sock.set_inheritable(True)
    return sock


def _bind_unix(spec: EndpointSpec) -> socket.socket:
    from pathlib import Path

    assert spec.path is not None
    Path(spec.path).parent.mkdir(parents=True, exist_ok=True)
    # Dọn socket mồ côi của lần crash trước. ⚠ Nay CHA làm việc này, một lần,
    # trước khi có con nào - chứ không phải mỗi con tự dọn. Để con tự dọn với
    # đường dẫn dùng chung thì con thứ hai xoá socket của con thứ nhất rồi bind
    # cái mới: con một vẫn sống, vẫn accept() trên một inode không còn tên,
    # không ai gọi tới được, và không lỗi nào phát ra.
    if os.path.exists(spec.path):
        os.remove(spec.path)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(spec.path)
    except OSError as exc:
        sock.close()
        raise topology_error(
            "Cannot Bind A Shared Socket Path",
            f"Path  : {spec.path}",
            f"Detail: {exc}",
        ) from exc
    # ⛔ chmod TRƯỚC listen(), không phải sau. Từ lúc listen() trả về là socket
    # đã nhận kết nối, và cửa sổ tới lúc con gọi `secure_socket_file()` phủ
    # trọn: import lại main.py, dựng DI, mở pool, lấy cert, chạy run_once()
    # (migration). Framework tự khai cửa sổ đó có thể dài 60 giây
    # (_RUN_ONCE_WAIT, STARTUP_GRACE_SECONDS).
    #
    # Cha KHÔNG biết `socket.<id>.permission` đã cấu hình - khoá đó nằm trong
    # DI mà cha không dựng DI. Nên thứ tự đúng là **chặt trước, nới sau**: cha
    # đặt 0600, con nới ra nếu người vận hành đã khai rộng hơn.
    #
    # ⚠ Đây là hồi quy do 0.8 sinh ra: một tiến trình thì bind và chmod là hai
    # dòng liền nhau. Phát hiện C2 của kiểm toán 0.8. Và `allowed_uids` mặc
    # định rỗng, với `authorize_peer` ghi rõ "whitelist rỗng = chấp nhận mọi
    # UID; lúc đó dựa hoàn toàn vào file permission" - tức quyền tệp là chốt
    # chặn DUY NHẤT trong cửa sổ này.
    if os.name != "nt":
        try:
            os.chmod(spec.path, 0o600)
        except OSError as exc:
            sock.close()
            raise topology_error(
                "Cannot Secure A Shared Socket Path",
                f"Path  : {spec.path}",
                f"Detail: {exc}",
                "Fix   : the parent refuses to listen on a socket it cannot "
                "restrict - any local user could otherwise connect during "
                "startup.",
            ) from exc
    sock.listen(_BACKLOG)
    sock.set_inheritable(True)
    return sock


def bind_shared_sockets(
    topology: ProcessTopology, adapters: Iterable[Adapter]
) -> dict[tuple[str, Any], socket.socket]:
    """Cha bind mỗi địa chỉ dùng chung **một lần**, trả về theo danh tính socket.

    ⭐ Lợi ích phụ đáng kể: **cổng bị chiếm thì cha nổ ngay lúc khởi động**, thay
    vì bốn con lần lượt nổ và người vận hành đọc bốn stack trace giống nhau.

    Địa chỉ dùng `SO_REUSEPORT` thì cha **không bind** - mỗi con tự bind, kernel
    chia. Ô không mở địa chỉ nào (mqtt, modbus, opcua) cũng không có gì để bind:
    đó là **ca 2**, và nó dễ hơn ca 1 chứ không phải khó hơn.
    """
    known = _index(adapters)
    bound: dict[tuple[str, Any], socket.socket] = {}
    try:
        for block in topology.blocks:
            for spec in block.endpoints.values():
                if not spec.shared or spec.endpoint in bound:
                    continue
                if share_strategy_of(known[spec.key]) != SHARE_INHERIT:
                    continue
                sock = _bind_unix(spec) if spec.path is not None else _bind_tcp(spec)
                bound[spec.endpoint] = sock
                _log.info(
                    "supervisor: bound shared %s %s for %s.%s",
                    spec.endpoint[0],
                    spec.endpoint[1],
                    spec.kind,
                    spec.adapter_id,
                )
    except BaseException:
        for sock in bound.values():
            sock.close()
        raise
    return bound


def _sockets_for(
    topology: ProcessTopology,
    process_id: str,
    bound: Mapping[tuple[str, Any], socket.socket],
) -> SocketMap:
    block = topology.by_id(process_id)
    assert block is not None
    out: SocketMap = {}
    for spec in block.endpoints.values():
        sock = bound.get(spec.endpoint) if spec.shared else None
        if sock is not None:
            out[spec.key] = sock
    return out


# ----------------------------------------------------------------------
# Con: gán ô cho adapter, lọc adapter không chạy ở tiến trình này
# ----------------------------------------------------------------------


def prepare_worker(
    topology: ProcessTopology,
    adapters: Iterable[Adapter],
    process_id: str,
    sockets: Mapping[tuple[str, str], socket.socket],
    *,
    single: bool = False,
) -> list[Adapter]:
    """Gán ô cấu hình và trả về đúng những adapter chạy ở tiến trình này."""
    block = topology.by_id(process_id)
    if block is None:
        raise topology_error(
            "Unknown Process Id",
            f"{PROCESS_ID_ENV}: {process_id}",
            f"Known      : {', '.join(topology.ids)}",
            "Detail     : the environment names a process that no processes "
            "block defines.",
        )

    from xime.core.bootstrap.adapter import SCALING_SINGLETON

    primary_block = topology.by_id(topology.primary_id)
    active: list[Adapter] = []
    for adapter in adapters:
        key = (adapter_kind_of(adapter), adapter_id_of(adapter))
        spec = block.endpoints.get(key)
        if (
            spec is None
            and getattr(adapter, "scaling", None) == SCALING_SINGLETON
            and primary_block is not None
        ):
            # ⭐ Adapter hạng ĐƠN NHẤT được giữ ở MỌI tiến trình, dù cấu hình chỉ
            # khai nó ở khối primary - và nó phải được khai đúng một chỗ, vì
            # `_reject_singleton_in_many_processes` cấm khai ở khối khác.
            #
            # Không giữ thì nó **biến mất** khỏi con phụ, và lúc primary chết thì
            # không con nào có nó để nhận vai: cụm mất job nền vĩnh viễn, không
            # gì báo. Thiết kế mục 4.5 nói *"con biết adapter nào là singleton"* -
            # câu đó giả định nó CÓ MẶT ở con, và giai đoạn 3 thì không.
            #
            # Lấy ô của khối primary vì theo cấu trúc chỉ có đúng một ô như vậy.
            spec = primary_block.endpoints.get(key)
        if spec is None:
            # Phép kiểm 3: lọc, không phải lỗi. Nhưng **phải nói ra** - với web
            # thì im lặng là chấp nhận được, với một dây chuyền thiết bị thì im
            # lặng nghĩa là không ai đọc nó mà không ai biết.
            _log.warning(
                "process %s does not declare %s.%s - that adapter will not run here",
                process_id,
                key[0],
                key[1],
            )
            continue
        _assign(adapter, AdapterSlot(
            process_id=process_id,
            primary=block.primary,
            spec=spec,
            sock=sockets.get(key),
            single=single,
        ))
        active.append(adapter)
    return active


def _assign(adapter: Adapter, slot: AdapterSlot) -> None:
    assign = getattr(adapter, "assign_slot", None)
    if assign is None:
        raise topology_error(
            "Adapter Does Not Accept A processes Block",
            f"Adapter: {type(adapter).__name__}",
            f"Config : processes.{slot.process_id}.{slot.spec.kind}."
            f"{slot.spec.adapter_id}",
            "Detail : under share_load() the framework pushes configuration "
            "into each adapter, so the adapter must implement assign_slot(). "
            "This adapter still reads its own configuration and would bind the "
            "wrong address.",
        )
    assign(slot)


# ----------------------------------------------------------------------
# Tìm biến giữ Application trong `__main__`
# ----------------------------------------------------------------------


def main_attribute_of(app: Application) -> str:
    """Tên biến ở mức module trong `__main__` đang giữ `app`.

    Con chạy lại `main.py` nên nó dựng một `Application` **của riêng nó**; cha
    chỉ cần nói *"lấy cái tên là X"*. Tìm bằng danh tính (`is`) chứ không bằng
    kiểu, để một app có hai `Application` không bị lấy nhầm.

    ⭐ Nó đồng thời **cưỡng chế** đúng thứ mô hình đòi: `app`, `add_config()` và
    `use()` phải nằm ở **mức module**. Đặt chúng trong `if __name__` thì con
    import xong sẽ có một app không adapter nào và DI rỗng - và cách hỏng đó
    không có triệu chứng. Ở đây nó thành một dòng chữ.
    """
    main = sys.modules.get("__main__")
    namespace = getattr(main, "__dict__", {}) if main is not None else {}
    for name, value in namespace.items():
        if value is app and not name.startswith("__"):
            return name
    raise topology_error(
        "Application Is Not A Module-Level Variable",
        "Detail: share_load() spawns children that re-run main.py, so the "
        "Application object must be assigned to a module-level name there:",
        "",
        "    app = Application()",
        "    app.add_config(config)",
        "    app.use(WebAdapter())",
        "",
        "    if __name__ == \"__main__\":",
        "        app.share_load().run()",
        "",
        "Only the last line belongs inside `if __name__`.",
    )


def _application_from_main(attr: str) -> Application:
    main = sys.modules.get("__main__")
    app = getattr(main, attr, None) if main is not None else None
    if app is None:
        raise topology_error(
            "Child Process Cannot Find The Application",
            f"Expected: {attr} in __main__",
            "Detail  : the child re-runs main.py and looks for the same "
            "module-level name the parent had. Did that assignment move inside "
            "a function or inside `if __name__`?",
        )
    return app


# ----------------------------------------------------------------------
# Điểm vào của tiến trình con
# ----------------------------------------------------------------------


def worker_loop_factory(sockets: Mapping[tuple[str, str], socket.socket]) -> Any:
    """Chọn hiện thực event loop cho tiến trình đang chạy.

    ⚠ **Tên hàm hẹp hơn việc nó làm, và đó là chuyện của lịch sử.** Nó ra đời ở
    0.8.0 để giải đúng một ca (con Windows kế thừa socket), nhưng từ đợt kiểm
    toán 0.8.0 thì **cả ba nhánh** của `Application.run()` - đơn tiến trình,
    supervisor, worker - đều rơi vào `_run_worker()`, nơi có **đúng một** lời
    gọi `asyncio.run(..., loop_factory=worker_loop_factory(sockets))`. Nên đây
    là **cửa duy nhất** quyết định loop của mọi tiến trình Xime.

    ⭐ Nhờ vậy nỗi lo *"vá một nửa"* của bản thiết kế uvloop (sửa nhánh
    `share_load` mà quên nhánh thường, hoặc ngược lại, và **không gì báo**) nay
    **không tồn tại về mặt cấu trúc**, chứ không phải được tránh nhờ cẩn thận.
    Test canh: `tests_temp/bootstrap/test_event_loop.py`.

    Ba nhánh, và chúng nằm trên **hai nền tảng rời nhau** nên không đè nhau:

    | Nền tảng | Có socket kế thừa | Trả về |
    |---|---|---|
    | Windows | có | `asyncio.SelectorEventLoop` - xem `WinError 87` bên dưới |
    | Windows | không | `None` (proactor mặc định) |
    | Linux, macOS | bất kỳ | `uvloop_factory()`: uvloop nếu cài được, `None` nếu không |

    ⛔ **Đừng gộp hai điều kiện thành một dòng `if`.** Bản 0.8.0 viết
    `if sys.platform != "win32" or not sockets: return None`, đúng khi chỉ có
    nhánh Windows nhưng nó **trộn hai câu hỏi khác nhau** (*nền tảng nào* và *có
    kế thừa socket không*), nên thêm uvloop vào đó là sai ngay.

    ## Phần Windows: vì sao selector, và vì sao không được đụng vào

    ⚠⚠ **Đo được 2026-08-20, và nó lật một dòng của thiết kế.** Bảng ở mục 5.7.1
    ghi Windows ✅ cho web nhờ `WSADuplicateSocket`. Handle thì chuyển qua được
    thật, nhưng `asyncio` mặc định trên Windows là **proactor**, và ở đó lần
    `accept()` đầu tiên gọi `CreateIoCompletionPort` trên socket:

    ```text
    OSError: [WinError 87] The parameter is incorrect
    ```

    Nguyên nhân: **liên kết IOCP thuộc về SOCKET của kernel, không thuộc về
    HANDLE**. Tiến trình thứ nhất gắn socket vào IOCP của nó xong thì tiến trình
    thứ hai không gắn được vào IOCP của mình nữa - dù nó cầm một handle hợp lệ.

    Cách hỏng của nó là kiểu tệ nhất: con thứ hai khởi động **thành công**, log
    *"serving"*, rồi **không nhận nổi một kết nối nào**. Cụm mất một nửa năng
    lực trong khi mọi request đều 200 và không có gì đỏ.

    ⛔ `sock.share(os.getpid())` + `fromshare()` (cách uvicorn làm) **KHÔNG cứu
    được** - đã đo cả hai đường, cùng một lỗi. Thứ cứu được là **selector loop**:
    nó `accept()` thẳng, không đụng IOCP. Đo lại với selector: hai tiến trình
    cùng trả lời trên một cổng.

    Cái giá của selector trên Windows: `select()` giới hạn 512 socket, và không
    chạy được subprocess trên loop đó. Chấp nhận được vì **Windows là máy dev**,
    còn prod là Linux (ở đó proactor không tồn tại và `epoll` không có giới hạn
    này). Đổi lại giữ được thứ đắt hơn nhiều: **dev chạy giống prod**.

    ## Phần Linux/macOS: uvloop

    `uvloop_factory()` trả `None` khi uvloop không import được, tức app chạy
    đúng như mọi bản trước 0.8.1. Xem `_loop.py` cho lý do đầy đủ, gồm cả việc
    uvloop **đã nằm sẵn trên đĩa** ở mọi cài đặt Linux chuẩn mà trước nay chưa
    bao giờ chạy.

    ✅ **uvloop cộng `fork` là cạm bẫy kinh điển, và Xime không dính** - không
    phải nhờ tránh mà nhờ may: supervisor dùng `multiprocessing.get_context("spawn")`
    vì lý do khác hẳn (truyền socket và import lại `main.py`), và **cha không
    chạy asyncio** (nó là vòng lặp `waitpid` thuần). Mỗi con dựng loop từ đầu.
    ⚠ Ngày ai đó đổi `spawn` thành `fork` thì phải đọc lại đúng dòng này.
    """
    if sys.platform == "win32":
        if not sockets:
            return None
        import asyncio

        _log.warning(
            "windows: switching to the selector event loop because this process "
            "inherited %d shared socket(s) - the default proactor loop cannot "
            "accept on a socket another process already bound to its IOCP "
            "(WinError 87). Production runs on Linux, where this does not apply.",
            len(sockets),
        )
        return asyncio.SelectorEventLoop
    return uvloop_factory()


def _worker_entry(
    process_id: str,
    app_attr: str,
    sockets: SocketMap,
    shared: SharedHandle,
) -> None:
    """Chạy trong tiến trình con, **sau khi** `main.py` đã được import lại.

    `multiprocessing` với `spawn` import lại module `__main__` của cha (dưới tên
    `__mp_main__`, nên `if __name__ == "__main__"` **không** kích hoạt), rồi mới
    chạy hàm này. Tức `import config` và `app.use(...)` đã chạy tự nhiên.
    """
    os.environ[PROCESS_ID_ENV] = process_id
    app = _application_from_main(app_attr)
    app.run_as_worker(process_id, sockets, shared)


# ----------------------------------------------------------------------
# Vòng đời của cha
# ----------------------------------------------------------------------


class Supervisor:
    """Sinh con, trông con, tắt cả đàn. Không `accept()`, không dựng DI."""

    def __init__(
        self,
        app: Application,
        topology: ProcessTopology,
        bound: Mapping[tuple[str, Any], socket.socket],
        shared: SharedMemoryOwner | None = None,
    ) -> None:
        self._app = app
        self._topology = topology
        self._bound = bound
        self._shared = shared or SharedMemoryOwner(None)
        self._attr = main_attribute_of(app)
        self._ctx = MP_CONTEXT
        self._children: dict[str, Any] = {}
        self._spawned_at: dict[str, float] = {}
        # Số lần một con chết LIÊN TIẾP mà không sống nổi _RESPAWN_RESET_AFTER.
        self._respawns: dict[str, int] = {}
        self._stopping = False
        self._previous_handlers: dict[Any, Any] = {}
        # Ai đang giữ vai primary. Cấu hình chỉ nói ai **bắt đầu** với nó; từ
        # đó trở đi cha là nguồn sự thật, vì chỉ cha biết ai còn sống.
        self._primary_id: str | None = topology.primary_id
        self._run_once_done = False
        self._promotions: list[float] = []
        self._promotion_stopped = False
        self._notifier = SystemdNotifier()

    def run(self) -> None:
        """Sinh mọi con rồi trông tới khi bị ngắt."""
        _log.info(
            "supervisor: starting %d process(es): %s (primary=%s)",
            len(self._topology.blocks),
            ", ".join(self._topology.ids),
            self._topology.primary_id,
        )
        self._install_signal_handlers()
        try:
            # Primary TRƯỚC, và cha **đợi nó báo xong** rồi mới sinh những con
            # còn lại: `run_once()` là việc chạy một lần cho cả cụm (migration,
            # lấy khoá ký lần đầu), và nó phải xong **trước khi bất cứ ai phục
            # vụ**. Đó là toàn bộ khác biệt giữa `run_once` và một job một-lần
            # của scheduler.
            ordered = self._ordered_ids()
            self._spawn(ordered[0])
            self._await_run_once(ordered[0])
            for process_id in ordered[1:]:
                if self._stopping:
                    break
                self._spawn(process_id)
            self._notifier.ready()
            self._watch()
        except KeyboardInterrupt:
            _log.info("supervisor: interrupted")
        finally:
            self._notifier.stopping()
            self._shutdown()
            self._notifier.close()
            self._restore_signal_handlers()

    def _install_signal_handlers(self) -> None:
        """Bắt tín hiệu dừng để cha tắt cả đàn theo thứ tự.

        Không bắt thì cha chết ngay còn con **sống tiếp mồ côi** - vẫn giữ cổng,
        vẫn phục vụ, và không ai dựng lại chúng nữa. Đúng thứ tệ nhất: hệ thống
        trông như đã tắt mà thực ra chưa.

        `SIGTERM` là thứ `systemd` gửi, nên nó là đường tắt máy thật ở prod.
        `SIGBREAK` chỉ có trên Windows và là tín hiệu duy nhất bắt được ở đó khi
        tiến trình chạy trong một nhóm riêng.
        """
        import signal

        names = ["SIGINT", "SIGTERM", "SIGBREAK"]
        for name in names:
            sig = getattr(signal, name, None)
            if sig is None:
                continue
            try:
                self._previous_handlers[sig] = signal.signal(sig, self._on_signal)
            except (ValueError, OSError):
                # Không phải luồng chính (test, notebook): bỏ qua, `KeyboardInterrupt`
                # vẫn là đường lui.
                continue

    def _restore_signal_handlers(self) -> None:
        import signal

        for sig, handler in self._previous_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                continue
        self._previous_handlers.clear()

    def _on_signal(self, signum: int, _frame: Any) -> None:
        _log.info("supervisor: signal %s received - stopping", signum)
        self._stopping = True

    def _ordered_ids(self) -> list[str]:
        primary = self._topology.primary_id
        return [primary] + [pid for pid in self._topology.ids if pid != primary]

    def _spawn(self, process_id: str) -> None:
        sockets = _sockets_for(self._topology, process_id, self._bound)
        # Chỉ số theo đúng thứ tự khai trong cấu hình, nên một con được dựng
        # lại **giữ nguyên** chỉ số của nó. Suy từ thứ tự sinh thì con dựng lại
        # sẽ nhận một chỉ số khác, và `nguoi_ghi` trong bảng hoá ra trỏ vào một
        # tiến trình không còn tồn tại.
        index = self._topology.ids.index(process_id)
        # Cha quyết ai là primary, không phải cấu hình - nếu không thì một
        # primary đã chết, được dựng lại, sẽ quay về **vẫn tin mình là primary**
        # trong khi cha đã trao vai cho người khác. Hai primary cùng chạy job
        # nền, và không gì báo.
        handle = self._shared.handle_for(index, primary=(process_id == self._primary_id))
        beats = self._shared.beats
        if beats is not None:
            # Xoá ô nhịp trước khi sinh: con mới thừa hưởng mốc của con vừa
            # chết, và nếu mốc đó đã quá hạn thì cha giết con mới ngay lúc nó
            # vừa ra đời - một vòng sinh-giết không lý do.
            beats.reset(index)
        proc = self._ctx.Process(
            target=_worker_entry,
            args=(process_id, self._attr, sockets, handle),
            name=f"xime-{process_id}",
        )
        # Con phải thấy id **trước mọi lệnh import**, vì `config/` chạy trước khi
        # hàm điểm vào của framework được gọi. `multiprocessing` không nhận
        # `env=`, nên đặt vào môi trường của cha đúng lúc sinh rồi trả lại ngay.
        previous = os.environ.get(PROCESS_ID_ENV)
        os.environ[PROCESS_ID_ENV] = process_id
        try:
            proc.start()
        finally:
            if previous is None:
                os.environ.pop(PROCESS_ID_ENV, None)
            else:
                os.environ[PROCESS_ID_ENV] = previous
        self._children[process_id] = proc
        self._spawned_at[process_id] = time.monotonic()
        _log.info(
            "supervisor: started %s (pid %s)%s",
            process_id,
            proc.pid,
            " [primary]" if process_id == self._primary_id else "",
        )

    def _watch(self) -> None:
        while not self._stopping:
            sentinels = {p.sentinel: pid for pid, p in self._children.items()}
            if not sentinels:
                return
            try:
                ready = mp_connection.wait(list(sentinels), timeout=1.0)
            except KeyboardInterrupt:
                raise
            except OSError:
                # Một sentinel đóng giữa chừng (con vừa được join ở vòng trước).
                continue
            # Vỗ lên systemd mỗi vòng: cha canh con, systemd canh cha. Watchdog
            # không nằm trên con CPU nó canh - đó là điều làm nó đáng tin.
            self._notifier.watchdog()
            self._pump_control()
            for sentinel in ready:
                process_id = sentinels[sentinel]
                self._respawn(process_id)
            self._reap_hung_children()

    # ------------------------------------------------------------------
    # Kênh điều khiển và watchdog
    # ------------------------------------------------------------------

    def _pump_control(self) -> None:
        """Đọc những gì con vừa báo. **Đồng bộ** - cha không có event loop."""
        link = self._shared.link
        if link is None:
            return
        try:
            messages = link.drain_sync(INTERNAL_CHANNEL)
        except Exception:  # noqa: BLE001 - một tin hỏng không được giết cha
            _log.warning(
                "supervisor: could not read the control channel", exc_info=True
            )
            return
        for message in messages:
            self._on_control(message.key, message.payload)

    def _on_control(self, key: str, payload: bytes) -> None:
        index, _flag, extra = _control.unpack(payload)
        who = self._id_at(index)
        if key == _control.RUN_ONCE_DONE:
            self._run_once_done = True
            _log.info("supervisor: %s finished the cluster-wide run_once", who)
        elif key == _control.READY:
            _log.info("supervisor: %s is serving", who)
        elif key == _control.PROMOTED:
            _log.info("supervisor: %s took the primary role", who)
        elif key == _control.PROMOTE_FAILED:
            reason = extra.decode("utf-8", errors="replace")
            # ⚠ Cảnh báo này hôm nay tới được journald, KHÔNG tới được người:
            # đường ra của cha (mục 2.8c của thiết kế) đang hoãn. Khai rõ để
            # không ai tưởng đã xong.
            _log.critical(
                "supervisor: %s REFUSED the primary role (%s) - it keeps serving, "
                "but the cluster has no primary until someone else takes it",
                who,
                reason,
            )
            self._promote_someone(exclude=who)
        elif key == _control.ADAPTER_ISOLATED:
            _log.critical(
                "supervisor: %s isolated adapter %s",
                who,
                extra.decode("utf-8", errors="replace"),
            )

    def _await_run_once(self, primary_id: str) -> None:
        """Đợi primary báo `run_once()` xong, hoặc đợi nó chết, hoặc hết hạn.

        Đây là chỗ `run_once` khác một job một-lần của scheduler: không phải
        *chạy một lần vào một thời điểm*, mà **chạy một lần, và mọi thứ khác đợi
        nó**. Migration xong rồi mới có con thứ hai mở kết nối.
        """
        deadline = time.monotonic() + _RUN_ONCE_WAIT
        while not self._stopping and not self._run_once_done:
            proc = self._children.get(primary_id)
            if proc is None or not proc.is_alive():
                _log.error(
                    "supervisor: %s died before finishing run_once", primary_id
                )
                return
            if time.monotonic() > deadline:
                _log.warning(
                    "supervisor: %s has not reported run_once after %.0fs - "
                    "starting the remaining processes anyway",
                    primary_id,
                    _RUN_ONCE_WAIT,
                )
                return
            self._pump_control()
            time.sleep(0.05)

    def _reap_hung_children(self) -> None:
        """Giết con đã im quá lâu. ⛔ **GIẾT, không phải thăng cấp.**

        Thăng cấp chỉ tin `waitpid`. Con bị giết ở đây làm sentinel của nó nổ ở
        vòng sau, và `_respawn` mới là chỗ quyết định thăng cấp - nên ca *"hai
        primary"* đóng chặt: A treo, cha giết A, kernel xác nhận A chết, cha mới
        trao vai. A **không thể tỉnh lại** vì nó đã chết thật chứ không phải bị
        coi là chết.
        """
        beats = self._shared.beats
        if beats is None:
            return
        # ⛔ CÙNG đồng hồ với thứ con ghi vào ô nhịp. Con dùng `monotonic()`
        # (xem `_watchdog.py`), nên cha so bằng `time()` là trừ hai đại lượng
        # khác hệ quy chiếu - ra một con số cỡ giờ epoch, và mọi con đều bị coi
        # là treo. Đây là NHÁNH THỨ HAI của T1: hai dòng cách nhau vài file
        # cùng đo một khoảng thời gian bằng hai đồng hồ khác nhau.
        now = time.monotonic()
        for process_id, proc in list(self._children.items()):
            if not proc.is_alive():
                continue
            index = self._topology.ids.index(process_id)
            silent = beats.silent_for(index, now=now)
            if silent is None:
                # Chưa vỗ lần nào: đang khởi động. Nhưng đang-khởi-động không
                # phải một lời bào chữa vĩnh viễn - xem STARTUP_GRACE_SECONDS.
                age = time.monotonic() - self._spawned_at.get(process_id, 0.0)
                if age <= STARTUP_GRACE_SECONDS:
                    continue
                _log.critical(
                    "supervisor: %s never sent a heartbeat in %.0fs - killing it",
                    process_id,
                    age,
                )
            elif silent > SILENCE_SECONDS:
                _log.critical(
                    "supervisor: %s has been silent for %.1fs (its event loop is "
                    "blocked) - killing it",
                    process_id,
                    silent,
                )
            else:
                continue
            proc.kill()

    # ------------------------------------------------------------------
    # Thăng cấp primary
    # ------------------------------------------------------------------

    def _id_at(self, index: int) -> str:
        ids = self._topology.ids
        return ids[index] if 0 <= index < len(ids) else f"#{index}"

    def _promote_someone(self, *, exclude: str | None = None) -> None:
        """Trao vai primary cho một con **đang sống**, có chống domino."""
        link = self._shared.link
        if link is None or self._promotion_stopped:
            return
        now = time.monotonic()
        self._promotions = [t for t in self._promotions if now - t < _PROMOTION_WINDOW]
        if len(self._promotions) >= _PROMOTION_LIMIT:
            self._promotion_stopped = True
            self._primary_id = None
            # ⚠ Hai công tắc riêng: cha VẪN dựng lại con đã chết, chỉ thôi cấp
            # vai primary. Mất job nền còn hơn mất khả năng phục vụ.
            _log.critical(
                "supervisor: %d promotions in %.0fs - this looks like a job that "
                "kills whoever runs it. NO MORE PROMOTIONS; the cluster keeps "
                "serving without background jobs. Processes are still restarted.",
                _PROMOTION_LIMIT,
                _PROMOTION_WINDOW,
            )
            return
        candidate = next(
            (
                pid
                for pid in self._topology.ids
                if pid != exclude
                and pid in self._children
                and self._children[pid].is_alive()
            ),
            None,
        )
        if candidate is None:
            self._primary_id = None
            _log.error("supervisor: no live process left to take the primary role")
            return
        self._promotions.append(now)
        self._primary_id = candidate
        index = self._topology.ids.index(candidate)
        _log.warning("supervisor: promoting %s to primary", candidate)
        try:
            link.announce_sync(
                INTERNAL_CHANNEL,
                _control.pack(index, flag=0 if self._run_once_done else 1),
                key=_control.PROMOTE,
            )
        except Exception:  # noqa: BLE001 - đường báo tin không kéo cha theo
            _log.critical(
                "supervisor: could not tell %s to take the primary role",
                candidate,
                exc_info=True,
            )

    def _respawn(self, process_id: str) -> None:
        proc = self._children.pop(process_id, None)
        if proc is None:
            return
        proc.join()
        # ⚠ Kiểm `_stopping` TRƯỚC khi log. Nói *"restarting"* rồi không restart
        # là một dòng log mang hai nghĩa, và nó nói dối đúng lúc người ta đang
        # đọc log để hiểu vì sao cụm tắt. Ca thật: tín hiệu dừng tới cả nhóm
        # tiến trình nên con chết TRƯỚC khi cha kịp vào bước tắt.
        if self._stopping:
            _log.info(
                "supervisor: %s exited with code %s during shutdown",
                process_id,
                proc.exitcode,
            )
            return
        _log.warning(
            "supervisor: %s exited with code %s - restarting",
            process_id,
            proc.exitcode,
        )
        # ⭐ THĂNG CẤP Ở ĐÂY, không ở chỗ phát hiện treo: tới được dòng này
        # nghĩa là `join()` đã trả về, tức **kernel xác nhận tiến trình đã
        # exit**. Đó là ràng buộc (a) của thiết kế, và nó là thứ đóng chặt ca
        # "hai primary" - một tiến trình đã chết thật thì không tỉnh lại được.
        if process_id == self._primary_id:
            self._primary_id = None
            self._promote_someone(exclude=process_id)
        song_duoc = time.monotonic() - self._spawned_at.get(process_id, 0.0)
        if song_duoc >= _RESPAWN_RESET_AFTER:
            # Con này đã khởi động được và phục vụ một lúc; lần chết này không
            # thuộc cùng một chuỗi với những lần trước.
            self._respawns.pop(process_id, None)
        lan = self._respawns.get(process_id, 0) + 1
        self._respawns[process_id] = lan
        cho = min(_RESPAWN_DELAY * (2 ** (lan - 1)), _RESPAWN_DELAY_MAX)
        if lan >= _RESPAWN_LOUD_AFTER:
            _log.critical(
                "supervisor: %s has died %d times in a row (alive %.1fs last "
                "time). Waiting %.0fs before the next attempt. This is a "
                "configuration or startup failure, not a transient crash - the "
                "supervisor will keep trying, but nothing will improve until "
                "the cause is fixed.",
                process_id, lan, song_duoc, cho,
            )
        elif lan > 1:
            _log.warning(
                "supervisor: %s has died %d times in a row - waiting %.0fs "
                "before restarting it",
                process_id, lan, cho,
            )
        time.sleep(cho)
        self._spawn(process_id)

    def _shutdown(self) -> None:
        self._stopping = True
        # Log KỂ CẢ khi không còn con nào. Không có dòng này thì một lần tắt tử
        # tế và một cái chết đột ngột để lại **cùng một** dấu vết trong log, và
        # người vận hành không có cách nào phân biệt.
        _log.info("supervisor: stopping (%d process(es) still alive)", len(self._children))
        if not self._children:
            self._close_sockets()
            return
        # `terminate()` là `SIGTERM` trên POSIX, và uvicorn bắt nó để tắt êm.
        # Gửi thêm một lần dù con đã nhận `SIGINT` từ nhóm tiến trình cũng vô
        # hại - nó chỉ đặt lại đúng cái cờ thoát.
        for proc in self._children.values():
            if proc.is_alive():
                proc.terminate()
        deadline = time.monotonic() + _SHUTDOWN_GRACE
        for proc in self._children.values():
            proc.join(timeout=max(0.0, deadline - time.monotonic()))
        for process_id, proc in list(self._children.items()):
            if proc.is_alive():
                _log.error("supervisor: %s ignored terminate - killing", process_id)
                proc.kill()
                proc.join(timeout=5.0)
        self._children.clear()
        self._close_sockets()

    def _close_sockets(self) -> None:
        for endpoint, sock in self._bound.items():
            try:
                sock.close()
            finally:
                if endpoint[0] == "unix":
                    # Cha tạo file thì cha dọn. Con không được đụng vào - xem
                    # ghi chú ở `_bind_unix`.
                    try:
                        os.remove(endpoint[1])
                    except OSError:
                        pass


def run_supervisor(
    app: Application, topology: ProcessTopology, adapters: Iterable[Adapter]
) -> None:
    """Nhánh cha của `run()`.

    Thứ tự ở đây là hợp đồng: **kiểm cấu hình -> chiếm tài nguyên -> sinh con**.
    Cấp vùng nhớ chung trước khi sinh con là bắt buộc (con attach theo tên), và
    sau khi bind socket là cố ý - một cổng đã bị chiếm thì nổ ngay, chứ không
    nổ sau khi vừa cấp xong một mớ bộ nhớ phải đi dọn.
    """
    adapters = list(adapters)
    validate_against_adapters(topology, adapters)
    # Dọn vùng nhớ chung của những lần chạy trước đã chết bằng SIGKILL. Phải ở
    # đây, trước khi cấp vùng mới: đây là điểm duy nhất trong đời một cụm mà ta
    # biết chắc chưa có tiến trình con nào của MÌNH đang sống.
    #
    # ⚠ Hàm này tồn tại từ đầu, có 4 test, nằm trong `__all__`, và docstring
    # xếp nó là lớp che `kill -9` DUY NHẤT - nhưng **không đường khởi động nào
    # gọi nó**. Phát hiện T3 của kiểm toán 0.8, và là ca thật của khuôn *"một
    # cơ chế phòng thủ CÓ MẶT nhưng KHÔNG BAO GIỜ CHẠY"*. Nên test canh cho nó
    # phải canh **CHỖ GỌI NÀY**, không chỉ canh bản thân hàm.
    sweep_orphans()
    bound = bind_shared_sockets(topology, adapters)
    # `+ 1` ô cho chính cha: nó là một hàng trong bảng bus như mọi tiến trình
    # khác, vì kênh điều khiển `__xime__` đi hai chiều.
    shared = allocate_shared_memory(len(topology.ids))
    try:
        Supervisor(app, topology, bound, shared).run()
    finally:
        shared.close()
