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
        Only instances that were successfully reached are eligible for pre_destroy().

    stop() — called on application shutdown (step 1 of shutdown):
        Iterates only the instances that completed start() in reverse order.
        Does NOT stop on the first error — every pre_destroy() is attempted.
        If any failed, raises ExceptionGroup with all collected exceptions.
    """

    def __init__(self, instances: list[object]) -> None:
        self._instances = list(instances)
        # Filled incrementally during start(). If start() fails midway, only
        # the instances reached before the failure are torn down — avoiding
        # pre_destroy() on instances whose post_construct() never ran.
        self._started: list[object] = []

    async def start(self) -> None:
        """
        Call post_construct() on every PostConstruct instance in order.
        Raises immediately on the first failure (fail-fast startup).
        Each instance is added to _started before the next one begins, so
        stop() only tears down what was actually initialised.
        """
        for instance in self._instances:
            if isinstance(instance, PostConstruct):
                await instance.post_construct()
            self._started.append(instance)

    async def stop(self) -> None:
        """
        Call pre_destroy() on every started PreDestroy instance in reverse order.
        Collects all errors and raises them together as ExceptionGroup.
        """
        errors: list[Exception] = []

        for instance in reversed(self._started):
            if isinstance(instance, PreDestroy):
                try:
                    await instance.pre_destroy()
                except Exception as exc:
                    errors.append(exc)

        if errors:
            raise ExceptionGroup("Errors during lifecycle shutdown", errors)
