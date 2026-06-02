from __future__ import annotations

import importlib
import inspect
import pkgutil

from ._decorators import ROUTE_ATTR


class ControllerScanner:
    """Walks Python packages and finds controller classes.

    A class is a controller if at least one of its own methods carries the
    ROUTE_ATTR attribute (set by @get, @post, @put, @patch, @delete).

    The scanner never creates instances — it returns types only.
    Instances are fetched from the DI container by RouteBuilder.
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
        for _name, cls in inspect.getmembers(package, inspect.isclass):
            if cls.__module__ == package_name and self._is_controller(cls):
                classes.append(cls)

        # Walk sub-modules recursively.
        for _finder, module_name, _is_pkg in pkgutil.walk_packages(
            path=package_path,
            prefix=package_name + ".",
        ):
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue

            for _name, cls in inspect.getmembers(module, inspect.isclass):
                # Skip classes that were imported from elsewhere.
                if cls.__module__ != module_name:
                    continue
                if self._is_controller(cls):
                    classes.append(cls)

        return classes

    def _is_controller(self, cls: type) -> bool:
        """Return True if cls has at least one method decorated with a route decorator."""
        for _name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
            if hasattr(member, ROUTE_ATTR):
                return True
        return False
