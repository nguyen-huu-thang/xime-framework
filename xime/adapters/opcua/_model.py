"""Declarative node model for OPC UA.

The same idea as the Modbus device model, but the problem it solves is smaller:
OPC UA already carries type information, so there is nothing to decode. What a
model buys here is a NAME for every NodeId — turning

    await client.read_values([client.get_node("ns=2;s=Tank.Level")])

into

    tank = await opcua.read_model(Tank)
    tank.level

and giving @on_node_change something to point at that a rename can follow.
Model ở đây không phải để giải mã (OPC UA đã mang kiểu) mà để ĐẶT TÊN cho NodeId.

    @node_model
    class Tank:
        level:    float = Node("ns=2;s=Tank.Level")
        setpoint: float = Node("ns=2;s=Tank.Setpoint")

This module is pure Python: importing a model does not require asyncua.
"""

from __future__ import annotations

import typing
from typing import Any

# Attribute holding the NodeModelInfo built by @node_model.
NODE_MODEL_ATTR = "_xime_opcua_model"


class OpcuaNode:
    """One node of a model: its NodeId and how it behaves.

    A data descriptor, like ModbusField, so `Tank.level` is the node itself
    (for @on_node_change and writes) while `tank.level` is the value.
    Data descriptor: truy cập qua CLASS ra node, qua INSTANCE ra giá trị.
    """

    __slots__ = (
        "node_id", "name", "writable", "default", "declared_type",
        "_attr", "_owner_info",
    )

    def __init__(
        self,
        node_id: str,
        *,
        writable: bool = True,
        default: Any = None,
    ) -> None:
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(
                "a node needs a NodeId string, e.g. Node('ns=2;s=Tank.Level')"
            )
        if "=" not in node_id:
            raise ValueError(
                f"{node_id!r} does not look like a NodeId. Expected forms are "
                f"'ns=<n>;s=<string>', 'ns=<n>;i=<int>', 'i=<int>', "
                f"'ns=<n>;g=<guid>' or 'ns=<n>;b=<bytes>'."
            )
        self.node_id = node_id
        self.writable = writable
        # Initial value used when Xime SERVES this node; ignored on the client
        # side, where the server owns the value.
        # Giá trị khởi tạo khi Xime làm server; phía client bỏ qua.
        self.default = default
        self.name = ""
        # The Python type written next to the node in the model body
        # (`level: float = Node(...)`), filled in by @node_model. Only the
        # SERVER side uses it, to create a variable of the right OPC UA type.
        # Kiểu Python khai cạnh node trong thân model; chỉ phía SERVER dùng.
        self.declared_type: Any = None
        self._attr = ""
        self._owner_info: NodeModelInfo | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        self._attr = f"__xime_opcua_{name}"

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        return getattr(obj, self._attr, None)

    def __set__(self, obj: Any, value: Any) -> None:
        setattr(obj, self._attr, value)

    def __repr__(self) -> str:
        return f"Node(name={self.name!r}, node_id={self.node_id!r})"


def Node(  # noqa: N802 - reads as a type in model declarations
    node_id: str,
    *,
    writable: bool = True,
    default: Any = None,
) -> Any:
    """Declare one OPC UA node inside a @node_model class."""
    return OpcuaNode(node_id, writable=writable, default=default)


class NodeModelInfo:
    """Everything the adapter needs to know about one node model class."""

    __slots__ = ("cls", "nodes", "namespace")

    def __init__(self, cls: type, nodes: dict[str, OpcuaNode], namespace: str | None):
        self.cls = cls
        self.nodes = nodes
        self.namespace = namespace

    def node_ids(self) -> list[str]:
        return [node.node_id for node in self.nodes.values()]

    def __repr__(self) -> str:
        return f"NodeModelInfo(cls={self.cls.__name__}, nodes={list(self.nodes)})"


