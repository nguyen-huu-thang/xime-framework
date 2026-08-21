"""Khối `processes:` - ai mở cửa nào, ở cổng nào.

Nguyên lý trung tâm của mô hình đa tiến trình (0.8): **không id tiến trình nào
xuất hiện trong code**. `main.py` khai *ứng dụng này CÓ những cửa nào*; khối
`processes:` khai *tiến trình nào ĐANG mở cửa nào ở cổng nào*.

```yaml
processes:
  main:
    primary: true
    web:  { default:  { host: 0.0.0.0,   port: 8086, shared: true } }
    grpc: { internal: { host: 127.0.0.1, port: 9095 } }
    socket: { rpc:    { path: /run/xime/data-main.sock } }

  workers:
    count: 3                       # sinh workers-1, workers-2, workers-3
    web:  { default:  { host: 0.0.0.0, port: 8086, shared: true } }
    grpc: { internal: { host: 127.0.0.1, port: 9095, shared: true } }
```

Ba tầng khoá: **id tiến trình** -> **loại adapter** -> **id adapter**. Cổng thuộc
về **cặp** `(tiến trình, adapter)`, không thuộc riêng cái nào - đó là lý do trước
nay phải truyền cổng vào constructor, và là lý do nay cấm.

⚠ Module này **không biết adapter nào tồn tại**. Nó đọc YAML thành cấu trúc và
kiểm những thứ tự kiểm được; phép kiểm cần biết `main.py` khai gì thì nằm ở
`_supervisor.py`, nơi có danh sách adapter.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from xime.core.exception.framework import StartupException

# Biến môi trường mang id tiến trình xuống con. Dùng env chứ không dùng
# `sys.argv` vì `argv` là chỗ ứng dụng có thể tự dùng, còn env thì thừa kế tự
# nhiên và **có mặt trước mọi lệnh import** - tức trước cả khi `config/` chạy.
PROCESS_ID_ENV: Final[str] = "XIME_PROCESS_ID"

# Khoá dành riêng trong một khối tiến trình; mọi khoá khác là một LOẠI adapter.
_RESERVED_KEYS: Final[frozenset[str]] = frozenset({"primary", "count"})

# Id tiến trình đi vào tên tiến trình, vào mọi dòng log, và (khi có) vào
# `/healthz`. Giữ nó ở tập ký tự an toàn để không phải nghĩ về escaping ở bốn
# chỗ khác nhau.
_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class EndpointSpec:
    """Một ô trong ma trận `tiến trình x adapter`.

    Attributes:
        kind: loại adapter (`web`, `grpc`, `socket`, `mqtt`...) - chính là khoá
            tầng hai trong YAML, và là giá trị `adapter_kind` của adapter.
        adapter_id: id tầng ba (`default`, `internal`, `rpc`...).
        host / port: cho điểm phục vụ TCP.
        path: cho điểm phục vụ unix socket.
        shared: **khai tường minh**, vì *"bind thành công"* mang hai nghĩa - *tôi
            độc chiếm cổng này* và *tôi đang chia cổng với người khác*. Không có
            cờ này thì khai nhầm trùng cổng sẽ chạy êm trên Linux
            (`SO_REUSEPORT` mặc định của gRPC) và một nửa request đi nhầm chỗ.
        options: **nguyên văn** ô YAML. Framework tìm đúng ô; adapter hiểu ô đó.
    """

    kind: str
    adapter_id: str
    host: str | None
    port: int | None
    path: str | None
    shared: bool
    options: Mapping[str, Any]

    @property
    def key(self) -> tuple[str, str]:
        """Khoá tra trong một khối: `(loại, id)`."""
        return (self.kind, self.adapter_id)

    @property
    def listens(self) -> bool:
        """Ô này có mở một cổng hay đường dẫn nào không.

        ⚠ Hỏi sai câu thì hỏng theo hai chiều khác nhau: một adapter **kết nối
        RA** (mqtt, modbus, opcua) không mở cổng nào, nên đòi nó khai cổng là
        đòi thứ không tồn tại - đó là supervisor **ca 2**, ca DỄ hơn ca 1 chứ
        không phải khó hơn.
        """
        return self.port is not None or self.path is not None

    @property
    def endpoint(self) -> tuple[str, Any]:
        """Danh tính của cái socket mà ô này trỏ tới.

        Hai ô cùng danh tính là **cùng một socket**, nên chúng phải cùng khai
        `shared` và cùng `host`. Cố ý bỏ `host` ra khỏi danh tính TCP: cùng cổng
        mà khác host thì vẫn va nhau lúc bind (`0.0.0.0:8086` nuốt luôn
        `127.0.0.1:8086`), nên gộp chúng làm một danh tính rồi kiểm host riêng
        cho ra thông báo đúng bệnh.
        """
        if self.path is not None:
            return ("unix", self.path)
        return ("tcp", self.port)


@dataclass(frozen=True)
class ProcessBlock:
    """Một tiến trình: id, có phải primary không, và các ô của nó."""

    process_id: str
    primary: bool
    endpoints: Mapping[tuple[str, str], EndpointSpec]

    def spec_for(self, kind: str, adapter_id: str) -> EndpointSpec | None:
        return self.endpoints.get((kind, adapter_id))


@dataclass(frozen=True)
class ProcessTopology:
    """Toàn bộ khối `processes:` sau khi đã bung `count:` và kiểm.

    Mọi tiến trình đọc **cùng một file**, nên mỗi tiến trình tự kiểm được tính
    nhất quán toàn cục **mà không cần nói chuyện với tiến trình nào** - không
    bus, không khoá, không kho.
    """

    blocks: tuple[ProcessBlock, ...]

    def by_id(self, process_id: str) -> ProcessBlock | None:
        for block in self.blocks:
            if block.process_id == process_id:
                return block
        return None

    @property
    def primary_id(self) -> str:
        for block in self.blocks:
            if block.primary:
                return block.process_id
        # Không tới được: parse_topology đã ép đúng một primary.
        raise AssertionError("topology has no primary block")

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(block.process_id for block in self.blocks)

    def specs_for(self, kind: str, adapter_id: str) -> tuple[EndpointSpec, ...]:
        """Mọi ô cùng `(loại, id)` trên khắp các khối."""
        found = []
        for block in self.blocks:
            spec = block.spec_for(kind, adapter_id)
            if spec is not None:
                found.append(spec)
        return tuple(found)

    @property
    def declared_keys(self) -> tuple[tuple[str, str], ...]:
        """Mọi `(loại, id)` xuất hiện ở bất kỳ khối nào, giữ thứ tự gặp."""
        seen: dict[tuple[str, str], None] = {}
        for block in self.blocks:
            for key in block.endpoints:
                seen[key] = None
        return tuple(seen)


def topology_error(title: str, *lines: str) -> StartupException:
    """Khuôn thông báo dùng chung cho mọi phép kiểm của mô hình đa tiến trình."""
    body = "\n".join(f"  {line}" for line in lines)
    return StartupException(f"\n{title}\n{body}")


def _require_mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise topology_error(
            "Invalid processes Block",
            f"Config: {where}",
            f"Found : {type(value).__name__}",
            "Detail: expected a mapping (a nested YAML block).",
        )
    return value


def _validate_id(value: str, where: str) -> str:
    if not _ID_PATTERN.match(value):
        raise topology_error(
            "Invalid processes Identifier",
            f"Config: {where}",
            f"Value : {value!r}",
            "Detail: use letters, digits, '.', '_' or '-', starting with a "
            "letter or digit. The id becomes a process name and a log label.",
        )
    return value


def _parse_endpoint(kind: str, adapter_id: str, raw: Any, where: str) -> EndpointSpec:
    options = _require_mapping(raw, where)

    port = options.get("port")
    if port is not None and (not isinstance(port, int) or isinstance(port, bool)):
        raise topology_error(
            "Invalid Endpoint Port",
            f"Config: {where}.port",
            f"Value : {port!r}",
            "Detail: port must be an integer.",
        )
    path = options.get("path")
    if path is not None and not isinstance(path, str):
        raise topology_error(
            "Invalid Endpoint Path",
            f"Config: {where}.path",
            f"Value : {path!r}",
            "Detail: path must be a string.",
        )
    host = options.get("host")
    if host is not None and not isinstance(host, str):
        raise topology_error(
            "Invalid Endpoint Host",
            f"Config: {where}.host",
            f"Value : {host!r}",
            "Detail: host must be a string.",
        )
    if port is not None and path is not None:
        raise topology_error(
            "Ambiguous Endpoint",
            f"Config: {where}",
            "Detail: declare either port (TCP) or path (unix socket), not both.",
        )

    shared = options.get("shared", False)
    if not isinstance(shared, bool):
        raise topology_error(
            "Invalid shared Flag",
            f"Config: {where}.shared",
            f"Value : {shared!r}",
            "Detail: shared must be true or false. It is declared explicitly "
            "because 'bind succeeded' otherwise means two different things.",
        )

    spec = EndpointSpec(
        kind=kind,
        adapter_id=adapter_id,
        host=host,
        port=port,
        path=path,
        shared=shared,
        options=dict(options),
    )
    if shared and not spec.listens:
        raise topology_error(
            "shared Without An Address",
            f"Config: {where}.shared",
            "Detail: shared only means something for an endpoint that binds a "
            "port or a unix socket path. This block declares neither.",
        )
    return spec


def _parse_block(
    process_id: str, raw: Mapping[str, Any], *, primary: bool
) -> ProcessBlock:
    endpoints: dict[tuple[str, str], EndpointSpec] = {}
    for kind, kind_raw in raw.items():
        if kind in _RESERVED_KEYS:
            continue
        where_kind = f"processes.{process_id}.{kind}"
        _validate_id(str(kind), where_kind)
        for adapter_id, endpoint_raw in _require_mapping(kind_raw, where_kind).items():
            where = f"{where_kind}.{adapter_id}"
            _validate_id(str(adapter_id), where)
            endpoints[(str(kind), str(adapter_id))] = _parse_endpoint(
                str(kind), str(adapter_id), endpoint_raw, where
            )
    _reject_duplicate_endpoint_within_block(process_id, endpoints)
    return ProcessBlock(process_id=process_id, primary=primary, endpoints=endpoints)


def _reject_duplicate_endpoint_within_block(
    process_id: str, endpoints: Mapping[tuple[str, str], EndpointSpec]
) -> None:
    """Hai adapter của CÙNG một tiến trình không được trỏ vào cùng một socket.

    `shared` không cứu được ca này: nó nói *"tôi chia cổng với tiến trình
    khác"*, không nói *"tôi chia cổng với chính tôi"*, và một tiến trình mở hai
    server trên cùng một cổng thì không request nào biết mình nên vào đâu.
    """
    seen: dict[tuple[str, Any], EndpointSpec] = {}
    for spec in endpoints.values():
        if not spec.listens:
            continue
        previous = seen.get(spec.endpoint)
        if previous is not None:
            raise topology_error(
                "Duplicate Address In One Process",
                f"Process : {process_id}",
                f"Address : {spec.endpoint[0]} {spec.endpoint[1]}",
                f"Declared: {previous.kind}.{previous.adapter_id} "
                f"and {spec.kind}.{spec.adapter_id}",
                "Detail  : two adapters in the same process cannot bind the "
                "same address.",
            )
        seen[spec.endpoint] = spec


def _expand_count(name: str, raw: Mapping[str, Any]) -> list[tuple[str, bool]]:
    """Bung `count: N` thành `name-1 .. name-N`.

    Id sinh ra phải **xác định** vì nó là nhãn trong mọi dòng log; không tự sinh
    dải cổng vì đó là lấn sang việc của sổ đăng ký mạng, và người vận hành sẽ có
    N cổng không ai đăng ký.
    """
    count = raw.get("count", 1)
    if not isinstance(count, int) or isinstance(count, bool):
        raise topology_error(
            "Invalid count",
            f"Config: processes.{name}.count",
            f"Value : {count!r}",
            "Detail: count must be an integer.",
        )
    if count < 1:
        raise topology_error(
            "Invalid count",
            f"Config: processes.{name}.count",
            f"Value : {count}",
            "Detail: count must be at least 1.",
        )
    primary = raw.get("primary", False)
    if not isinstance(primary, bool):
        raise topology_error(
            "Invalid primary Flag",
            f"Config: processes.{name}.primary",
            f"Value : {primary!r}",
            "Detail: primary must be true or false.",
        )
    if count == 1:
        return [(name, primary)]
    if primary:
        raise topology_error(
            "primary On A count Block",
            f"Config: processes.{name}",
            f"Detail: count is {count}, so this block expands into "
            f"{name}-1 .. {name}-{count} and 'primary: true' would not say "
            "which one. Give the primary process its own block.",
        )
    return [(f"{name}-{index}", False) for index in range(1, count + 1)]


def _reject_unshared_ports_under_count(name: str, block: ProcessBlock) -> None:
    for spec in block.endpoints.values():
        if spec.listens and not spec.shared:
            raise topology_error(
                "count With A Private Address",
                f"Config: processes.{name}.{spec.kind}.{spec.adapter_id}",
                "Detail: every process this block expands into would bind the "
                "same address, so each listening endpoint must declare "
                "'shared: true'. Xime does not invent a port range - that would "
                "leave you with ports nobody registered.",
            )


def parse_topology(raw_processes: Any) -> ProcessTopology:
    """Đọc khối `processes:` thành `ProcessTopology`, kiểm mọi thứ tự kiểm được.

    Phép kiểm cần biết `main.py` khai adapter nào thì **không** ở đây - xem
    `validate_against_adapters()` trong `_supervisor.py`.
    """
    processes = _require_mapping(raw_processes, "processes")
    if not processes:
        raise topology_error(
            "Empty processes Block",
            "Config: processes",
            "Detail: declare at least one process block, or remove the key and "
            "do not call share_load().",
        )

    blocks: list[ProcessBlock] = []
    for raw_name, raw in processes.items():
        name = _validate_id(str(raw_name), f"processes.{raw_name}")
        block_raw = _require_mapping(raw, f"processes.{name}")
        for process_id, primary in _expand_count(name, block_raw):
            block = _parse_block(process_id, block_raw, primary=primary)
            if process_id != name:
                _reject_unshared_ports_under_count(name, block)
            blocks.append(block)

    _reject_duplicate_ids(blocks)
    _require_exactly_one_primary(blocks)
    _reject_conflicting_endpoints(blocks)
    return ProcessTopology(blocks=tuple(blocks))


def _reject_duplicate_ids(blocks: list[ProcessBlock]) -> None:
    """`count: 2` trên khối `api` cộng một khối tên `api-1` là hai id trùng nhau."""
    seen: set[str] = set()
    for block in blocks:
        if block.process_id in seen:
            raise topology_error(
                "Duplicate Process Id",
                f"Process: {block.process_id}",
                "Detail : two blocks resolve to the same id. Remember that "
                "'count: N' on block 'x' produces x-1 .. x-N.",
            )
        seen.add(block.process_id)


def _require_exactly_one_primary(blocks: list[ProcessBlock]) -> None:
    """Phép kiểm 1: đúng một khối `primary: true`.

    Khai tường minh chứ không dựa thứ tự trong file: thứ tự YAML mang ý nghĩa là
    một phụ thuộc ngầm, và sắp xếp lại cho gọn mắt sẽ đổi hành vi mà không gì
    báo.
    """
    primaries = [block.process_id for block in blocks if block.primary]
    if len(primaries) == 1:
        return
    if not primaries:
        raise topology_error(
            "No primary Process",
            f"Blocks: {', '.join(block.process_id for block in blocks)}",
            "Detail: exactly one process block must declare 'primary: true'. "
            "It is the process that runs whatever must run only once.",
        )
    raise topology_error(
        "Multiple primary Processes",
        f"Blocks: {', '.join(primaries)}",
        "Detail: exactly one process block may declare 'primary: true'.",
    )


def _reject_conflicting_endpoints(blocks: list[ProcessBlock]) -> None:
    """Phép kiểm 4: cùng một socket ở hai khối thì phải khai `shared` cả hai.

    Đây là bản vá cho chỗ *"bind thành công"* mang hai nghĩa: khai nhầm trùng
    cổng thì Windows báo ngay, còn Linux chạy êm (gRPC bật `SO_REUSEPORT` mặc
    định) và một nửa request đi vào tiến trình không định gửi tới.
    """
    groups: dict[tuple[str, Any], list[tuple[str, EndpointSpec]]] = {}
    for block in blocks:
        for spec in block.endpoints.values():
            if spec.listens:
                groups.setdefault(spec.endpoint, []).append((block.process_id, spec))

    for endpoint, entries in groups.items():
        if len(entries) < 2:
            continue
        where = f"{endpoint[0]} {endpoint[1]}"
        unshared = [pid for pid, spec in entries if not spec.shared]
        if unshared:
            raise topology_error(
                "Address Used By Several Processes",
                f"Address  : {where}",
                f"Processes: {', '.join(pid for pid, _ in entries)}",
                f"Missing  : 'shared: true' in {', '.join(unshared)}",
                "Detail   : declare it in every block that uses the address, or "
                "give each process its own address.",
            )
        hosts = {spec.host for _, spec in entries}
        if len(hosts) > 1:
            listed = ", ".join(repr(host) for host in sorted(hosts, key=str))
            raise topology_error(
                "Shared Address With Different Hosts",
                f"Address  : {where}",
                f"Processes: {', '.join(pid for pid, _ in entries)}",
                f"Hosts    : {listed}",
                "Detail   : a shared address is one socket, so every block must "
                "bind it on the same host.",
            )
        kinds = {(spec.kind, spec.adapter_id) for _, spec in entries}
        if len(kinds) > 1:
            listed = ", ".join(f"{kind}.{aid}" for kind, aid in sorted(kinds))
            raise topology_error(
                "Shared Address Across Different Adapters",
                f"Address : {where}",
                f"Declared: {listed}",
                "Detail  : a shared address is one socket served by one kind of "
                "adapter. Two different adapters cannot share it.",
            )


# ----------------------------------------------------------------------
# Một tiến trình: khối `process:` (số ít), và phép dịch khoá phẳng cũ
# ----------------------------------------------------------------------

SINGLE_KEY: Final[str] = "process"
MULTI_KEY: Final[str] = "processes"

# Id nội bộ của khối `process:`. Người viết cấu hình không đặt tên nó - một
# tiến trình duy nhất thì cái tên không phân biệt được với cái gì cả. Framework
# vẫn cần một nhãn cho log và cho `by_id()`.
SINGLE_PROCESS_ID: Final[str] = "main"

# Khoá chỉ có nghĩa khi có NHIỀU tiến trình. Khai chúng ở khối `process:` là
# lỗi, không phải bỏ qua: một khoá bị bỏ qua im lặng là chỗ để người ta tin vào
# thứ không xảy ra.
_MULTI_ONLY_PROCESS_KEYS: Final[tuple[str, ...]] = ("primary", "count")
_MULTI_ONLY_ENDPOINT_KEYS: Final[tuple[str, ...]] = ("shared",)


def parse_single(raw_process: Any) -> ProcessTopology:
    """Đọc khối `process:` - một tiến trình, nhiều điểm phục vụ.

    Bên trong **giống hệt** một khối của `processes:`, trừ những khoá chỉ có
    nghĩa khi có nhiều tiến trình. Đi từ một sang nhiều là đổi `process:` thành
    `processes:`, thụt vào một cấp và đặt tên - không sửa lại gì bên trong.
    """
    block_raw = _require_mapping(raw_process, SINGLE_KEY)
    for key in _MULTI_ONLY_PROCESS_KEYS:
        if key in block_raw:
            raise topology_error(
                f"{key} In A Single-Process Block",
                f"Config: {SINGLE_KEY}.{key}",
                f"Detail: {_why_multi_only(key)}",
            )
    block = _parse_block(SINGLE_PROCESS_ID, block_raw, primary=True)
    for spec in block.endpoints.values():
        for key in _MULTI_ONLY_ENDPOINT_KEYS:
            if key in spec.options:
                raise topology_error(
                    f"{key} In A Single-Process Block",
                    f"Config: {SINGLE_KEY}.{spec.kind}.{spec.adapter_id}.{key}",
                    f"Detail: {_why_multi_only(key)}",
                )
    return ProcessTopology(blocks=(block,))


def _why_multi_only(key: str) -> str:
    return {
        "primary": "the only process is always the primary one, so saying so "
        "adds nothing. Drop the key.",
        "count": "nothing spawns children without share_load(), so a count "
        "above one cannot happen. Use processes: and share_load() instead.",
        "shared": "sharing one address needs at least two processes. With a "
        "single process there is nobody to share it with.",
    }[key]


# Khoá phẳng cũ và ô tương ứng. 58/69 file cấu hình trong workspace dùng
# `server:`, nên đây là hiện thực đông nhất - không bắt ai sửa.
_FLAT_SOURCES: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    # loại adapter -> (khoá phẳng, các khoá con chép sang ô)
    "web": ("server", ("host", "port", "ssl")),
    "grpc": ("grpc", ("port", "tls")),
}

# ⭐⭐ Cổng mặc định của khoá phẳng - KHÔI PHỤC hợp đồng có từ trước 0.8.
#
# Trước 0.8, khối `server:` và khối `grpc:` đều **tuỳ chọn**: vắng mặt thì
# `WebServerConfig()` cho `0.0.0.0:8080` và `GrpcServerConfig()` cho `:50051`,
# và ứng dụng chạy. Docstring của `GrpcServerConfig` nói thẳng: *"All fields
# have sensible defaults so the block is optional."*
#
# Bản dịch khoá phẳng của 0.8 làm rơi mất phần đó, nên một `application.yml`
# không khai `server:` chết lúc khởi động với "Web Endpoint Without A Port".
# Chính dự án do `xime init` sinh ra rơi vào đúng ca này - trình tạo cố ý để
# `server:` ở dạng chú thích, vì cổng là thứ **framework mặc định được**.
#
# ⚠ Vì sao chỉ khôi phục ở ĐƯỜNG PHẲNG, không áp cho `process:`/`processes:`:
# hai đường trả lời hai câu khác nhau. Vắng `server:` nghĩa là *"tôi không nói
# gì về mạng, cho tôi mặc định"* - đó là hợp đồng cũ. Còn viết
# `process: web: { default: {} }` nghĩa là *"tôi đang mô tả topology"*, và ở đó
# một ô thiếu địa chỉ nhiều khả năng là gõ nhầm (`porrt:`) chứ không phải ý
# muốn dùng mặc định - khoá lạ hiện chưa bị từ chối, nên chính thông báo
# "Endpoint Without A Port" là thứ duy nhất bắt được nó.
#
# Đo 2026-08-20: 27/27 app trong workspace đều đã khai `server:`, nên bản vá
# này không đổi hành vi của app nào ở đây; nó cứu người dùng ngoài và cứu
# trình tạo.
_FLAT_DEFAULT_PORTS: Final[dict[str, int]] = {
    "web": 8080,
    "grpc": 50051,
}


def synthesize_from_flat(
    read: Any, declared: Iterable[tuple[str, str]]
) -> ProcessTopology:
    """Dựng một topology một-tiến-trình từ khoá phẳng cũ (`server:`, `grpc:`).

    ⭐ Đây là một phép **DỊCH**, không phải một nhánh xử lý thứ hai. Dịch xong
    thì từ đó trở đi chỉ còn một đường code, và khoá phẳng **không thể trôi
    lệch** vì nó chỉ diễn tả nổi một điểm phục vụ mỗi loại.

    `read` là `RuntimeConfig.get`; nhận vào để module này không phải biết kiểu
    cấu hình của core.
    """
    endpoints: dict[tuple[str, str], EndpointSpec] = {}
    for kind, adapter_id in declared:
        options: dict[str, Any] = {}
        source = _FLAT_SOURCES.get(kind)
        if source is not None:
            flat_key, fields = source
            if adapter_id != "default":
                raise topology_error(
                    "A Second Endpoint Needs The process Block",
                    f"Adapter: {kind}.{adapter_id}",
                    f"Detail : the flat `{flat_key}:` key describes exactly one "
                    f"{kind} endpoint, so there is nowhere for this one to get "
                    f"an address. Declare it under `{SINGLE_KEY}:`:",
                    "",
                    f"    {SINGLE_KEY}:",
                    f"      {kind}:",
                    f"        {adapter_id}: {{ host: 127.0.0.1, port: 8081 }}",
                )
            for field in fields:
                value = read(f"{flat_key}.{field}")
                if value is not None:
                    options[field] = value
            if "port" not in options and kind in _FLAT_DEFAULT_PORTS:
                options["port"] = _FLAT_DEFAULT_PORTS[kind]
        endpoints[(kind, adapter_id)] = _parse_endpoint(
            kind, adapter_id, options, f"{flat_key if source else kind}"
        )
    block = ProcessBlock(
        process_id=SINGLE_PROCESS_ID, primary=True, endpoints=endpoints
    )
    _reject_duplicate_endpoint_within_block(SINGLE_PROCESS_ID, endpoints)
    return ProcessTopology(blocks=(block,))


def build_topology(
    read: Any, declared: Iterable[tuple[str, str]], *, share_load: bool
) -> ProcessTopology:
    """Một cửa duy nhất dựng topology, cho cả ba nhánh của `run()`.

    | Cấu hình | `share_load()` | |
    |---|---|---|
    | `process:` | không | một tiến trình, nhiều điểm phục vụ |
    | `processes:` | có | nhiều tiến trình |
    | khoá phẳng cũ | không | dịch thành một khối `process:` |

    ⚠ `process` và `processes` khác nhau **đúng một ký tự**, nên gõ nhầm phải
    bắt được ở **cả hai chiều** - không tổ hợp nào được chạy êm mà sai.
    """
    single = read(SINGLE_KEY)
    multi = read(MULTI_KEY)

    if single is not None and multi is not None:
        raise topology_error(
            "Both process And processes Are Declared",
            f"Detail: `{SINGLE_KEY}:` describes one process, `{MULTI_KEY}:` "
            "describes several. Two sources for the same thing is exactly the "
            "shape this design removes. Keep one.",
        )

    if share_load:
        if multi is None:
            raise topology_error(
                "share_load Without A processes Block",
                f"Detail: share_load() reads `{MULTI_KEY}:` to learn which "
                "processes exist and which addresses each one serves."
                + (
                    f" You declared `{SINGLE_KEY}:`, which describes a single "
                    f"process - rename it to `{MULTI_KEY}:` and give the block "
                    "a name."
                    if single is not None
                    else " Add one, or drop share_load() to run as a single "
                    "process."
                ),
            )
        return parse_topology(multi)

    if multi is not None:
        raise topology_error(
            "processes Block Without share_load",
            f"Config: {MULTI_KEY}",
            f"Detail: `{MULTI_KEY}:` declares several processes but nothing "
            "spawns them - main.py never calls share_load(), so the ports "
            f"declared there have no effect. Either call "
            f"app.share_load().run(), or use `{SINGLE_KEY}:` for one process.",
        )
    if single is not None:
        return parse_single(single)
    return synthesize_from_flat(read, declared)
