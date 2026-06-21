from __future__ import annotations


class _ControllerRegistry:
    """Module-level singleton that stores packages containing controllers.

    Read by WebAdapter during startup to discover and register routes.
    """

    def __init__(self) -> None:
        self._packages: list[str] = []

    def add(self, *packages: str) -> None:
        self._packages.extend(packages)

    def get_packages(self) -> list[str]:
        return list(self._packages)

    def reset(self) -> None:
        """Clear all registrations - test cleanup only."""
        self._packages.clear()


controller_registry = _ControllerRegistry()


def configure_controllers(*packages: str) -> None:
    """Register packages that contain controller classes.

    Call this once in your config layer (e.g. config/routing.py).
    WebAdapter reads this registry after DI startup and registers all routes.

    Follows the same explicit-call pattern as configure_openapi() and configure_jwt():
    no magic auto-scan, developer opts in by calling this function.

    Note: controller packages must also be passed to dependency.scan() so that
    the DI container creates instances before route registration runs.

    Example:
        from xime.adapters.web.routing import configure_controllers

        configure_controllers("api.rest", "api.internal")
    """
    controller_registry.add(*packages)
