from __future__ import annotations

import importlib
import inspect
import pkgutil

from xime.core.container.scanner import _module_itself_missing

from .._decorators import MQTT_ATTR


class MqttControllerScanner:
    """Walks packages and finds MQTT controller classes.

    A class is an MQTT controller if at least one of its methods carries the
    MQTT_ATTR attribute (set by @subscribe / @rpc). Mirrors the web
    ControllerScanner; returns types only - instances come from the DI container.
    Tìm controller có method gắn @subscribe/@rpc; chỉ trả type, instance lấy từ DI.
    """

    def find_controllers(self, *packages: str) -> list[type]:
        seen: set[type] = set()
        result: list[type] = []
        for package_name in packages:
            for cls in self._scan_package(package_name):
                if cls not in seen:
                    seen.add(cls)
                    result.append(cls)
        return result

    def _scan_package(self, package_name: str) -> list[type]:
        try:
            package = importlib.import_module(package_name)
        except ImportError as exc:
            raise ImportError(
                f"Cannot scan MQTT controller package '{package_name}': {exc}"
            ) from exc
        return self._walk_modules(package, package_name)

    def _walk_modules(self, package: object, package_name: str) -> list[type]:
        classes: list[type] = []
        package_path = getattr(package, "__path__", [])

        for _name, cls in inspect.getmembers(package, inspect.isclass):
            if cls.__module__ == package_name and self._is_controller(cls):
                classes.append(cls)

        for _finder, module_name, _is_pkg in pkgutil.walk_packages(
            path=package_path, prefix=package_name + "."
        ):
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError as exc:
                if _module_itself_missing(exc, module_name):
                    continue
                raise  # a missing dependency inside the module is a real error
            for _name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ != module_name:
                    continue
                if self._is_controller(cls):
                    classes.append(cls)
        return classes

    def _is_controller(self, cls: type) -> bool:
        for _name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
            if hasattr(member, MQTT_ATTR):
                return True
        return False
