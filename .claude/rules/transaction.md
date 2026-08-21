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

- **Không có magic** - không có Proxy, Bytecode Manipulation hay Runtime Method Interception
- **Dễ đọc** - `async with self.transaction():` thể hiện rõ transaction boundary
- **Dễ debug** - Stack Trace phản ánh đúng luồng thực tế, không có proxy trung gian
- **Tương thích async** - hoạt động tự nhiên với FastAPI, grpc.aio, asyncio

---

## Khối chỉ đọc: `ReadOnlyManager` (0.6.3)

Usecase chỉ đọc dùng một manager **riêng, cùng cấp** với `TransactionManager`.
Hiện thực: `core/transaction/readonly.py` (Protocol) +
`starters/sqlalchemy/readonly.py` (impl).

```python
class ProductService:
    def __init__(self, read_only: ReadOnlyManager, products: ProductRepository):
        self.read_only = read_only
        self.products = products

    async def get_detail(self, product_id: str):
        async with self.read_only():
            return await self.products.find_or_fail(product_id)
```

Bốn điều cần nhớ khi sửa hoặc dùng:

1. **Không bao giờ commit.** Thoát khối là hủy, dù thành công hay lỗi. Đây là
   toàn bộ lý do nó tồn tại như một thứ tách biệt.
2. **Lồng nhau thì mượn session.** Vào khối mà `_current_session` đã có giá trị
   -> dùng lại, thoát ra không làm gì. Nhờ vậy service chỉ đọc ghép được vào
   usecase có ghi mà không mở connection thứ hai và không đóng nhầm session của
   transaction bao ngoài. **Đừng đổi thành ném lỗi** - ca lồng nhau là ca thật.
3. **`expunge_all()` phải chạy TRƯỚC `rollback()`.** Rollback làm expire mọi
   object trong session, entity trả ra ngoài sẽ ném `DetachedInstanceError` khi
   đọc thuộc tính. Gỡ trước thì giá trị đã nạp còn nguyên. Có test canh đúng dòng
   này: `tests_temp/sqlalchemy/test_read_only.py::TestEntitiesSurviveTheBlock`
   (đã kiểm chứng bằng cách xóa dòng đó - hai test chuyển đỏ).
4. **Không gọi `begin()` tường minh**, để SQLAlchemy autobegin. Khối không đọc gì
   thì không lấy connection nào khỏi pool.

### Vì sao tách manager riêng thay vì `transaction.read_only()`

Là binding riêng nên về sau trỏ được sang **read replica** / isolation khác /
decorator cache chỉ bằng một dòng `bind`, không sửa code nghiệp vụ. Nếu là method
thì nó dính chặt vào engine của đường ghi.

### Ranh giới đã chốt: KHÔNG chặn việc sửa entity đọc ngoài transaction

Framework không phát hiện, không cảnh báo. Thay đổi bị bỏ đi im lặng. Đây là
**lựa chọn có chủ đích** (chốt 2026-07-29): chặn được thì phải hook SQLAlchemy
event và trả phí runtime cho mọi lời đọc, trái nguyên tắc minimal magic. Bù lại
bằng quy tắc tài liệu:

> Entity đọc trong `read_only()` chỉ để **trả về hoặc render**. Muốn sửa thì mở
> `transaction()` và **load lại** trong đó.

Đừng đề xuất lại cơ chế chặn tự động trừ khi có bằng chứng thực tế là quy tắc này
bị vi phạm nhiều.

---

## Định hướng tương lai

```python
async with self.transaction(isolation="SERIALIZABLE"):
    ...
```

Không thay đổi triết lý thiết kế ban đầu.
