# Script kiểm chứng bảo mật (đợt 2026-08-01)

Bốn script này là **bằng chứng chạy được** của báo cáo
[`../../docs/kiem-toan/0.7-bao-mat.md`](../../docs/kiem-toan/0.7-bao-mat.md). Chúng không sửa gì
trong repo, không cần service nào đang chạy, và tự chèn `d:/code/xime/xime framework` vào
`sys.path` nên chạy được ngay bằng Python hệ thống.

```bash
python .claude/scripts/bao-mat/poc_web.py
python .claude/scripts/bao-mat/poc_web2.py
python .claude/scripts/bao-mat/poc_config.py
python .claude/scripts/bao-mat/poc_cors_real.py
```

| Script | PoC | Kiểm điều gì | Kết quả 2026-08-01 |
|---|---|---|---|
| `poc_web.py` | 1 | WebSocket có bị `JwtAuthMiddleware` chặn không | ❌ **KHÔNG** - đi thẳng qua (F1) |
| | 2 | `cors.allow_origins` khai dạng chuỗi trong YAML | ❌ thành wildcard / khớp chuỗi con (F4) |
| | 3 | `filename` người dùng nhét vào `Content-Disposition` | ❌ tên tiếng Việt -> 500 (F8) |
| | 4 | `validate_object_key` với khóa dị dạng | ⚠ cho lọt khóa có `\` (F14) |
| | 5 | Lách `public_paths` bằng chuẩn hóa đường dẫn | ✅ **ĐẠT** - mọi biến thể đều 401 |
| `poc_web2.py` | 6 | CRLF trong filename có ra tới dây qua uvicorn thật | ✅ **ĐẠT** - h11 và httptools đều chặn |
| | 7 | `LocalFileStorage._resolve` chống traversal | ✅ **ĐẠT** - phòng tuyến `.resolve()` giữ vững |
| | 8 | Content-Type kẻ tấn công khai lúc upload có quay ra lúc tải về | ❌ **CÓ** - XSS lưu trữ (F2) |
| `poc_config.py` | 9 | `RuntimeConfig` in secret khi log/repr | ❌ **CÓ** rò (F5) |
| | 10 | `XIME_ENV` đọc được file ngoài `resources/` không | ✅ **ĐẠT** - không đọc được |
| | 11 | Thiếu file profile YAML thì sao | ⚠ im lặng chạy tiếp (F7) |
| `poc_cors_real.py` | 12 | CORS thật của 23 app với origin là IP công cộng | ❌ **cấp quyền kèm credentials** (A2) |

**Ba PoC cho kết quả ĐẠT (5, 6, 7, 10) quan trọng ngang những cái tìm ra lỗi** - chúng là lý do
báo cáo không thổi phồng CRLF thành response splitting và không thổi phồng khóa `..\` thành path
traversal. Chạy lại trước khi kết luận bất cứ điều gì về bốn miền đó.

Chạy lại toàn bộ sau khi vá để xác nhận, và trước mỗi lần phát hành lên PyPI - cạnh ba script
`check_doc_imports.py` / `check_doc_register.py` / `find_reexport_gap.py` ở thư mục cha.

## Công cụ quét tự động

Không lưu ở đây vì chúng cần cài gói. Cách dựng lại (venv riêng, không đụng môi trường chính):

```bash
python -m venv /tmp/secaudit
/tmp/secaudit/Scripts/python.exe -m pip install bandit semgrep pip-audit
/tmp/secaudit/Scripts/python.exe -m bandit -r xime -f json -o bandit.json
/tmp/secaudit/Scripts/semgrep.exe --config=p/security-audit --metrics=off xime
/tmp/secaudit/Scripts/python.exe -m pip_audit -r <bộ deps SÀN theo pyproject.toml>
```

Đợt 2026-08-01: bandit và semgrep **không tìm ra lỗ hổng thật nào** (toàn dương tính giả).
`pip-audit` trên bộ **sàn** thì tìm ra 26 CVE (F3) - đó là thứ duy nhất trong 24 phát hiện đến từ
công cụ. Chạy `pip-audit` trên deps sàn, **không phải** trên deps đang cài: máy dev luôn có bản
mới nên chạy trên bản đang cài sẽ không thấy gì.
