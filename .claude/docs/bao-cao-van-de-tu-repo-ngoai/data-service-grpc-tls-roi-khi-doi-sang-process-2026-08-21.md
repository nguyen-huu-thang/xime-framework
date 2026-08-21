# gRPC tụt xuống PLAINTEXT khi chuyển từ khoá phẳng sang khối `process:`

> Báo từ **`Base Platform/data`** (data-service), 2026-08-21, trên bản Linux.
> Framework `0.8.0` cài editable, sau đợt vá kiểm toán 0.8 (commit `1821106`).
> Đây là file đầu tiên trong thư mục này.

## 1. Ở đâu

| | |
|---|---|
| `xime/adapters/grpc/_adapter.py:166-172` | ô cấu hình không có `tls` -> **không lấy gì cả** |
| `xime/adapters/web/_adapter.py:265-268` | ô cấu hình không có `ssl` -> **kế thừa `server.ssl`** |
| `xime/core/bootstrap/_processes.py:556` | đường khoá phẳng: `"grpc": ("grpc", ("port", "tls"))` |

```python
# grpc/_adapter.py - ô thiếu `tls` thì GrpcServerConfig nhận mặc định, tức TẮT
config = GrpcServerConfig.model_validate({
    "port": slot.spec.port,
    **_shared_grpc_settings(runtime),
    **({"tls": slot.spec.options["tls"]} if "tls" in slot.spec.options else {}),
})

# web/_adapter.py - ô thiếu `ssl` thì QUAY VỀ server.ssl
raw = slot.spec.options.get("ssl")
if raw is None:
    return WebServerConfig.from_runtime(runtime).ssl
return ServerTlsConfig.model_validate(raw)
```

## 2. Đo được

Cấu hình trước, dùng khoá phẳng, gRPC **có mTLS**:

```yaml
server: { host: "0.0.0.0", port: 8086 }
grpc:
  port: 9095
  tls: { enabled: true, mutual: true }
```

Làm đúng lời tài liệu `docs/vn/multi-process.md` mục *"Một hình dạng cấu hình, hai
cách viết"* - đổi sang `process:`, không đụng khối `grpc:`:

```yaml
process:
  web:  { default: { host: "0.0.0.0", port: 8086 } }
  grpc: { default: { host: "0.0.0.0", port: 9095 } }
grpc:
  tls: { enabled: true, mutual: true }      # <- vẫn còn nguyên ở đây
```

Khởi động thật, log:

```text
WARNING | xime.adapters.grpc._adapter | gRPC server 'default' on port 9095 is
serving PLAINTEXT: traffic is unencrypted and any client may call it.
```

Cùng một `application.yml`, cùng một `grpc.tls`, chỉ đổi cách khai địa chỉ, và
**mTLS biến mất**. Trước khi đổi: không có dòng WARNING nào. Đây là phép đối
chứng hai vế, không phải suy luận.

## 3. Hậu quả với repo gọi

Với data-service thì đây là **mất một chốt chặn bảo mật, không phải mất một tính
năng**. `grpc.internal.allowed_callers` lọc theo **CN của client cert**; không có
mTLS thì không có client cert, nên lớp chặn đó không còn đối tượng để xét. Cửa
`PurgeObject` (xoá vĩnh viễn cả blob) nằm sau đúng lớp đó.

Ba tính chất khiến nó đắt hơn một lỗi cấu hình thường:

| | |
|---|---|
| **Đi đúng đường tài liệu chỉ** | Tài liệu nói *"đổi `process:` thành `processes:`... KHÔNG sửa lại gì bên trong"*, và ở chiều phẳng -> `process:` thì cũng không có dòng nào bảo phải mang `tls` theo |
| **Hỏng theo chiều AN TOÀN -> KÉM AN TOÀN** | Không có gì đỏ. Service lên, cổng mở, client cũ **vẫn gọi được** vì gRPC plaintext nhận cả client không cert |
| **Dấu hiệu duy nhất là một dòng WARNING** | Lẫn giữa vài chục dòng khởi động, và không ai đọc log khởi động của một service đang chạy tốt |

⭐ Tài liệu của chính framework đã lập luận đúng chuyện này - nhưng chỉ cho web:

> *"Ô không khai `ssl` thì web kế thừa `server.ssl`, và đó là một **tính chất bảo
> mật** chứ không phải tiện lợi: một server phụ âm thầm chạy HTTP trong khi server
> chính đã HTTPS là lỗ hổng không ai để ý, vì nó vẫn trả lời 200."*

Lập luận đó đúng **từng chữ** với gRPC, mà gRPC lại không có hành vi đó.

## 4. Đề xuất

**Ưu tiên 1 - cho gRPC kế thừa `grpc.tls` y như web kế thừa `server.ssl`.** Một
dòng, và nó xoá hẳn loại lỗi này thay vì cảnh báo về nó:

```python
**({"tls": slot.spec.options["tls"]}
   if "tls" in slot.spec.options
   else {"tls": raw} if (raw := runtime.get("grpc.tls")) else {}),
```

Muốn một endpoint cố ý chạy plaintext thì khai rỗng tường minh - đúng khuôn
`ssl: {}` mà tài liệu web đã dạy.

**Ưu tiên 2 - nếu cố ý KHÔNG kế thừa** thì sự im lặng mới là chỗ phải sửa: khi
`grpc.tls.enabled: true` có mặt trong cấu hình mà ô của `process:` không mang
`tls`, đó gần như chắc chắn là một cuộc di trú làm rơi mất chứ không phải một ý
muốn. Trường hợp đó nên **nổ lúc khởi động**, không phải WARNING - cùng lập luận
mà `configure_cors` đã dùng ("cấu hình sai kiểu thì nổ lúc khởi động").

⚠ Kèm một chỗ nữa nếu chọn ưu tiên 2: `docs/{vn,en}/multi-process.md` mục *"TLS: ô
trước, `server.ssl` sau"* hiện chỉ nói về web, nên người đọc suy sang gRPC là suy
sai. Bảng *"Khoá của một ô"* ghi `ssl` / `tls` chung một dòng cho `web / grpc`,
càng làm người đọc tin hai bên hành xử giống nhau.

## 5. Phạm vi tôi đo được tới đâu

- Đo trên **một repo** (`Base Platform/data`), **một adapter gRPC**, id `default`.
- **Chưa đo** `grpc.servers.<id>.tls` cho server thứ hai, và **chưa đo** nhánh
  `processes:` nhiều tiến trình - nhưng cả hai đi qua cùng đoạn code ở dòng 166
  nên nhiều khả năng giống nhau.
- **Chưa đo** chiều ngược lại của web: không có `server.ssl` trong cấu hình này
  nên tôi chỉ đọc được hành vi kế thừa của web **trong code**, không đối chứng
  bằng lần chạy thật.
- Repo khác trong workspace: **chưa đo cái nào**. Nhưng ai còn dùng khoá phẳng thì
  chưa dính; nó chỉ nổ vào đúng lúc người ta di trú sang `process:` - tức là
  **đúng lúc đọc tài liệu 0.8 và làm theo**.
