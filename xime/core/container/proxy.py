from __future__ import annotations

from collections.abc import Callable

from xime.core.container.switcher import Switcher

# Framework lifecycle hook names the proxy must NOT forward. PostConstruct and
# PreDestroy are runtime_checkable Protocols that test for exactly these
# attributes; if the proxy forwarded them, isinstance(proxy, PostConstruct)
# would see the current impl's hook and LifecycleManager would run it a second
# time (the impl already runs its own hook directly).
# Tên hook lifecycle proxy KHÔNG được forward. PostConstruct/PreDestroy là
# Protocol runtime_checkable kiểm đúng các thuộc tính này; nếu proxy forward,
# isinstance(proxy, PostConstruct) sẽ thấy hook của impl và LifecycleManager chạy
# lần hai (impl đã tự chạy hook của nó rồi).
_RESERVED = frozenset({"post_construct", "pre_destroy"})


class DynamicProxy:
    """
    Transparent stand-in injected for a Protocol that is bound to several impls
    while dynamic binding is enabled. Consumers keep their original code
    (`self.gateway.charge(x)`); every attribute access is forwarded to whichever
    implementation the Switcher currently points at.

    Proxy trong suốt được inject thay cho một Protocol bind nhiều impl khi bật
    dynamic binding. Consumer giữ nguyên code; mọi truy cập thuộc tính được
    forward tới impl mà Switcher đang trỏ tới.

    One proxy singleton per interface. Forwarding reads the current impl type
    from the Switcher and resolves its singleton through the container, so plain
    methods, async methods and properties all work unchanged.

    Caveat: syntax that bypasses instance __getattr__ (e.g. isinstance against a
    non-runtime_checkable Protocol, or dunder access via special-method slots)
    does not see the impl. Everyday services only call declared methods, so this
    is rarely an issue.

    Caveat on startup ordering: a consumer depends on this proxy, not on the
    implementations, so the dependency graph holds no edge from the consumer to
    any impl and their relative post_construct order is undefined. Every
    post_construct still runs during startup, so requests served afterwards are
    unaffected; the only exposure is a consumer that calls into the impl from
    inside its own post_construct, where the impl may be constructed but not yet
    initialised. Do that work lazily (on first use) instead.

    Caveat về thứ tự lúc startup: consumer phụ thuộc proxy này chứ không phụ
    thuộc các impl, nên dependency graph không có cạnh consumer -> impl và thứ tự
    post_construct giữa hai bên là không xác định. Mọi post_construct vẫn chạy
    đủ trong startup nên request sau đó không ảnh hưởng; rủi ro duy nhất là
    consumer gọi vào impl ngay trong post_construct của chính nó - lúc đó impl có
    thể đã dựng nhưng chưa khởi tạo xong. Hãy làm việc đó lười (lúc dùng lần đầu).
    """

    __slots__ = ("_interface", "_switcher", "_resolver")

    def __init__(
        self,
        interface: type,
        switcher: Switcher,
        resolver: Callable[[type], object],
    ) -> None:
        # object.__setattr__ keeps these slots out of the __getattr__ path below.
        # object.__setattr__ để các slot này không đi qua __getattr__ phía dưới.
        object.__setattr__(self, "_interface", interface)
        object.__setattr__(self, "_switcher", switcher)
        object.__setattr__(self, "_resolver", resolver)

    def __getattr__(self, name: str) -> object:
        # __getattr__ runs only for attributes not found normally; the three
        # slots above are found normally, so there is no recursion here.
        # __getattr__ chỉ chạy khi không tìm thấy thuộc tính theo cách thường; ba
        # slot trên tìm thấy theo cách thường nên không có đệ quy ở đây.
        if name in _RESERVED:
            raise AttributeError(name)
        impl_type = self._switcher.current(self._interface)
        target = self._resolver(impl_type)
        return getattr(target, name)
