# Con mồ côi VÔ HÌNH với phép dò quen thuộc, và 401 lạnh máy đếm theo TIẾN TRÌNH

> Báo cáo từ phiên giữ **`Service ngang/kho`**, ngày 2026-08-23, sau khi di trú
> M0-M6 xong và chạy e2e thật lần đầu (Trust + application + identity + user +
> organization + kho, cụm 3 tiến trình, Windows).
>
> **Hai mục dưới đây tôi đo được chắc chắn. Mục 3 tôi CHƯA quy được trách nhiệm** -
> khai ra kèm bằng chứng thay vì im, và cũng thay vì gọi nó là lỗi framework khi
> chưa chứng minh được.

## 0. Tóm tắt

| # | Vấn đề | Mức | Tôi đo được tới đâu |
|---|---|---|---|
| 1 | **Con mồ côi vô hình**: tiến trình con giữ socket dùng chung nhưng KHÔNG khớp phép dò `app.main` mà chính tài liệu đang dạy | ⭐⭐ Cao - **làm hỏng phép đo mà không ai biết** | Chắc chắn. 11 tiến trình, 3 socket, phục vụ bằng **mã cũ** suốt 4 vòng gỡ lỗi |
| 2 | **401 lạnh máy đếm theo TIẾN TRÌNH**, không phải theo service | ⭐ Trung bình - đúng thiết kế, nhưng hệ quả chưa ai ghi | Chắc chắn. Cần **8 lần gọi liên tiếp** mới ấm cả cụm 3 tiến trình |
| 3 | Con bị `SIGTERM` (-15) rồi supervisor dựng lại, lặp lại nhiều lần | ? | **Chưa quy được**: có thể là watchdog, cũng có thể là công cụ chạy lệnh của tôi. Bằng chứng ở mục 3 |

---

## 1. ⭐⭐ Con mồ côi VÔ HÌNH với phép dò mà tài liệu đang dạy

### Chuyện đã xảy ra

Tôi sửa một lỗi trong `DocumentUseCase`, khởi động lại kho, chạy e2e - **vẫn lỗi y
hệt**. Sửa tiếp, khởi động lại, vẫn y hệt. Ba vòng như vậy.

Nguyên nhân: request của tôi **không đến tiến trình vừa khởi động**. Nó đến một tiến
trình con **mồ côi từ lần chạy trước**, đang chạy **mã cũ**, và vẫn giữ socket 8122.

### Vì sao phép dò quen thuộc không thấy nó

