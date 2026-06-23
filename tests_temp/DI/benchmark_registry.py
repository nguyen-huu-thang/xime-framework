"""
Micro-benchmark đối chiếu registry mới (dict tự viết) vs cách cũ
(dependency-injector: DynamicContainer + providers.Singleton + tên md5/regex).

Không phải test (tên không bắt đầu bằng `test_` nên pytest bỏ qua). Chạy tay:

    python tests_temp/DI/benchmark_registry.py

Đo hai trục:
  - build : register() + eager-instantiate toàn bộ singleton theo topo order
  - warm  : throughput get() sau khi đã dựng xong (đường nóng runtime của Xime)

Đồ thị phụ thuộc: chuỗi tuyến tính C0 <- C1 <- ... <- C{N-1} (mỗi class 1 dep),
mô phỏng eager build đi đúng topo order nên mỗi dep luôn là cache hit.
"""
import re
import hashlib
import time

try:
    from dependency_injector import containers, providers
    _HAS_DI = True
except ImportError:
    # Thư viện đã được gỡ khỏi dependency (0.6) — chỉ đo backend mới.
    _HAS_DI = False

from xime.core.container.graph import DependencyGraph
from xime.core.container.registry import DependencyRegistry

N = 500          # số class trong chuỗi phụ thuộc
WARM_ROUNDS = 2000   # số vòng quét get() khi đo đường nóng


def build_classes(n):
    """Sinh n class động: C0 không dep, Ci (i>0) phụ thuộc C{i-1}."""
    classes = []
    for i in range(n):
        if i == 0:
            def __init__(self):
                pass
        else:
            def __init__(self, d):
                self.d = d
        cls = type(f"C{i}", (), {"__init__": __init__})
        classes.append(cls)

    resolved = {}
    for i, cls in enumerate(classes):
        resolved[cls] = {} if i == 0 else {"d": classes[i - 1]}
    return classes, resolved


# --------------------------------------------------------------------------
# Backend cũ — tái hiện đúng logic registry trước đây (dependency-injector)
# --------------------------------------------------------------------------

class OldRegistry:
    def __init__(self):
        self._container = containers.DynamicContainer()
        self._provider_map = {}

    def register(self, resolved):
        for cls, deps in resolved.items():
            name = self._unique_name(cls)
            self._provider_map[cls] = name
            kwargs = {
                p: getattr(self._container, self._provider_map[d])
                for p, d in deps.items()
                if d in self._provider_map
            }
            setattr(self._container, name, providers.Singleton(cls, **kwargs))

    def get(self, cls):
        return getattr(self._container, self._provider_map[cls])()

    @staticmethod
    def _unique_name(cls):
        full = f"{cls.__module__}.{cls.__name__}"
        slug = re.sub(r"[^a-z0-9]", "_", full.lower())
        suffix = hashlib.md5(full.encode()).hexdigest()[:6]
        return f"{slug}_{suffix}"


# --------------------------------------------------------------------------
# Đo
# --------------------------------------------------------------------------

def bench_new(classes, resolved):
    t0 = time.perf_counter()
    reg = DependencyRegistry()
    reg.register(resolved, DependencyGraph(resolved))
    for cls in classes:          # eager build theo topo order
        reg.get(cls)
    build = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(WARM_ROUNDS):
        for cls in classes:
            reg.get(cls)
    warm = time.perf_counter() - t0
    return build, warm


def bench_old(classes, resolved):
    t0 = time.perf_counter()
    reg = OldRegistry()
    reg.register(resolved)
    for cls in classes:
        reg.get(cls)
    build = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(WARM_ROUNDS):
        for cls in classes:
            reg.get(cls)
    warm = time.perf_counter() - t0
    return build, warm


def main():
    classes, resolved = build_classes(N)
    gets = WARM_ROUNDS * N

    # Khởi động nóng để loại nhiễu import lần đầu.
    bench_new(*build_classes(N))
    new_build, new_warm = bench_new(classes, resolved)

    print(f"N classes = {N}, warm get() calls = {gets:,}\n")
    print(f"{'':10} {'build (ms)':>14} {'warm total (ms)':>18} {'warm per-get (us)':>20}")
    print(f"{'new':10} {new_build * 1e3:14.3f} {new_warm * 1e3:18.3f} {new_warm / gets * 1e6:20.4f}")

    if not _HAS_DI:
        print("\n(dependency-injector đã gỡ — bỏ qua đối chiếu backend cũ)")
        return

    bench_old(*build_classes(N))
    old_build, old_warm = bench_old(classes, resolved)
    print(f"{'old':10} {old_build * 1e3:14.3f} {old_warm * 1e3:18.3f} {old_warm / gets * 1e6:20.4f}")
    print(f"\nbuild speedup : {old_build / new_build:.2f}x")
    print(f"warm  speedup : {old_warm / new_warm:.2f}x")


if __name__ == "__main__":
    main()
