# Nghiệm thu logging và tiếp nhận bản vá Linux

> **Trạng thái:** ĐÃ TIẾP NHẬN VÀ KIỂM LẠI WINDOWS ngày 2026-10-19; đủ căn cứ chốt ứng viên phát hành trong phạm vi đã kiểm, còn điều kiện thử VPS trước PyPI.
> **Thuộc bản:** working tree sau `c76b6cd`, G1–G4 và bản vá Linux; metadata vẫn 0.8.3, không phải bản 0.8.3 đã phát hành.
> **Thay cái gì:** trạng thái chờ Linux trong `BAN-GIAO-LINUX-LOGGING.md` và `KIEM-THU-GRPC-HANDSHAKE.md`.
> **Bị thay bởi:** chưa có; kết quả phát hành cuối phải gắn với version và artifact dựng lại sau khi chủ dự án chốt.

## 1. Nguồn đã tiếp nhận

Gói `D:\temp\xime framework.zip`, SHA-256:
`e575bad16e5628c1d828455a300245881d65fca78950d86f3e175d866f753ed8`.
Đã giải nén vào `D:\temp\xime-linux-receive-20261018-cugzquqk\xime framework`.

- Đã kiểm đủ 793 file theo `final-source-manifest.json`: hash và kích thước khớp.
- Mốc incoming của cả 13 file sửa khớp source Windows trước tiếp nhận; không có
  xung đột hoặc thay đổi Windows mới hơn cần ghi đè. Chín file thêm chưa tồn tại.
- Tiếp nhận đúng delta **22 file = 13 sửa + 9 thêm, không xóa**; runtime có sáu
  file thuộc ba bản vá. Không chép toàn cây, Git, cấu hình riêng hay môi trường.
- `pyproject.toml`, version và sàn dependency giữ nguyên. Đã giữ bản source trước
  tiếp nhận và staged diff trong vùng kiểm thử Windows.

Nguồn kết quả Linux: `ket-qua-linux-logging/20261018T142347Z/BAO-CAO.md` và
`BAN-GIAO-CHO-WINDOWS.md` trong cây đã giải nén. Kế hoạch bổ sung đã được chủ dự án
duyệt tại Linux nằm trong `ket-qua-kiem-thu-linux/KE-HOACH-PHAT-HANH-2026-10-18.md`.

## 2. Ba bản vá Linux đã nhập

| Nhóm | Lỗi và hành vi sau sửa |
|---|---|
| Shutdown/lifecycle | Application sở hữu signal khi chạy worker, tránh uvicorn phát lại tín hiệu trước cleanup; adapter, PreDestroy và logging được dọn. Khôi phục handler cũ, không giành signal của embedding host. Supervisor vẫn có deadline/kill fallback. |
| Native gRPC 1.72.1 | Nhận tiền tố trace cũ `handshake_manager` cùng định dạng mới; IP/port chỉ lấy từ metadata của cùng record, không từ reason; trace thành công không tăng unparsed. |
| S3 StreamingBody | Giữ wrapper khi đọc get/stream thay vì dùng response thô từ context manager; sửa lỗi read(size), giữ đọc chunk và cleanup khi lỗi, cancel hoặc đóng stream. |

Linux có đối chứng đỏ/xanh cho cả ba nhóm, không nâng dependency hoặc sửa
consumer để làm test xanh. S3 được phát hiện và đo lại bằng MinIO thật, không
chỉ fake client. Runtime Linux đã kiểm là Python 3.13.5, không phải Python 3.12.

## 3. Kết quả Linux đã đối chiếu

| Môi trường cuối Linux/Python 3.13.5 | Passed | Skipped | Failed |
|---|---:|---:|---:|
| Resolver, asyncio | 2975 | 12 | 0 |
| Resolver, uvloop | 2975 | 12 | 0 |
| grpcio/tools 1.72.1, asyncio | 2975 | 12 | 0 |
| grpcio/tools 1.72.1, uvloop | 2975 | 12 | 0 |

Đã đọc bốn JUnit `full-final-v3-*`: mỗi lượt 2987 testcase, không có failure/error.
Không cộng bốn lượt thành testcase độc lập. Skip gồm sáu ca Windows-only và sáu
ca MQTT/S3 đóng endpoint có chủ ý; MQTT/S3 đã có lượt riêng với dịch vụ thật.

Soak một process trong 30 phút, 20 vòng Application: 380 HTTP và 720 RPC mTLS
hợp lệ; **3600/3600** lỗi TLS khớp capture, tuple kết nối thực và JSONL trên đĩa.
Không có counter mất log/parse/read/flush lỗi. FD và thread ổn định ở 15/15 sau
mỗi vòng. RSS tăng khoảng 5,46 MiB trong harness giữ toàn bộ expected/event;
không dùng kết quả đó để khẳng định không thể có leak khi chạy nhiều ngày.

