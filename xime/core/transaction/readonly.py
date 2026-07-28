from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ReadOnlyContext(Protocol):
    """
    Async context manager wrapping a read-only unit of work.

    Entering opens a database session; exiting always discards it - a read-only
    block never commits, so an accidental entity change cannot reach the
    database. Implementations live in starters (e.g. starters/sqlalchemy/).
    Vào block thì mở session; ra khỏi block thì luôn hủy - khối chỉ-đọc không bao
    giờ commit, nên lỡ sửa entity cũng không xuống được database.

    Usage - obtained by calling ReadOnlyManager:
        async with self.read_only():
            return await self.repository.find_all()
    """

    async def __aenter__(self) -> "ReadOnlyContext": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None: ...


class ReadOnlyManager(Protocol):
    """
    Factory that creates a ReadOnlyContext for each read-only unit of work.

    A sibling of TransactionManager, not a method on it. Injected separately so
    a service that only reads never has to depend on the write path:
    Là anh em cùng cấp với TransactionManager chứ không phải method của nó. Inject
    riêng để service chỉ đọc không phải phụ thuộc vào đường ghi:

        class ProductService:
            def __init__(
                self,
                read_only: ReadOnlyManager,
                products: ProductRepository,
            ) -> None:
                self.read_only = read_only
                self.products = products

            async def get_detail(self, product_id: str) -> ProductDto:
                async with self.read_only():
                    product = await self.products.find_or_fail(product_id)
                return ProductDto.of(product)

    Why a separate Protocol instead of TransactionManager.read_only():
      Being its own binding means it can be pointed at a different backend later
      - a read replica, a different isolation level, a caching decorator -
      without touching the write path. As a method it would stay welded to
      whatever engine the write manager uses.
      Là binding riêng nên về sau trỏ được sang backend khác (read replica, mức
      isolation khác, decorator cache) mà không đụng đường ghi; nếu là method thì
      nó dính chặt vào engine của manager ghi.

    Register in config/dependency.py alongside TransactionManager:
        dependency.bind({
            TransactionManager: SqlAlchemyTransactionManager,
            ReadOnlyManager: SqlAlchemyReadOnlyManager,
        })

    Nesting: opening a read-only block inside an existing transaction (or inside
    another read-only block) reuses the session already in flight and does
    nothing on exit, so a read-only service composes into a writing use case.
    Lồng nhau: mở khối chỉ-đọc bên trong transaction (hoặc bên trong khối chỉ-đọc
    khác) sẽ dùng lại session đang chạy và không làm gì lúc thoát, nên service
    chỉ đọc ghép được vào usecase có ghi.
    """

    def __call__(self) -> ReadOnlyContext: ...
