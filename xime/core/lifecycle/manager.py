from __future__ import annotations

import logging

from xime.core.lifecycle.hooks import PostConstruct, PreDestroy, RunOnce

_log = logging.getLogger("xime.lifecycle")


class LifecycleManager:
    """
    Orchestrates PostConstruct and PreDestroy hooks across all registered singletons.

    Instances must be provided in topological order (dependencies before dependents).
    Bootstrap builds this list by walking the dependency graph after all singletons
    are created.

    start() - called once after all singletons are created (step 7 of startup):
        Iterates instances in order and calls post_construct() on each eligible one.
        Fails immediately if any post_construct() raises - startup is aborted.
        Only instances that were successfully reached are eligible for pre_destroy().

    stop() - called on application shutdown (step 1 of shutdown):
        Iterates only the instances that completed start() in reverse order.
        Does NOT stop on the first error - every pre_destroy() is attempted.
        If any failed, raises ExceptionGroup with all collected exceptions.
    """

    def __init__(self, instances: list[object]) -> None:
        self._instances = list(instances)
        # None  → start() never called; stop() falls back to all instances.
        # list  → filled incrementally during start(); if start() fails midway
        #         only the instances reached before the failure are torn down.
        self._started: list[object] | None = None

    async def start(self) -> None:
        """
        Call post_construct() on every PostConstruct instance in order.
        Raises immediately on the first failure (fail-fast startup).
        Each instance is added to _started before the next one begins, so
        stop() only tears down what was actually initialised.
        """
        self._started = []
        for instance in self._instances:
            if isinstance(instance, PostConstruct):
                await instance.post_construct()
            self._started.append(instance)

    async def run_once(self) -> None:
        """Chạy `run_once()` của mọi instance khai nó, theo thứ tự topo.

        **Chỉ primary gọi.** Framework quyết chỗ gọi; class không có cờ nào để
        tự kiểm, đúng khuôn adapter hạng đơn nhất - *một object không được gọi
        thì không chạy*, và không có gì để quên.

        In ra danh sách tìm thấy vì đây là thứ **không nhìn thấy được từ chỗ
        khác**: `run_once` là một tên method, không phải một dòng khai trong
        `config/`. Người vận hành cần một cách biết cụm đang chạy những gì một
        lần, mà không phải đi đọc code.

        ⚠ Ném lỗi thì **ném luôn**, đúng như `start()`: đây vẫn là giai đoạn
        *chưa phục vụ được*.
        """
        eligible = [i for i in self._instances if isinstance(i, RunOnce)]
        if not eligible:
            return
        _log.info(
            "run_once: %d task(s) for the whole cluster: %s",
            len(eligible),
            ", ".join(type(i).__name__ for i in eligible),
        )
        for instance in eligible:
            await instance.run_once()

    async def stop(self) -> None:
        """
        Call pre_destroy() on every eligible PreDestroy instance in reverse order.
        Collects all errors and raises them together as ExceptionGroup.

        If start() was never called (_started is None), all instances are eligible.
        If start() ran (possibly partially), only the instances that completed
        post_construct() are eligible.
        """
        instances_to_stop = (
            self._started if self._started is not None else self._instances
        )
        errors: list[Exception] = []

        for instance in reversed(instances_to_stop):
            if isinstance(instance, PreDestroy):
                try:
                    await instance.pre_destroy()
                except Exception as exc:
                    errors.append(exc)

        if errors:
            raise ExceptionGroup("Errors during lifecycle shutdown", errors)