Linux cũng kiểm runtime web/WS/Unix, symlink TLS, 13 nhóm extra minimum,
MinIO/MQTT/Redis/PostgreSQL riêng và wheel sạch. Candidate Linux có 262 file
runtime và khớp byte với source ngay sau tiếp nhận. Wheel SHA-256:
`3317b580f347cf39cef5a52043698b6f28ddde0885dff22d6ed24bc84070239f`.
Đây là artifact test tên 0.8.3, **không upload** và không dùng thay bản phát hành cũ.

## 4. Lỗi Windows tìm thêm và cách xử lý

Kiểm trên Windows/Python 3.12.10 với grpcio/tools **đúng 1.72.1** phát hiện
trace legacy in pointer bằng hex cố định không có `0x`. Parser Linux chỉ nhận
pointer có `0x`, dẫn tới RPC vẫn chạy nhưng **0/20 event**, unparsed=92.

Đã bổ sung nhận pointer hex 8/16 ký tự của Windows; giữ nguyên kiểm source,
metadata tail, listener và endpoint. Không nâng sàn grpcio, không lấy IP từ raw
reason hoặc record khác. Mở rộng test cho pointer Windows, chia byte, thành
công không tăng parse loss, pointer sai và reason giả. Đối chứng trước sửa:
**8 failed / 8 passed**. Bổ sung hai ca Windows gửi CTRL_BREAK thật vào process
group riêng, kiểm PreDestroy đúng một lần và drain file, có/không có WebAdapter.

Một assertion của test cụm cũng chỉ nhận pointer `0x`: đã sửa nhận cả định dạng
Windows, giữ mọi kiểm event/PID/promotion/respawn. Đây là sửa phép đo console,
không bỏ qua sự kiện hoặc hạ tiêu chí đúng IP.

Probe sàn sau sửa: **20/20 event trong capture và trên đĩa, bốn RPC hợp lệ**;
multiset server_id/remote/local IP+port khớp expected, PID đúng, không bịa request
ID; mọi counter ngoài received/emitted bằng 0. Đã kiểm JSONL độc lập, không lấy
exit 0 của probe làm bằng chứng đủ.

Các lượt full Windows trước đó chưa hoàn thành đã được giữ log và không được
tính pass. Lượt đang chạy khi phát hiện lỗi pointer đã dừng để tránh nghiệm thu
lẫn runtime trước/sau sửa. Một lượt mục tiêu sau vá runtime còn đỏ vì assertion
console của test cụm chưa nhận pointer Windows; full suite sau sửa assertion đã đạt.

| Windows/source cuối | Passed | Skipped | Deselected | Failed | Thời gian pytest |
|---|---:|---:|---:|---:|---:|
| Python 3.14.8, resolver, grpcio 1.84.0 | 2965 | 33 | 1 | 0 | 323,40 s |
| Python 3.12.10, core exact floors + grpcio/tools 1.72.1 | 2965 | 33 | 1 | 0 | 354,10 s |

Mỗi lượt có 2999 ca trước deselect, 2998 testcase trong JUnit. Source tăng thêm
12 ca so với mốc Linux: hai ca signal Windows và mười biến thể parser. 33 skip
là POSIX/Linux-only cùng MQTT/S3 không mở endpoint thật trên Windows. Một ca
`tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive` được
deselect theo hạn chế Windows đã biết; đã chạy trong full Linux. Không gọi
skip/deselect là đã thực thi trên Windows, không cộng hai lượt thành ca độc lập.

Core exact floors đã cài và chạy: FastAPI 0.133.0, Starlette 1.3.1,
AnyIO 4.14.2, Pydantic 2.7.0, PyYAML 6.0.1; gRPC/tool 1.72.1 và protobuf 6.33.5.
Các extra khác dùng resolver tương thích, không gọi toàn bộ môi trường là
exact floor của mọi extra. Python 3.12 được tách vào thư mục tạm, không thay
Python hệ thống. Mypy: 0 lỗi/261 file, Ruff và pip check đạt; note của mypy về
hàm chưa có type không phải error. Tài liệu: 416 tên import/53 file và 444 Python
block đạt; ba class register thực đạt, hai tên minh họa được bỏ qua có lý do.

Wheel Windows dựng lại từ sdist sau bản vá pointer, metadata vẫn 0.8.3 để test:

- Wheel SHA-256: `f0296b8661444e190066d87c468e57d2d92eff3f76d5598d4591ac23f77943bc`.
- Sdist SHA-256: `c85e62728b7686e8619b39f48fa87a824c599522932567daea57bfe38b2dbc3f`.
- 262 file runtime khớp byte source trong wheel và sdist; không có `.claude`,
  `tests_temp` hoặc Git; twine check đạt.
- Venv trắng chỉ cài wheel `[web,grpc,jwt,s3]`, không pytest/mypy/dev, chạy ngoài
  checkout bằng Python `-I`; xác nhận import site-packages, pip check, JWT RSA,
  CLI init/check config đạt. Native collector ghi 20/20 event trên đĩa và bốn RPC
  mTLS hợp lệ, không counter lỗi/mất log. Không dùng venv editable để chứng minh wheel.

Các số Linux ở mục 3 thuộc source trước bổ sung pointer Windows. Định dạng Linux
có `0x` được giữ trong guard test và full Windows; chưa chạy lại Linux sau bổ sung
này. Không sửa báo cáo/manifest Linux gốc để gọi đó là bằng chứng của source khác.

