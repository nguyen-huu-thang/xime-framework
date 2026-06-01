import importlib
import inspect
import pkgutil

from core.metadata.type_utils import (
    get_init_parameters,
    is_abstract,
    is_protocol,
    resolve_constructor_hints,
)

# Package name segments that are never registered into DI.
# The scanner skips any module whose dotted path contains one of these segments.
_DEFAULT_EXCLUDED_SEGMENTS = frozenset(
    ["domain", "dto", "entity", "vo", "constant", "exception"]
)


class PackageScanner:
    """
    Scans one or more Python packages and returns every class that is
    eligible for DI registration.

    Eligibility rules:
      - Not a Protocol
      - Not an abstract class (ABC with unimplemented methods)
      - Every __init__ parameter has a type hint
        (parameters without hints → class is silently skipped)
    """

    def __init__(self, excluded_segments: frozenset[str] | None = None):
        self._excluded = excluded_segments if excluded_segments is not None else _DEFAULT_EXCLUDED_SEGMENTS

    def scan(self, *package_names: str) -> list[type]:
        """Scan all given packages and return eligible classes (no duplicates)."""
        seen: set[type] = set()
        result: list[type] = []

        for package_name in package_names:
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
                f"Cannot scan package '{package_name}': {exc}"
            ) from exc

        # If __init__.py declares __all__, honour it exclusively.
        if hasattr(package, "__all__"):
            return self._collect_from_all(package)

        return self._walk_modules(package, package_name)

    def _collect_from_all(self, package) -> list[type]:
        """Collect only the classes explicitly listed in __all__."""
        classes = []
        for name in package.__all__:
            obj = getattr(package, name, None)
            if obj is not None and inspect.isclass(obj) and self._is_eligible(obj):
                classes.append(obj)
        return classes

    def _walk_modules(self, package, package_name: str) -> list[type]:
        """Recursively walk all sub-modules and collect eligible classes."""
        classes = []
        package_path = getattr(package, "__path__", [])

        for _finder, module_name, _is_pkg in pkgutil.walk_packages(
            path=package_path,
            prefix=package_name + ".",
        ):
            if self._is_excluded_module(module_name):
                continue

            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue

            for _name, cls in inspect.getmembers(module, inspect.isclass):
                # Skip classes that were merely imported into this module.
                if cls.__module__ != module_name:
                    continue
                if self._is_eligible(cls):
                    classes.append(cls)

        return classes

    def _is_excluded_module(self, module_name: str) -> bool:
        """Return True if any dotted segment of the module name is excluded."""
        segments = set(module_name.split("."))
        return bool(segments & self._excluded)

    def _is_eligible(self, cls: type) -> bool:
        """Return True if cls should be registered in the DI container."""
        if is_protocol(cls):
            return False
        if is_abstract(cls):
            return False

        params = get_init_parameters(cls)
        if not params:
            # No dependencies — singleton with no constructor args, valid.
            return True

        hints = resolve_constructor_hints(cls)
        # Any parameter without a type hint → silently skip this class.
        return all(param in hints for param in params)
