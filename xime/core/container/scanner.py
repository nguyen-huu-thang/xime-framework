import importlib
import inspect
import pkgutil

from xime.core.exception.framework import MissingTypeHintException
from xime.core.metadata.type_utils import (
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


def _module_itself_missing(exc: ModuleNotFoundError, module_name: str) -> bool:
    """True when exc reports `module_name` (or a dotted parent) absent, rather
    than a dependency imported *inside* it.

    Lets scanners skip a genuinely-absent module while surfacing a real import
    error (e.g. a missing third-party dependency) instead of hiding it.
    Phân biệt "module vắng" với "dependency bên trong thiếu" để scanner bỏ qua cái
    đầu nhưng ném ra cái sau.
    """
    missing = (exc.name or "").split(".")
    parts = module_name.split(".")
    return parts[: len(missing)] == missing


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

        # Scan classes defined directly in the package root (__init__.py).
        # pkgutil.walk_packages only yields sub-modules, so the root is handled here.
        for _name, cls in inspect.getmembers(package, inspect.isclass):
            if cls.__module__ == package_name and self._is_eligible(cls):
                classes.append(cls)

        for _finder, module_name, _is_pkg in pkgutil.walk_packages(
            path=package_path,
            prefix=package_name + ".",
        ):
            if self._is_excluded_module(module_name):
                continue

            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError as exc:
                # Only skip when the walked module itself is absent (a race);
                # a missing *dependency* inside it is a real error -> surface it.
                # Chỉ bỏ qua khi chính module vắng; thiếu dependency bên trong là
                # lỗi thật -> ném ra.
                if _module_itself_missing(exc, module_name):
                    continue
                raise
            # Other ImportError (cannot import name, circular import, ...) is a
            # genuine bug in a scanned module -> do not hide it.
            # ImportError khác (cannot import name, circular...) là bug thật.

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

        try:
            hints = resolve_constructor_hints(cls)
        except NameError as exc:
            # A string annotation (forward reference) could not be resolved.
            # This is a developer mistake — fail fast with a clear message
            # rather than silently dropping the class from DI.
            raise MissingTypeHintException(cls.__name__, str(exc)) from exc

        # Any parameter without a type hint → silently skip this class.
        return all(param in hints for param in params)
