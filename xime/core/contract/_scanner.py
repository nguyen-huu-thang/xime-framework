from __future__ import annotations

import importlib
import inspect
import pkgutil

from xime.core.contract._decorators import ENDPOINT_ATTR


class ControllerScanner:
    """Walks Python packages and finds contract controller classes.

    A class is a controller if at least one of its own methods carries the
    ENDPOINT_ATTR attribute (set by @command / @stream).
    Một class là controller nếu có ít nhất một method mang ENDPOINT_ATTR.

    The scanner never creates instances — it returns types only.
    Instances are fetched from the DI container by the transport builder.
    Scanner không tạo instance — chỉ trả type. Instance do builder lấy từ DI.

    Mirrors the web ControllerScanner so the two read identically; the only
    difference is which marker attribute identifies a controller.
    """

    def find_controllers(self, *packages: str) -> list[type]:
        """Return all controller classes found in the given packages."""
        seen: set[type] = set()
        result: list[type] = []

        for package_name in packages:
            for cls in self._scan_package(package_name):
                if cls not in seen:
                    seen.add(cls)
                    result.append(cls)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_package(self, package_name: str) -> list[type]:
        try:
            package = importlib.import_module(package_name)
        except ImportError as exc:
            raise ImportError(
                f"Cannot scan controller package '{package_name}': {exc}"
            ) from exc

        return self._walk_modules(package, package_name)

    def _walk_modules(self, package: object, package_name: str) -> list[type]:
        classes: list[type] = []
        package_path = getattr(package, "__path__", [])

        # Collect controllers defined directly in the package __init__.py.
        # Gom controller khai báo ngay trong __init__.py của package.
        for _name, cls in inspect.getmembers(package, inspect.isclass):
            if cls.__module__ == package_name and self._is_controller(cls):
                classes.append(cls)

        # Walk sub-modules recursively.
        # Duyệt đệ quy các sub-module.
        for _finder, module_name, _is_pkg in pkgutil.walk_packages(
            path=package_path,
            prefix=package_name + ".",
        ):
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue

            for _name, cls in inspect.getmembers(module, inspect.isclass):
                # Skip classes imported from elsewhere — only own definitions.
                # Bỏ qua class import từ nơi khác — chỉ lấy định nghĩa của chính module.
                if cls.__module__ != module_name:
                    continue
                if self._is_controller(cls):
                    classes.append(cls)

        return classes

    def _is_controller(self, cls: type) -> bool:
        """Return True if cls has at least one method marked with ENDPOINT_ATTR."""
        for _name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
            if hasattr(member, ENDPOINT_ATTR):
                return True
        return False