def node_model(cls: type | None = None, *, namespace: str | None = None):
    """Mark a class as an OPC UA node model.

        @node_model
        class Tank:
            level: float = Node("ns=2;s=Tank.Level")

        @node_model(namespace="http://plant.example/tanks")
        class Tank:
            ...

    `namespace` is only used when Xime SERVES the model: the server registers
    that URI and the nodes are created under it. Clients address nodes by the
    NodeId string as written.
    `namespace` chỉ dùng khi Xime làm SERVER.
    """

    def decorator(target: type) -> type:
        nodes = _collect_nodes(target)
        if not nodes:
            raise ValueError(
                f"@node_model class '{target.__name__}' declares no nodes. Add "
                f"at least one, e.g. `level: float = Node('ns=2;s=Tank.Level')`."
            )
        _check_unique(target, nodes)

        info = NodeModelInfo(target, nodes, namespace)
        for node in nodes.values():
            if node._owner_info is None:
                node._owner_info = info
        setattr(target, NODE_MODEL_ATTR, info)

        if "__init__" not in target.__dict__:
            target.__init__ = _make_init(nodes)  # type: ignore[method-assign]
        if "__repr__" not in target.__dict__:
            target.__repr__ = _make_repr(nodes)  # type: ignore[method-assign]
        return target

    if cls is not None:          # used bare: @node_model
        return decorator(cls)
    return decorator             # used with arguments: @node_model(namespace=...)


def get_node_model_info(target: Any) -> NodeModelInfo | None:
    """Return the NodeModelInfo of a model class (or instance), or None."""
    cls = target if isinstance(target, type) else type(target)
    return getattr(cls, NODE_MODEL_ATTR, None)


def require_node_model_info(target: Any) -> NodeModelInfo:
    """Like get_node_model_info but fails with an actionable message."""
    info = get_node_model_info(target)
    if info is None:
        name = getattr(target, "__name__", type(target).__name__)
        raise TypeError(
            f"'{name}' is not an OPC UA node model. Decorate the class with "
            f"@node_model from xime.adapters.opcua."
        )
    return info


def _collect_nodes(cls: type) -> dict[str, OpcuaNode]:
    nodes: dict[str, OpcuaNode] = {}
    for klass in reversed(cls.__mro__):
        for name, value in vars(klass).items():
            if isinstance(value, OpcuaNode):
                if not value.name:
                    value.__set_name__(klass, name)
                nodes[name] = value
    _attach_declared_types(cls, nodes)
    return nodes


def _attach_declared_types(cls: type, nodes: dict[str, OpcuaNode]) -> None:
    """Record the Python type annotated next to each node.

    OPC UA variables are strongly typed and take that type from the value they
    are created with, so a server needs to know whether `running` is a bool
    before any value exists. The annotation the model already carries
    (`running: bool = Node(...)`) is that information; without reading it, every
    node was created as a Double and publishing a bool or a string failed with
    BadTypeMismatch on the first refresh.
    Biến OPC UA có kiểu chặt, lấy từ giá trị lúc tạo - nên server phải biết
    `running` là bool TRƯỚC khi có giá trị nào. Không đọc annotation thì mọi node
    bị tạo kiểu Double và đẩy bool/chuỗi sẽ hỏng ngay lần refresh đầu.

    Unresolvable annotations are left as None; the server then asks for an
    explicit `default=` rather than guessing.
    """
    try:
        hints = typing.get_type_hints(cls)
    except Exception:  # pragma: no cover - unresolvable forward reference
        return
    for name, node in nodes.items():
        if node.declared_type is None:
            node.declared_type = hints.get(name)


def _check_unique(cls: type, nodes: dict[str, OpcuaNode]) -> None:
    """Two attributes on one NodeId is almost always a copy-paste slip.

    Left alone, both attributes silently track the same value and the mistake
    only shows up as two fields that mysteriously always agree.
    """
    seen: dict[str, str] = {}
    for name, node in nodes.items():
        previous = seen.get(node.node_id)
        if previous is not None:
            raise ValueError(
                f"\nDuplicate NodeId in '{cls.__name__}'\n"
                f"  NodeId: {node.node_id}\n"
                f"  Fields: {previous}, {name}\n"
                f"  Fix   : give them distinct NodeIds, or remove one."
            )
        seen[node.node_id] = name


def _make_init(nodes: dict[str, OpcuaNode]):
    names = tuple(nodes)

    def __init__(self: Any, **values: Any) -> None:
        unknown = set(values) - set(names)
        if unknown:
            raise TypeError(
                f"{type(self).__name__} got unexpected node(s) {sorted(unknown)}; "
                f"known nodes: {list(names)}"
            )
        for name in names:
            setattr(self, name, values.get(name))

    return __init__


def _make_repr(nodes: dict[str, OpcuaNode]):
    names = tuple(nodes)

    def __repr__(self: Any) -> str:
        body = ", ".join(f"{n}={getattr(self, n)!r}" for n in names)
        return f"{type(self).__name__}({body})"

    return __repr__
