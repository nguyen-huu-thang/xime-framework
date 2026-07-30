from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PostConstruct(Protocol):
    """
    Implement this Protocol to run initialization logic after all singletons
    have been created and dependencies injected.

    Called by LifecycleManager.start() in topological order —
    a dependency's post_construct() always runs before its dependents.

    Typical uses: warm up caches, open connection pools, validate config,
    register event listeners.

    CONTRACT for partial failure (decided 2026-07-30): pre_destroy() is only
    called for instances whose post_construct() COMPLETED - running it on a
    half-initialised object would raise a second error that buries the first.
    So a post_construct that opens a resource and then fails at a later step
    must close that resource itself before re-raising; it is the only code
    that knows how far it got. For several resources, use
    contextlib.AsyncExitStack with pop_all() on success.
    HỢP ĐỒNG khi hỏng giữa chừng: pre_destroy() chỉ gọi cho instance đã chạy
    XONG post_construct(). Mở tài nguyên rồi hỏng ở bước sau thì chính
    post_construct phải tự đóng trước khi ném tiếp - chỉ nó biết đã mở tới đâu.
    Nhiều tài nguyên thì dùng AsyncExitStack + pop_all() lúc thành công.

    Example:
        class UserService:
            def __init__(self, repository: UserRepository): ...

            async def post_construct(self) -> None:
                await self.repository.ping()
    """

    async def post_construct(self) -> None: ...


@runtime_checkable
class PreDestroy(Protocol):
    """
    Implement this Protocol to run cleanup logic before the application shuts down.

    Called by LifecycleManager.stop() in reverse topological order —
    a dependent's pre_destroy() always runs before its dependencies.

    LifecycleManager.stop() attempts every pre_destroy() even when some fail,
    then raises ExceptionGroup with all collected errors.

    Typical uses: flush queues, close connections, release locks, save state.

    Example:
        class CacheService:
            async def pre_destroy(self) -> None:
                await self.client.close()
    """

    async def pre_destroy(self) -> None: ...
