# Đối chiếu yêu cầu kế hoạch và bằng chứng nghiệm thu

> **Trạng thái:** completion audit sau e5a5b5c ngày 2026-10-17; các mục Windows
> đã có bằng chứng; cả hai full suite cuối đã đạt. Bản vá và bảng này được lưu
> chung trong commit bổ sung sau e5a5b5c.
> **Thuộc bản:** worktree bổ sung F4/F7, metadata vẫn 0.8.3.
> **Thay:** bảng tự kiểm từng nhóm yêu cầu của kế hoạch đã duyệt.
> **Bị thay bởi:** chưa có; không dùng bảng này để đánh dấu Linux đã đạt.

Kế hoạch gốc: [`ke-hoach-va-loi-kiem-toan-framework.md`](../sap-toi/ke-hoach-va-loi-kiem-toan-framework.md).
Chỉ thị làm liền/git add/commit và dừng Linux thay nhịp bàn giao cũ; không mở
phạm vi sang sửa consumer, dịch vụ đang chạy, tag/push/nâng version/phát hành.

| Yêu cầu | Bằng chứng có thể kiểm lại | Kết luận |
|---|---|---|
| 0: baseline/index, 11 file sửa sẵn, HEAD/version | index-before.diff, existing-files-before.json; commit e5a5b5c chứa phần owner đã stage; metadata 0.8.3 | Đạt; chỉ thay index sau chỉ thị git add -A |
| 0: venv/output riêng, không DB/broker/bucket production | venv-jwt, venv-resolved, venv-wheel và các venv wheel-completion; fixture SQLite/tmp_path; log pipeline | Đạt; không cài package vào môi trường chung |
| 0: bằng chứng lưu bền và test cũ đỏ/mới xanh | Báo cáo framework, test_untrusted_input, TestConditionalRanges, test_cleanup_failures, test_environment_check; log red/green | Đạt; không chỉ dựa số passed tổng |
| 1: JWT tĩnh/provider, RecursionError/HTTP, hợp lệ sau đầu vào lỗi | test_untrusted_input.py: verifier/authenticator, ASGI, listener httptools/h11, cause và exception khác | Đạt; bản cũ 5/12 đỏ, bản vá đạt |
| 1: hết hạn, chữ ký, claims, issuer/audience, key rotation, public_paths, options | Toàn bộ tests_temp/jwt và tests_temp/ws; probe options-baseline/options-candidate | Đạt; không bỏ kiểm chữ ký hoặc tái dùng options |
| 1: PyJWT/AnyIO runtime floor, 16 advisory, APScheduler | pyproject; bảng triage 16 mục; audit floors; audit 120 package; APScheduler dùng MemoryDataStore/LocalEventBroker | Đạt; không thêm ACCEPTED; APScheduler cũ vẫn có giới hạn đã ghi |
| 1/7: cài sạch thật, không bị dev che crypto | check_wheel_jwt_runtime.py, wheel-completion/results.json: 15 ca × 2 venv; versions/import path/pip check | Đạt sau sửa F7; wheel cũ lỗi 12 ca mỗi venv |
| 2: strong If-Range, stale/weak/date/missing/malformed, xét trước 416 | TestConditionalRanges; local overwrite và S3-like stat | Đạt; stale Range không thỏa vẫn trả full 200 |
| 2: file rỗng suffix/open/closed, malformed bị bỏ qua | TestConditionalRanges ba dạng valid Range và ba malformed; _parse_range | Đạt; 416 bytes */0, không tạo điểm cuối âm |
| 2: streaming, 404, nosniff, disposition/Unicode, backend trung tính | web_files/storage 95 pass/6 skip; stream_object chỉ stat/open_stream; backend streaming tests | Đạt; không đổi StorageStat/multi-range hoặc hứa snapshot nguyên tử |
| 3: reset context kể cả begin/commit/rollback/close, cancellation | test_cleanup_failures: lỗi close, operation lỗi, close CancelledError, next unit of work | Đạt; finally reset độc lập close |
| 3: giữ lỗi gốc/log/note; không đóng session mượn; outer restoration | test_cleanup_failures và test_read_only; _cleanup.py; test SQLite/entity sống sau khối | Đạt; không thêm savepoint/AOP |
| 4: common/cả hai branch, raw spelling và merged required/alias | test_environment_check, test_check, runtime_environment_overlay; 12 consumer YAML clean | Đạt; không báo oan field kế thừa |
| 4: process.web/processes.<id>.web ID động và SSL schema | test_dynamic_process_and_endpoint_names_are_checked; ssl shape test | Đạt; test topology cũ đã sửa fixture đúng parser |
| 4: không echo credential, kể cả parse lỗi; verdict/HTTP/app schema | ba test yaml_parse_failures, đối chứng HEAD, valid-credential finding, các test HTTP/app block/unreadable | Đạt sau bổ sung nhánh parse; lỗi vẫn inconclusive |
| 5: RSA/ECDSA, TLS 1.2/1.3, default/explicit, startup/reload A→B→C | test_tls.py/test_tls_reload.py; Uvicorn 0.47 đối chứng TLS 1.2 đỏ, 0.48 xanh | Đạt Windows; không chọn cipher cứng thay ứng dụng |
| 5: SNI/no-SNI, keep-alive, cert/key mismatch rollback, wrong CA/host | ma trận test_reload_is_atomic... với handshake thật | Đạt; context cũ còn phục vụ khi reload lỗi |
| 5: watcher/backoff/dedup, client mTLS CA A→B | watcher tests, test_mtls_ca_rotation... với hai CA và client thiếu cert | Đạt cả TLS 1.2/1.3 trên Windows |
| 5: hai worker, ACK đủ/thiếu/hỏng/partial/timeout, promotion, management/public health | TestTlsReloadCoordination chạy thật; test_tls_reload_results; cluster lifecycle/management/health | Đạt; không ép fingerprint bằng nhau; public health giữ status-only |
| 6A: mypy 0, cùng cấu hình, không ignore/Any hàng loạt, không đổi API vì types | mypy 2.3.1/2.4.0: 0/250 file; diff pyproject chỉ dependency; ba cast boundary có giải thích | Đạt; static --platform linux không thay runtime Linux |
| 6A: kiểm hồi quy module bị ảnh hưởng | types-focused.log: 898 passed/6 skipped; full suite | Đạt; không viết test chỉ lặp annotation |
| 6B: đo EN/VN, phân loại từng tên, giữ exports, API có ngữ cảnh | phan-loai-api-cong-khai.md: 152 lượt, 94 API/54 infra/4 alias; docs 0/317 thiếu cả hai; __all__ không đổi | Đạt; registry/scanner có lý do riêng, không quảng cáo điểm mở rộng |
| 6B: import/cú pháp/register/ví dụ, docs feature và backlog | 410 import/49 file, 438 block, 6 ví dụ thực thi; register 0 lỗi/2 ví dụ cũ chưa đủ import; Range/transaction/config/starters/README cập nhật | Đạt theo phạm vi; không gọi các ví dụ cũ bỏ qua là đã kiểm |
| 7: full tests, so collected/skip/deselect, _alive riêng, lint/type/pip/advisory | full-completion.xml và full-completion-resolved.xml: mỗi bộ 2.884 pass/25 skip/1 deselect, thu thập 2.910; _alive riêng 1 pass; floor-f7.log; hai artifact runtime audit exit 0 | Đạt cả hai bộ dependency |
| 7: dependency mới do resolver chọn, artifact không rò nội bộ, cài wheel ngoài checkout | resolver `[all,dev]`, twine, artifact-completion-check.json; wheel metadata và 251 file khớp source | Đạt; wheel 256/sdist 306 entry, không .claude/test/token |
| 7: consumer tuần tự, không sửa repo/cài lại consumer; config/DI chỉ đúng phạm vi | 6.557 pass/8 skip; 5.709 file tracked không đổi; 24 nhánh/12 graph; consumer-config-equivalence 12 sau parser fix | Đạt; không suy thành startup/hook/DB/cert live |
| Bàn giao: git add -A, commit sau 6, không tag/push/version | e5a5b5c; bản vá bổ sung F4/F7 và tài liệu được lưu chung sau nghiệm thu; chưa push, metadata 0.8.3 | Đạt; không thay lịch sử commit mốc 6 |
| Dừng trước Linux theo chỉ thị | Không WSL/Linux/VPS; runtime Python 3.14 Windows; báo cáo giữ cổng chưa kiểm | Đã tuân thủ, không gắn nhãn Linux pass |

Các điều kiện chưa có môi trường test phù hợp: Python 3.12/Linux/uvloop/POSIX,
minimum của extra còn lại, broker MQTT/MinIO thật, Certbot/ACME/VPS và nghiệp vụ
consumer với DB/cert thật. Chúng được ghi ở cổng nghiệm thu tiếp theo, không
biến số skip thành passed và không tự bật dịch vụ của phiên khác.
