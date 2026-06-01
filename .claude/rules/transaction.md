# Thiết kế Transaction Management

## Nguyên tắc

Xime **không** dùng `@transactional` hay AOP proxy ẩn. Transaction được biểu diễn tường minh qua Python Async Context Manager.

> **Quy tắc cốt lõi:** "Dependency nên được ẩn bởi framework, nhưng Transaction nên được thể hiện rõ trong code nghiệp vụ."

---

## Cách dùng

```python
class UserService:

    def __init__(
        self,
        transaction: TransactionManager,
        repository: UserRepository
    ):
        self.transaction = transaction
        self.repository = repository

    async def create_user(self):
        async with self.transaction():
            await self.repository.save_user()
            await self.repository.save_profile()
```

Luồng thành công: `BEGIN → save_user() → save_profile() → COMMIT`

Luồng lỗi: `BEGIN → save_user() → Exception → ROLLBACK`

---

## TransactionManager

`TransactionManager` là abstract interface của framework:

```python
class TransactionManager:
    def __call__(self):
        return TransactionContext(...)
```

`SqlAlchemyTransactionManager` (trong SQLAlchemy Starter) là implementation cụ thể:

```python
class SqlAlchemyTransactionManager(TransactionManager):
    ...
```

---

## Triển khai Context Manager

```python
class TransactionContext:

    async def __aenter__(self):
        await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc:
            await self.session.rollback()
        else:
            await self.session.commit()
```

---

## Ưu điểm

- **Không có magic** — không có Proxy, Bytecode Manipulation hay Runtime Method Interception
- **Dễ đọc** — `async with self.transaction():` thể hiện rõ transaction boundary
- **Dễ debug** — Stack Trace phản ánh đúng luồng thực tế, không có proxy trung gian
- **Tương thích async** — hoạt động tự nhiên với FastAPI, grpc.aio, asyncio

---

## Định hướng tương lai

```python
async with self.transaction.read_only():
    ...

async with self.transaction(isolation="SERIALIZABLE"):
    ...
```

Không thay đổi triết lý thiết kế ban đầu.
