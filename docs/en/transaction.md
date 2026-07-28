# Transaction Management

**English** | [Tiếng Việt](../vn/transaction.md)

[← Routing](routing.md) · **5/9 — Transaction** · [Starters →](starters.md)

---

## Philosophy

XIME does not use `@transactional` or AOP proxies. Transactions are explicit Python async context managers.

> **Core rule:** "Dependencies should be hidden by the framework, but transactions should be visible in business code."

This design avoids hidden behavior, makes stack traces accurate, and works naturally with async/await.

---

## Basic Usage

```python
class UserService:
    def __init__(
        self,
        transaction: TransactionManager,
        repository: UserRepository,
    ) -> None:
        self.transaction = transaction
        self.repository = repository

    async def create_user(self, name: str, email: str) -> User:
        async with self.transaction():
            user = User(name=name, email=email)
            await self.repository.save(user)
            await self.repository.save_profile(user.id)
            return user
```

**Success flow:** `BEGIN → save() → save_profile() → COMMIT`

**Error flow:** `BEGIN → save() → Exception → ROLLBACK`

If any exception is raised inside the `async with` block, the transaction is rolled back automatically.

---

## TransactionManager Interface

`TransactionManager` is a Core interface:

```python
class TransactionManager:
    def __call__(self) -> TransactionContext:
        ...
```

It is callable — `self.transaction()` returns a `TransactionContext` (the async context manager).

---

## TransactionContext

```python
class TransactionContext:
    async def __aenter__(self) -> "TransactionContext":
        await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            await self.session.rollback()
        else:
            await self.session.commit()
```

---

## SQLAlchemy Implementation

The SQLAlchemy starter provides `SqlAlchemyTransactionManager`:

```python
# config/dependency.py
from xime.core.transaction import TransactionManager
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager

dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
})
```

Business code depends only on the `TransactionManager` interface — it knows nothing about SQLAlchemy.

---

## Read-only Blocks: `read_only()` (0.6.3)

Use cases that only read use `ReadOnlyManager` — a **separate, sibling** manager
to `TransactionManager`, not a method on it:

```python
from xime.core.transaction import ReadOnlyManager

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
```

Bind it next to the transaction manager:

```python
# config/dependency.py
from xime.core.transaction import ReadOnlyManager, TransactionManager
from xime.starters.sqlalchemy import (
    SqlAlchemyReadOnlyManager,
    SqlAlchemyTransactionManager,
)

dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
    ReadOnlyManager: SqlAlchemyReadOnlyManager,
})
```

### How it differs from `transaction()`

| Situation | `transaction()` | `read_only()` |
| --- | --- | --- |
| Normal exit | COMMIT | always discarded, **never** commits |
| Exception | ROLLBACK | always discarded (as above) |
| Nested in a block already open | opens a new session | **borrows** the session in flight, does nothing on exit |
| Block reads nothing | still issues `BEGIN` | checks out no connection at all |

Because it never commits, an accidental entity change inside a read-only block
**cannot reach the database**. It is also **not reported** — see the warning below.

Nesting is deliberate: a read-only service composes into a writing use case
without opening a second connection, and without closing the enclosing
transaction's session.

### Why a separate manager, not `transaction.read_only()`

Being its own binding means it can be pointed at a different backend later — a
**read replica**, a different isolation level, or a caching decorator — just by
binding `ReadOnlyManager` to another implementation, with **no change to business
code**. As a method it would stay welded to whatever engine the write path uses.

### Warning: do not modify what you read outside a transaction

The framework does **not** prevent changes to entities read in a read-only block.
Such changes are dropped silently — no error, no log.

> **Rule:** entities read in `read_only()` are for **returning or rendering only**.
> To modify one, open `transaction()` and **load it again** in there.

This is a deliberate choice: catching that case would require hooking SQLAlchemy
events and paying a runtime cost on every read, against Xime's minimal-magic
principle.

### Entities stay usable after the block

Before discarding the session, a read-only block detaches every entity
(`expunge_all()`) and only then rolls back. Rolling back first would *expire*
every object and the next attribute read would raise `DetachedInstanceError`.
Detaching first keeps **already-loaded** attributes readable after the block:

```python
async with self.read_only():
    product = await self.products.find_or_fail(product_id)

return product.name        # OK — the loaded value is intact
return product.category    # FAILS unless eager-loaded (use selectinload)
```

Unloaded relationships still fail, exactly as in plain async SQLAlchemy — keep
using `selectinload` explicitly as you already do.

---

## Nested Transactions

The current design uses a single session per transaction scope. Nested `async with self.transaction():` blocks are possible but share the same underlying session — true nested transactions (savepoints) are not yet supported.

---

## Future API

Planned extensions that do not change the underlying philosophy:

```python
# Custom isolation level
async with self.transaction(isolation="SERIALIZABLE"):
    balance = await self.account_repo.get_balance(account_id)
    await self.account_repo.deduct(account_id, amount)
```

---

## Why Not `@transactional`?

Spring's `@transactional` works via AOP bytecode proxies — a mechanism that does not exist in Python. Python equivalents typically use metaclasses or decorators that wrap methods in proxy objects, which:

- Hide the transaction boundary from the reader
- Complicate stack traces (proxy frames appear)
- Can cause subtle bugs with async code
- Make testing harder (you must test through the proxy)

The `async with self.transaction():` approach makes the boundary obvious, the stack trace clean, and the test straightforward.

---

[← Routing](routing.md) · **5/9 — Transaction** · [Starters →](starters.md)
