from __future__ import annotations

from core.lifecycle.hooks import PostConstruct, PreDestroy


class LifecycleManager:
    """
    Orchestrates PostConstruct and PreDestroy hooks across all registered singletons.

    Instances must be provided in topological order (dependencies before dependents).
    Bootstrap builds this list by walking the dependency graph after all singletons
    are created.

    start() — called once after all singletons are created (step 7 of startup):
        Iterates instances in order and calls post_construct() on each eligible one.
        Fails immediately if any post_construct() raises — startup is aborted.

    stop() — called on application shutdown (step 1 of shutdown):
        Iterates instances in reverse order and calls pre_destroy() on each eligible one.
        Does NOT stop on the first error — every pre_destroy() is attempted.
        If any failed, raises ExceptionGroup with all collected exceptions.
    """

    def __init__(self, instances: list[object]) -> None:
        self._instances = list(instances)

    async def start(self) -> None:
        """
        Call post_construct() on every PostConstruct instance in order.
        Raises immediately on the first failure (fail-fast startup).
        """
        for instance in self._instances:
            if isinstance(instance, PostConstruct):
                await instance.post_construct()

    async def stop(self) -> None:
        """
        Call pre_destroy() on every PreDestroy instance in reverse order.
        Collects all errors and raises them together as ExceptionGroup.
        """
        errors: list[Exception] = []

        for instance in reversed(self._instances):
            if isinstance(instance, PreDestroy):
                try:
                    await instance.pre_destroy()
                except Exception as exc:
                    errors.append(exc)

        if errors:
            raise ExceptionGroup("Errors during lifecycle shutdown", errors)
