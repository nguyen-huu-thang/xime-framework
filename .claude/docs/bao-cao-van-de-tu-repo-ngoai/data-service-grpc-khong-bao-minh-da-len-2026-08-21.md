# Adapter gRPC không bao giờ nói nó đã lên, chỉ nói ở đâu nó KHÔNG chạy

> Báo từ **`Base Platform/data`** (data-service), 2026-08-21, bản Linux,
> framework `0.8.0` editable sau đợt vá kiểm toán 0.8.
>
> Mức: **thấp**, nhưng nó **cộng hưởng** với báo cáo
> [`data-service-grpc-tls-roi-khi-doi-sang-process`](data-service-grpc-tls-roi-khi-doi-sang-process-2026-08-21.md)
> theo cách khiến cả hai cùng khó thấy hơn. Đọc mục 3.

## 1. Ở đâu

| File | Số lệnh log |
|---|---|
| `xime/adapters/grpc/_adapter.py` | **2**, cả hai là `_log.warning` (dòng 315, 322 - đều về TLS) |
| `xime/adapters/web/_adapter.py` | có `_log.info` ở dòng 312 báo đã phục vụ |

## 2. Đo được

Một cụm 3 tiến trình, `main` khai gRPC còn `api-2` / `api-3` thì không. Toàn bộ
dấu vết gRPC trong log khởi động:

```text
WARNING | xime.bootstrap | process api-3 does not declare grpc.default - that adapter will not run here
WARNING | xime.bootstrap | process api-2 does not declare grpc.default - that adapter will not run here
```

Đếm dòng `serving on`: **3** - cả ba đều của web.

Nói cách khác: log cho biết **hai chỗ gRPC KHÔNG chạy**, và không cho biết chỗ
nào nó **có** chạy. Muốn biết nó lên thật hay không thì phải đi mở cổng bằng tay.

## 3. Vì sao đáng sửa dù mức thấp

**Tín hiệu bị đảo chiều.** Người vận hành đọc log khởi động để trả lời *"cái gì
đã lên"*. Ở đây họ chỉ nhận được câu trả lời cho *"cái gì không lên"*, và hai câu
đó không thay thế nhau: một cụm mà gRPC **hỏng** ở `main` sinh ra log **giống hệt**
một cụm mà gRPC **khoẻ** ở `main`.

**Cộng hưởng với lỗ TLS.** Báo cáo kia cho thấy gRPC có thể lên ở chế độ
**PLAINTEXT** sau một lần di trú cấu hình, và dấu hiệu duy nhất là một dòng
WARNING. Ghép hai chuyện lại thì mọi thứ người vận hành biết về gRPC đều đến từ
cảnh báo, không có lấy một mốc dương nào để đối chiếu:

| Tình huống | Log nói gì |
|---|---|
| gRPC lên, có mTLS | **không gì cả** |
| gRPC lên, plaintext | một dòng WARNING |
| gRPC không chạy ở tiến trình này | một dòng WARNING |

Ô đầu tiên trống là chỗ hỏng: **trạng thái tốt không có dấu vết**, nên không có
gì để so khi nghi ngờ. Đúng khuôn *"một chốt chặn không chạy trông y hệt một chốt
chặn không có việc để làm"* mà chính đợt kiểm toán 0.8 đã đặt tên.

## 4. Đề xuất

Một dòng `_log.info` sau khi server bind xong, cùng khuôn web đã có, và **nói
luôn chế độ bảo mật** để nó vừa là mốc dương vừa là chỗ đối chiếu cho lỗ TLS:

```text
INFO | grpc default: process main serving on 0.0.0.0:9095 (mTLS)
INFO | grpc default: process main serving on 0.0.0.0:9095 (PLAINTEXT)
```

Ghi chế độ vào **cùng một dòng** với địa chỉ có một cái lợi mà một dòng WARNING
riêng không có: người đọc thấy nó **mỗi lần**, ở đúng chỗ họ đang tìm, thay vì
phải nhận ra sự vắng mặt của một cảnh báo.

## 5. Phạm vi tôi đo được tới đâu

- Đo trên **một** ứng dụng, một adapter gRPC id `default`, ba tiến trình, mức log
  mặc định của framework.
- **Chưa thử** hạ mức log xuống DEBUG - nhưng `grep` toàn file `_adapter.py` chỉ
  ra đúng hai lệnh log và cả hai là `warning`, nên nhiều khả năng không có dòng
  nào bị mức log che.
- Không đo adapter `socket`, không biết nó có cùng hình dạng không.
