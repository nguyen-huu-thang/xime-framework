# Quản lý Transaction

[English](../en/transaction.md) | **Tiếng Việt**

---

## Triết lý

XIME không dùng `@transactional` hay AOP proxy. Transaction được biểu diễn tường minh qua Python async context manager.

> **Quy tắc cốt lõi:** "Dependency nên được ẩn bởi framework, nhưng Transaction nên được thể hiện rõ trong code nghiệp vụ."

Thiết kế này tránh behavior ẩn, stack trace chính xác và hoạt động tự nhiên với async/await.

---

## Cách dùng cơ bản

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

**Luồng thành công:** `BEGIN → save() → save_profile() → COMMIT`

**Luồng lỗi:** `BEGIN → save() → Exception → ROLLBACK`

Nếu có exception nào được raise bên trong khối `async with`, transaction sẽ được rollback tự động.

---

## TransactionManager Interface

`TransactionManager` là interface của Core:

```python
class TransactionManager:
    def __call__(self) -> TransactionContext:
        ...
```

Nó có thể gọi được — `self.transaction()` trả về `TransactionContext` (async context manager).

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

## Implementation SQLAlchemy

SQLAlchemy starter cung cấp `SqlAlchemyTransactionManager`:

```python
# config/dependency.py
from xime.transaction import TransactionManager
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager

dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
})
```

Business code chỉ phụ thuộc vào interface `TransactionManager` — nó không biết gì về SQLAlchemy.

---

## Nested Transaction

Thiết kế hiện tại dùng một session cho mỗi transaction scope. Các khối `async with self.transaction():` lồng nhau có thể dùng nhưng share cùng underlying session — nested transaction thực sự (savepoint) chưa được hỗ trợ.

---

## API tương lai

Các mở rộng được lên kế hoạch không thay đổi triết lý thiết kế:

```python
# Read-only transaction (không commit, có thể dùng replica)
async with self.transaction.read_only():
    users = await self.repository.find_all()

# Custom isolation level
async with self.transaction(isolation="SERIALIZABLE"):
    balance = await self.account_repo.get_balance(account_id)
    await self.account_repo.deduct(account_id, amount)
```

---

## Tại sao không dùng `@transactional`?

`@transactional` của Spring hoạt động qua AOP bytecode proxy — cơ chế này không tồn tại trong Python. Các giải pháp Python tương đương thường dùng metaclass hoặc decorator bọc method trong proxy object, gây ra:

- Boundary transaction bị ẩn khỏi người đọc code
- Stack trace phức tạp (xuất hiện proxy frame)
- Bug tinh tế với async code
- Testing khó hơn (phải test qua proxy)

Cách tiếp cận `async with self.transaction():` làm boundary rõ ràng, stack trace sạch và test đơn giản.
