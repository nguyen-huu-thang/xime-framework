# Đề nghị giao tiếp: phiên framework làm việc với nhóm thế nào

> Ghi ngày **2026-08-04** bởi **phiên leader** (workspace gốc `D:\code\xime`), theo yêu cầu chủ dự án.
>
> Viết cho **phiên sẽ được bật ở repo này**. Bạn chưa từng ở trong nhóm, nên đọc file này trước khi nhận việc.

## 1. Vì sao repo này cần một kênh, dù trước nay không có

Xime Framework là **thứ duy nhất mọi service Python phụ thuộc vào**, và nó được cài **editable** trên máy này. Nghĩa là:

> **Mỗi thay đổi trong repo này có hiệu lực ngay với ~30 codebase, không cần ai cài lại gì.**

Đó là quyền lực lớn hơn bất kỳ repo nào khác trong workspace, và nó đi kèm hai rủi ro mà nhóm đã gặp thật:

| Rủi ro | Ca đã xảy ra |
|---|---|
| Đổi framework làm test repo khác đỏ mà họ không biết vì sao | 2026-08-03, bản `0.7.1` đổi hành vi `save_upload` / `configure_cors` / `stream_object` |
| Phiên khác **đoán** về framework rồi kết luận sai | 2026-08-04, một phiên grep **một file tài liệu** rồi kết luận *"framework không có scheduler"* - sai, và con số sai suýt đi tới 30 repo |

Ca thứ hai là lý do trực tiếp của tài liệu này: **không ai trong nhóm biết chắc framework có gì, vì không ai giữ nó.**

## 2. Kênh liên lạc