`crm/.claude/docs/09` (bẫy 6) và `kho/.claude/docs/07` đều dặn: *"giết con trước, rồi
kiểm `netstat` tới khi cổng sạch"*. Tôi làm đúng thế, bằng phép dò tự nhiên nhất:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*app.main*' }
```

**Nó trả về 1 tiến trình. Thực tế có 12.**

Vì tiến trình con **không mang `app.main` trong dòng lệnh**:

```text
cha (supervisor):  python -m app.main
con  (thật sự phục vụ):  python -c "from multiprocessing.spawn import spawn_main; ..."
```

### Và `netstat` nói dối theo một kiểu khác

Sau khi giết supervisor, `netstat` hiện socket 8122 **LISTENING dưới PID không còn tồn
tại**:

```text
TCP  0.0.0.0:8122  LISTENING  3084     <- Get-Process 3084 -> khong ton tai
TCP  0.0.0.0:8122  LISTENING  10188    <- cung vay
TCP  0.0.0.0:8122  LISTENING  13056    <- cung vay
```

Ba PID "ma" đó là ba supervisor đã chết. Socket vẫn sống vì **con của chúng còn sống
và thừa kế handle**. Nhưng `netstat` gán socket cho PID người tạo, nên nó chỉ vào ba
xác chết, và người đọc kết luận *"chỉ là bản ghi cũ, kệ nó"* - đúng thứ tôi đã kết
luận, sai.

⭐ Cái làm nó nguy hiểm không phải là con mồ côi tồn tại - **tài liệu đã cảnh báo rồi**.
Cái nguy là **cả hai phép dò mà người ta sẽ dùng đều trả lời sai theo hướng trấn an**:
lọc theo `app.main` ra "1 tiến trình, đúng như mong đợi", và `netstat` ra "PID đã chết
rồi". Hai câu trả lời yên tâm, và tổng của chúng là **bốn vòng gỡ lỗi vào hư không**.

### Phép dò ĐÚNG (đã dùng để dọn được thật)

```powershell
# Tìm theo QUAN HỆ CHA, không theo dòng lệnh
$chaChet = @(3084, 10188, 13056)   # PID supervisor lấy từ netstat, kể cả đã chết
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $chaChet -contains $_.ParentProcessId } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Kiểm bằng chủ sở hữu THẬT, không bằng netstat
Get-NetTCPConnection -LocalPort 8122 -State Listen | Select-Object OwningProcess
```

### Đề nghị (framework quyết, tôi không tự sửa)

1. ⭐ **Cho tiến trình con một dòng lệnh nhận ra được** - ví dụ thêm một tham số vô
   hại mang tên process id (`--xime-process=api-2`). Chỉ cần thế là mọi phép dò quen
   thuộc bắt được nó, và cả `Task Manager` cũng đọc được. Đây là đề nghị chính.
2. Nếu (1) không làm được: **ghi vào tài liệu bẫy 6 rằng phép dò theo dòng lệnh KHÔNG
   dùng được**, và đưa hai lệnh ở trên vào chỗ bẫy 6 đang nằm.
3. Cân nhắc: supervisor có nên đặt job object trên Windows để con chết theo cha không?
   Tôi không biết đủ về ràng buộc của framework để đề nghị chắc chắn.

---

## 2. ⭐ 401 lạnh máy đếm theo TIẾN TRÌNH, không phải theo service

### Quan sát

Sau mỗi lần khởi động cụm, request có token **đầu tiên** nhận `401 Unknown signing
key`. Đó là hệ quả **đúng thiết kế** của hợp đồng `JwtKeyProvider`: `keys()` không
bao giờ được gọi mạng, nên nó trả bộ khoá đang có (rỗng) rồi xếp lịch fetch nền.

Fail-closed, an toàn, không phàn nàn gì.

**Điều chưa ai ghi là hệ quả khi cụm có nhiều tiến trình:** mỗi tiến trình giữ bộ khoá
RIÊNG, nên *"đã ấm"* là thuộc tính của **từng tiến trình**. Một lời gọi thành công chỉ
chứng minh cho đúng tiến trình vừa trả lời.

Đo thật trên cụm 3 tiến trình: phải **8 lần gọi liên tiếp không-401** mới đủ tin là cả
cụm đã ấm. Một lần thành công rồi đi tiếp thì lời gọi thứ hai rơi vào tiến trình khác
và 401 - đúng thứ đã làm hỏng lượt e2e đầu tiên của tôi và đổ dây chuyền 16 phép đo.

### Vì sao đáng ghi dù không phải lỗi

Nó biến một tính chất *"an toàn, tự khỏi sau vài giây"* thành một **cái bẫy cho mọi
kịch bản đo và mọi lần triển khai**: người viết e2e sẽ hâm một lần rồi tin, và người
triển khai sẽ thấy 401 rải rác ngay sau khi deploy mà không giải thích được.

### Đề nghị

Không đề nghị đổi hành vi - hợp đồng `keys()` không gọi mạng là đúng. Chỉ đề nghị
**một dòng trong tài liệu đa tiến trình**: *bộ khoá verify ấm theo từng tiến trình,
nên phép đo phải đòi N lần liên tiếp chứ không phải một lần*.

Nếu framework muốn làm hơn: cân nhắc nạp khoá **một lần ở `post_construct`** (đọc, mọi
tiến trình đều làm được) thay vì để lần verify đầu tiên gánh. Nhưng đó là đổi hành vi,
và tôi không đủ ngữ cảnh để nói nó có phá gì không.

---

## 3. Con bị SIGTERM rồi dựng lại - CHƯA quy được trách nhiệm

### Bằng chứng

```text
16:50:56 | WARNING | xime.bootstrap | supervisor: api-3 exited with code -15 - restarting
16:50:57 | WARNING | xime.bootstrap | supervisor: main exited with code -15 - restarting
16:50:59 | INFO    | xime.bootstrap | supervisor: api-2 took the primary role
```

Xảy ra vài lần, mỗi lần khoảng 40 giây sau khi khởi động, trong lúc e2e đang chạy.

**Hệ quả đo được:** gRPC chỉ chạy ở ô `main` (không `shared`, vì Windows không có
`SO_REUSEPORT`), nên mỗi lần `main` được dựng lại là **cổng 8127 mất vài giây** trong
khi 8122 vẫn phục vụ bình thường. Client gRPC nhận `UNAVAILABLE: Connection refused`
đúng lúc đó, và nhìn từ ngoài thì trông y hệt "gRPC chưa bao giờ lên".

### ⚠ Vì sao tôi KHÔNG gọi đây là lỗi framework

`-15` là `SIGTERM` - **ai đó gửi**, không phải tiến trình tự chết. Hai ứng viên, và
tôi không loại được cái nào:

| Ứng viên | Ủng hộ | Phản đối |
|---|---|---|
| Watchdog của framework | Đúng lúc có tải; supervisor dựng lại ngay như thiết kế | Không thấy dòng log nào của watchdog nói lý do |
| **Công cụ chạy lệnh của tôi** | Tôi chạy nền bằng `&` trong một lệnh shell rồi lệnh đó kết thúc - nhiều công cụ gửi `SIGTERM` cho cả nhóm tiến trình lúc đó | Nếu là tín hiệu cả nhóm thì **supervisor cũng phải chết**, mà nó sống và dựng lại con |

Vế phản đối ở dòng cuối là lý do tôi nghiêng về **không phải lỗi framework**, nhưng
nghiêng không phải là chứng minh.

### Đề nghị

Chỉ một, và rẻ: **khi supervisor thấy con thoát, ghi thêm nó chết vì tín hiệu nào và
có phải watchdog của chính mình giết không.** Dòng log hiện tại (`exited with code
-15 - restarting`) đúng nhưng không phân biệt được *"tôi vừa giết nó vì nó treo"* với
*"ai đó bên ngoài giết nó"* - hai chuyện khác hẳn nhau về việc phải làm tiếp theo, mà
người đọc log không có cách nào tách ra.

Cùng họ với luật 03 ở tầng log: một dòng mang hai nghĩa thì người đọc phải đoán, và
sẽ đoán sai.

---

## 4. Tôi đo được tới đâu

| | |
|---|---|
| Môi trường | Windows 11, Python 3.14, framework cài editable từ `D:\code\xime\xime framework` |
| Cụm | 3 tiến trình (`main` primary + `api-2` + `api-3`), web 8122 `shared`, gRPC 8127 chỉ ở `main` |
| Service Base cùng chạy | Trust, application, identity, user, organization (đều Java) |
| Mục 1 | **Chắc chắn** - đếm được 11 tiến trình con mồ côi, 3 socket dưới PID đã chết, và xác nhận chúng phục vụ mã cũ bằng cách so hành vi trước/sau khi giết |
| Mục 2 | **Chắc chắn** - lặp lại được mọi lần khởi động; con số 8 lần liên tiếp là ngưỡng tôi phải dùng để e2e ổn định |
| Mục 3 | **Chưa quy được** - xem bảng hai ứng viên ở trên |
| Thứ tôi KHÔNG kiểm | Linux (không có máy). Cả ba mục đều có thể mang hình dạng khác hẳn ở đó, nhất là mục 1 (process group của Unix vốn giải quyết chuyện này) |
