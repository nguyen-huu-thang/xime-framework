from __future__ import annotations

from xime.core.exception import XimeException


class SwitcherError(XimeException):
    """
    Raised when the Switcher is misused at runtime: switching while the feature
    is disabled, naming an interface that was not bound to a tuple, or selecting
    an implementation that is not one of the interface's declared impls.

    Phát sinh khi dùng sai Switcher lúc runtime: đổi khi tính năng đang tắt, gọi
    interface không bind dạng tuple, hoặc chọn impl không thuộc tuple đã khai báo.
    """


class Switcher:
    """
    Runtime control point for dynamic interface binding. An injectable singleton.

    use(Interface, Impl)  - point the whole app at Impl for Interface.
    reset(Interface)      - restore Interface to its default (first tuple element).
    reset()               - restore every dynamic interface to its default.

    Switching is GLOBAL: it swaps a shared pointer, so every consumer / request /
    coroutine sees the new impl on its next call - a request already in flight is
    switched mid-way too (that is the nature of "global", not a bug). Assignment
    to the pointer dict is atomic under the GIL, so no lock is needed. There is no
    request scope and no ContextVar.

    Điểm điều khiển runtime cho dynamic interface binding (singleton inject được).
    Đổi là TOÀN CỤC: tráo con trỏ dùng chung nên mọi consumer thấy impl mới ở lần
    gọi kế tiếp; request đang chạy dở cũng bị chuyển giữa chừng. Gán dict atomic
    dưới GIL nên không cần lock; không có request scope, không ContextVar.
    """

    def __init__(self, tuples: dict[type, tuple[type, ...]], enabled: bool) -> None:
        self._enabled = enabled
        # interface -> declared impl tuple (first element is the default).
        # interface -> tuple impl đã khai báo (phần tử đầu là mặc định).
        self._tuples: dict[type, tuple[type, ...]] = dict(tuples)
        # interface -> currently selected impl type. Default = first element.
        # interface -> impl đang chọn. Mặc định = phần tử đầu.
        self._current: dict[type, type] = {
            interface: impls[0] for interface, impls in self._tuples.items()
        }

    def current(self, interface: type) -> type:
        """Return the impl type currently selected for interface (read by the proxy)."""
        return self._current[interface]

    def use(self, interface: type, implementation: type) -> None:
        """
        Switch interface to implementation across the whole application.
        implementation must be one of the impls declared in the binding tuple.
        """
        self._require_enabled()
        impls = self._require_known(interface)
        if implementation not in impls:
            allowed = ", ".join(impl.__name__ for impl in impls)
            raise SwitcherError(
                f"\nInvalid dynamic binding switch\n"
                f"  Interface     : {interface.__name__}\n"
                f"  Implementation: {implementation.__name__}\n"
                f"  Allowed       : {allowed}"
            )
        # Atomic dict assignment under the GIL - no lock needed.
        # Gán dict atomic dưới GIL - không cần lock.
        self._current[interface] = implementation

    def reset(self, interface: type | None = None) -> None:
        """Restore one interface, or every dynamic interface when interface is None."""
        self._require_enabled()
        if interface is None:
            for iface, impls in self._tuples.items():
                self._current[iface] = impls[0]
            return
        impls = self._require_known(interface)
        self._current[interface] = impls[0]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise SwitcherError(
                "\nDynamic binding is disabled\n"
                "  Set 'xime.di.dynamic-binding: true' in application.yml to "
                "switch implementations at runtime."
            )

    def _require_known(self, interface: type) -> tuple[type, ...]:
        impls = self._tuples.get(interface)
        if impls is None:
            raise SwitcherError(
                f"\nNot a dynamic interface\n"
                f"  Interface: {interface.__name__}\n"
                f"  Hint     : bind it to a tuple of implementations to make it "
                f"switchable."
            )
        return impls
