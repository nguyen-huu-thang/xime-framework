# Quản lý Transaction

[English](../en/transaction.md) | **Tiếng Việt**

[← Routing](routing.md) · **5/9 - Transaction** · [Starters →](starters.md)

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

Nó có thể gọi được - `self.transaction()` trả về `TransactionContext` (async context manager).

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
from xime.core.transaction import TransactionManager
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager

dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
})
```

Business code chỉ phụ thuộc vào interface `TransactionManager` - nó không biết gì về SQLAlchemy.

---

## Khối chỉ đọc: `read_only()` (0.6.3)

Usecase chỉ đọc dùng `ReadOnlyManager` - một manager **riêng, cùng cấp** với
`TransactionManager`, không phải method của nó:

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

Bind cạnh transaction manager:

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

### Nó khác `transaction()` ở chỗ nào

| Tình huống | `transaction()` | `read_only()` |
| --- | --- | --- |
| Kết thúc bình thường | COMMIT | luôn hủy, **không bao giờ** commit |
| Có exception | ROLLBACK | luôn hủy (như trên) |
| Lồng trong khối đang chạy | mở session mới | **dùng lại** session đang có, thoát ra không làm gì |
| Khối không đọc gì | vẫn `BEGIN` | không lấy connection nào khỏi pool |

Vì không bao giờ commit, lỡ sửa entity trong khối chỉ đọc thì thay đổi **không
xuống được database**. Nhưng nó cũng **không báo lỗi** - xem cảnh báo bên dưới.

Việc lồng nhau là có chủ đích: một service chỉ đọc ghép được vào usecase có ghi
mà không mở thêm connection thứ hai, và không tự đóng session của transaction bao
ngoài.

### Vì sao là manager riêng, không phải `transaction.read_only()`

Là binding riêng nên về sau trỏ được sang backend khác - **read replica**, mức
isolation khác, hay một decorator cache - chỉ bằng cách bind
`ReadOnlyManager` sang implementation khác, **không sửa dòng code nghiệp vụ nào**.
Nếu nó là method của `TransactionManager` thì nó dính chặt vào engine của đường ghi.

### Cảnh báo: đọc ngoài transaction thì đừng sửa

Framework **không chặn** việc sửa entity đọc được từ khối chỉ đọc. Thay đổi sẽ bị
bỏ đi im lặng - không lỗi, không log.

> **Quy tắc:** entity đọc trong `read_only()` chỉ để **trả về hoặc render**.
> Muốn sửa thì mở `transaction()` và **load lại** trong đó.

Đây là lựa chọn có chủ đích: chặn được ca này thì phải hook vào SQLAlchemy event
và trả phí runtime cho mọi lời đọc - trái nguyên tắc minimal magic của Xime.

### Entity vẫn dùng được sau khi ra khỏi khối

Trước khi hủy session, khối chỉ đọc gỡ mọi entity ra khỏi session
(`expunge_all()`) rồi mới rollback. Nếu rollback trước, SQLAlchemy sẽ *expire* mọi
object và lần đọc thuộc tính kế tiếp ném `DetachedInstanceError`. Nhờ gỡ trước,
các thuộc tính **đã nạp** vẫn đọc bình thường sau khi ra khỏi khối:

```python
async with self.read_only():
    product = await self.products.find_or_fail(product_id)

return product.name        # OK - giá trị đã nạp còn nguyên
return product.category    # LỖI nếu chưa eager-load (dùng selectinload)
```

Quan hệ chưa nạp thì vẫn lỗi, giống hệt async SQLAlchemy thông thường - cứ
`selectinload` tường minh như vẫn làm.

---

## Nested Transaction

Thiết kế hiện tại dùng một session cho mỗi transaction scope. Các khối `async with self.transaction():` lồng nhau có thể dùng nhưng share cùng underlying session - nested transaction thực sự (savepoint) chưa được hỗ trợ.

---

## API tương lai

Các mở rộng được lên kế hoạch không thay đổi triết lý thiết kế:

```python
# Custom isolation level
async with self.transaction(isolation="SERIALIZABLE"):
    balance = await self.account_repo.get_balance(account_id)
    await self.account_repo.deduct(account_id, amount)
```

---

## Tại sao không dùng `@transactional`?

`@transactional` của Spring hoạt động qua AOP bytecode proxy - cơ chế này không tồn tại trong Python. Các giải pháp Python tương đương thường dùng metaclass hoặc decorator bọc method trong proxy object, gây ra:

- Boundary transaction bị ẩn khỏi người đọc code
- Stack trace phức tạp (xuất hiện proxy frame)
- Bug tinh tế với async code
- Testing khó hơn (phải test qua proxy)

Cách tiếp cận `async with self.transaction():` làm boundary rõ ràng, stack trace sạch và test đơn giản.

---

[← Routing](routing.md) · **5/9 - Transaction** · [Starters →](starters.md)
