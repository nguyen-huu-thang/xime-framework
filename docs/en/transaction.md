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
from xime.transaction import TransactionManager
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager

dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
})
```

Business code depends only on the `TransactionManager` interface — it knows nothing about SQLAlchemy.

---

## Nested Transactions

The current design uses a single session per transaction scope. Nested `async with self.transaction():` blocks are possible but share the same underlying session — true nested transactions (savepoints) are not yet supported.

---

## Future API

Planned extensions that do not change the underlying philosophy:

```python
# Read-only transaction (no commit, may use replica)
async with self.transaction.read_only():
    users = await self.repository.find_all()

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
