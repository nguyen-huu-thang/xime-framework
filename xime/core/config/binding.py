from __future__ import annotations


class BindingConfig:
    """
    Collects DI scan packages and interface bindings declared in the
    application's config/dependency.py.

    Bootstrap reads this object after the user's config module runs and
    forwards its state to XimeContainer.

    Typical usage in app/config/dependency.py:
        from xime.core.config import BindingConfig

        dependency = BindingConfig()
        dependency.scan("app.service", "app.repository")
        dependency.bind({UserRepository: JpaUserRepository})
    """

    def __init__(self) -> None:
        self._packages: list[str] = []
        self._bindings: dict[type, type] = {}

    def scan(self, *package_names: str) -> None:
        """Register one or more package paths to scan for DI candidates."""
        self._packages.extend(package_names)

    def bind(self, bindings: dict[type, type]) -> None:
        """
        Declare explicit Protocol → Implementation mappings.
        Later calls overwrite earlier bindings for the same key.
        """
        self._bindings.update(bindings)

    @property
    def packages(self) -> tuple[str, ...]:
        """Immutable snapshot of registered scan packages."""
        return tuple(self._packages)

    @property
    def bindings(self) -> dict[type, type]:
        """Shallow copy of the current Protocol → Implementation map."""
        return dict(self._bindings)
