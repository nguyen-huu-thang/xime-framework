from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CodeFirstConfig:
    """One registered code-first gRPC unit (set of packages + output settings)."""

    packages: list[str]
    output_dir: str = "generated"
    lock_file: str = "proto.lock.json"
    proto_package: str | None = None  # reserved for future per-unit override


class _CodeFirstRegistry:
    """Module-level singleton read by the CLI and GrpcAdapter.

    Holds the packages that contain code-first controllers plus where to write
    generated artifacts. Follows the explicit-call pattern of the other
    configure_* helpers — no auto-scan magic.
    Singleton module-level: gói chứa controller code-first + nơi ghi artifact.
    """

    def __init__(self) -> None:
        self._units: list[CodeFirstConfig] = []

    def register(self, config: CodeFirstConfig) -> None:
        self._units.append(config)

    def get_units(self) -> list[CodeFirstConfig]:
        return list(self._units)

    def get_packages(self) -> list[str]:
        packages: list[str] = []
        for unit in self._units:
            packages.extend(unit.packages)
        return packages

    # The output dir / lock file are global for the project; use the first unit
    # that sets them, defaulting otherwise.
    # output dir / lock file mang tính toàn dự án — lấy unit đầu tiên đặt.
    def output_dir(self) -> str:
        return self._units[0].output_dir if self._units else "generated"

    def lock_file(self) -> str:
        return self._units[0].lock_file if self._units else "proto.lock.json"

    def reset(self) -> None:
        self._units.clear()


codefirst_registry = _CodeFirstRegistry()


def configure_grpc_codefirst(
    packages: list[str],
    output_dir: str = "generated",
    lock_file: str = "proto.lock.json",
) -> None:
    """Register packages of code-first gRPC controllers.

    Call once in your config layer (e.g. config/grpc.py). The CLI (`xime grpc
    generate` / `check`) and GrpcAdapter both read this registry.
    Gọi một lần trong config layer; CLI và GrpcAdapter đều đọc registry này.

    Note: these packages must ALSO be in dependency.scan() so the DI container
    creates controller instances before the adapter serves them.
    Lưu ý: gói này cũng phải nằm trong dependency.scan() để DI tạo instance.

    Example:
        from xime.adapters.grpc.codefirst import configure_grpc_codefirst
        configure_grpc_codefirst(
            packages=["api.grpc"],
            output_dir="generated",
            lock_file="proto.lock.json",
        )
    """
    codefirst_registry.register(
        CodeFirstConfig(packages=packages, output_dir=output_dir, lock_file=lock_file)
    )