Nhóm dùng thư mục **ngoài repo**: `D:\temp\xime\nhom-chat\`.

| Chỗ | Là gì |
|---|---|
| `CHAT-CHUNG.md` | **loa** - nói với cả nhóm cùng lúc |
| `leader-<tên>/` | cặp riêng giữa leader và từng phiên, mỗi bên sở hữu **một file** |
| `README.md` | **sổ việc đang mở**, do leader giữ |

**Luật xuyên suốt: chỉ ghi vào file mang tên mình, không bao giờ sửa file của bên kia.** Tin mới nhất **trên cùng**. Nhãn: `CẦN TRẢ LỜI` · `ĐỂ BIẾT` · `ĐÃ XONG`.

**Đề nghị:** khi bạn được bật, xin leader mở cặp `leader-framework/`. Đừng tự tạo - roster do leader giữ.

## 3. Ba việc bạn nên làm ngay khi được bật, theo thứ tự

| # | Việc | Vì sao |
|---|---|---|
| 1 | Đọc [`../da-phu-dinh/vuong-mac-scheduler-trong-test.md`](../da-phu-dinh/vuong-mac-scheduler-trong-test.md) | Việc cụ thể duy nhất đang chờ bạn. ⚠ Đọc **mục 5** trước khi ước lượng - phạm vi hẹp hơn tiêu đề |
| 2 | **Loa lên `CHAT-CHUNG.md` rằng framework nay CÓ người giữ** | Cả nhóm hiện thiếu chỗ hỏi. Chỉ cần một dòng |
| 3 | Chốt với chủ dự án **phiên bản hiện tại là gì** | Xem mục 4 - đây là chỗ nhóm đang mù |

## 4. ⚠ Cái bẫy số phiên bản, nhóm đã vấp

Ghi trong nhật ký điều phối 2026-08-03:

> **`pip show xime`, `importlib.metadata`, và `xime.__version__` đều trả `0.6.3`** trong khi code đang chạy mới hơn nhiều.

Cách kiểm đúng là **hỏi code**, không hỏi số phiên bản:

```python
from xime.core.contract import stream   # có = đang chạy >= 0.7.1
```

Chủ dự án đính chính 2026-08-03: **`0.7.0` là bản đã xong, `0.7.1` đang làm dở**. **Chủ dự án là người quyết phiên bản**, không phải phiên nào.

Mọi app Python trên máy đang chạy **code của một bản chưa hoàn tất**. Ai gặp test đỏ bất ngờ thì **đừng vá quanh nó** - báo bạn.

## 5. Luật của nhóm áp cho bạn

| Luật | Nghĩa với repo này |
|---|---|
| [`rules/01`](../../../../.claude/rules/01-song-song-hoa-va-shard.md) song song hoá & shard | Framework **không có bảng**, nên nghĩa 2 không áp. Nhưng nghĩa 1 thì có - và **framework là nơi quyết định các repo khác vi phạm dễ đến đâu** |
| [`rules/03`](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) một giá trị một nghĩa | **Áp mạnh nhất ở đây.** API của bạn là hợp đồng với 30 codebase. Bốn mặc định không an toàn của framework từng **im lặng** (gRPC plaintext, OPC UA None, MQTT không TLS, WebSocket không qua xác thực) - đó là giá trị mang hai nghĩa ở mức mặc định |
| ⛔ **Không tự sửa `.claude/rules/` của workspace** | Luật cắt ngang chỉ leader sửa, sau khi chủ dự án chốt. Thấy luật thiếu thì **đề xuất qua leader** |

Ngược lại, `.claude/rules/` **của repo này** là của bạn, sửa tự do.

## 6. Khuôn lỗi nhóm đúc kết - bốn cái mới nhất đều về *cách kiểm chứng*

Đọc [`04-chin-khuon-loi-lap-lai.md`](../../../../.claude/dieu-phoi/04-chin-khuon-loi-lap-lai.md) khi bạn định báo "xong". Bảng rút gọn:

| Thứ tưởng là bằng chứng | Thật ra không chứng minh gì |
|---|---|
| "đã quét sạch" | ...tới **commit nào**, trong **phạm vi nào** |
| test xanh | ...khi thao tác chạy **lần thứ hai** |
| phép kiểm im lặng | ...nếu nó **chưa bao giờ biết kêu** |
| service đang chạy, log không lỗi | ...rằng đường liên-service **còn sống** |

Và câu đắt nhất trong ngày, sinh ra từ đúng ca hiểu nhầm về framework:

> **Đối chứng chứng minh phép dò kêu đúng với những ca BẠN LIỆT KÊ. Nó không bao giờ chứng minh danh sách của bạn ĐỦ** - tín hiệu bạn chưa nghĩ ra thì cũng không có trong đối chứng, vì đối chứng được viết từ **cùng một cái đầu đang thiếu nó**.

## 7. Ba thứ đừng làm

1. **Đừng build và đẩy PyPI từ repo này.** Việc đó làm ở repo phát hành `D:\code\xime framework\upload` (ngoài workspace). Lý do: hatchling đóng gói **mọi thứ không bị `.gitignore` chặn**, nên build ở đây sẽ nhét cả `.claude/` lẫn `tests_temp/` vào sdist. Lệnh và hướng dẫn 8 bước: `python pypi_token.py --guide`.
2. **Đừng đổi hành vi mặc định mà không loa trước.** 30 codebase cài editable - thay đổi của bạn có hiệu lực trước khi ai kịp đọc changelog.
3. **Đừng tự bật/tắt service của repo khác.** Cần một service đang tắt thì **nhắn phiên giữ nó**, hoặc nhắn leader nếu nó vô chủ (hiện `Trust` và `placement` vô chủ).

## 8. Trạng thái nhóm lúc ghi tài liệu này

**Mọi service đã tắt** (đo lúc 11:35). Các phiên `user`, `identity`, `placement` đã tắt trong ngày; `user-locator` và `admin` có thể còn.

Nhật ký ngày đầy đủ: [`06-nhat-ky-2026-08-04.md`](../../../../.claude/dieu-phoi/06-nhat-ky-2026-08-04.md).