## 5. Kiểm phát hành và giới hạn

Audit lại bộ sàn và môi trường resolver: không có ID ngoài ngoại lệ
**PYSEC-2026-282 / CVE-2026-31072 của APScheduler 4.0.0a6**. Raw pip-audit resolver
exit 1, hai dòng cùng một ID; không gọi đây là zero advisory. Chấp nhận có điều
kiện cho MemoryDataStore/LocalEventBroker mặc định; kho ngoài hoặc serializer
JSON/CBOR cần đánh giá riêng. Nguồn: [OSV](https://osv.dev/vulnerability/PYSEC-2026-282).
Đã kiểm metadata PyPI: 4.0.0a6 vẫn là bản v4 mới nhất tại lúc kiểm.

Các nợ consumer được Linux xác định riêng ở thời điểm tiếp nhận:

- Dental thiếu khai Pillow: tám ca nén ảnh lỗi; cài chẩn đoán riêng thì qua.
- Dental YAML mẫu thiếu public path của route yêu cầu tư vấn; cần repo ứng dụng
  đối chiếu thiết kế và cấu hình thực trước khi sửa.
- Dental/Shop Hoa có guard báo khai cryptography trùng framework. Đây không
  phải resolver conflict; không bỏ assertion để gọi tất cả consumer xanh.

**Đã xử lý tại mã nguồn Dental/Shop Hoa ngày 2026-10-19:** bỏ khai cryptography
trùng, dùng dependency từ extra JWT của framework mới; khai Pillow runtime cho
Dental và đồng bộ sàn Pillow hai app lên 12.3.0. Đã kiểm OSV của 12.3.0 tại thời
điểm sửa không có advisory trả về, và chạy test với đúng phiên bản này. YAML mẫu
Dental bổ sung `/api/v1/cong-khai/yeu-cau-tu-van/*`; YAML local đã có đúng tiền tố,
không mở rộng toàn bộ nhánh công khai. Không đổi handler hoặc cơ chế hãm nhịp.

Full backend Windows/Python 3.14.8 sau sửa: **Dental 1578 passed**, **Shop Hoa
1083 passed/2 skipped**, không failure/error. Kiểm các dependency runtime đã khai
và pip check đạt. Bằng chứng tại `%TEMP%/xime-app-debts-20261019-l4d7557g/`.
Thay đổi mới nằm ở hai `backend/pyproject.toml` và YAML mẫu Dental; chưa đồng bộ
các thay đổi ứng dụng này sang build/VPS và chưa commit chúng.

Linux đã chạy Data 695, Notification 462, Kho 238/5 skip, Sổ thu chi 246/8 skip;
PostgreSQL riêng Kho bốn ca và Sổ thu chi bảy ca đều đạt. Kết quả lỗi Dental/Shop
Hoa trong báo cáo Linux gốc được giữ làm lịch sử; lượt Windows sửa consumer phía
trên là bằng chứng mới, không trộn vào tổng framework.

Chưa chứng minh: Linux/Python 3.12 với source cuối; Windows forced termination
thực hiện cleanup; VPS/systemd/ACME/DNS thật, AWS S3 cloud và nghiệp vụ live.
Windows terminate cưỡng bức không tương đương CTRL_BREAK. Không dùng static
mypy Linux, wheel sạch hoặc soak 30 phút thay cho VPS chạy nhiều ngày.

Trong phạm vi đo ở trên, không còn failure framework chưa xử lý; có thể chốt ứng
viên bản mới. Trước upload cần chốt version, dựng lại artifact đúng version đó
và kiểm hash/metadata/runtime sạch theo quy trình phát hành. Không upload
candidate 0.8.3. Theo điều kiện chủ dự án đã đặt, cần thử VPS vài ngày và đánh
giá ổn định trước PyPI; soak local 30 phút không thay cho điều kiện này.

## 6. Bằng chứng và thao tác của phiên Windows

Vùng kiểm thử Windows:
`%TEMP%/xime-framework-linux-accept-20261018-pp0xfp89/`.
Giữ command/result JSON, stdout/stderr, JUnit, receipt và đối chứng trước sửa.
Venv Python 3.12 và interpreter nằm riêng trong vùng này; không đổi Python
runtime của ứng dụng hoặc cấu hình/DB thật.

Bản sao bằng chứng Linux chọn lọc được giữ tại
`.claude/temp/linux-logging-20261018T142347Z/`; bằng chứng Windows chọn lọc tại
`.claude/temp/windows-logging-accept-20261019/`. Hai vùng này bị Git bỏ qua;
không stage raw log, fixture private key, venv hoặc wheel vào repo.

Đợt tiếp nhận framework chỉ cập nhật repo framework và tài liệu, giữ version và
dependency framework. Lượt consumer bổ sung ngày 2026-10-19 sửa metadata của hai
app và YAML mẫu Dental như mục 5; chưa đổi build/VPS hoặc commit phần bổ sung này.
Không push/tag/upload PyPI trong các lượt nghiệm thu.
