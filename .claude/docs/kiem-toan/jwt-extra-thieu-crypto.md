# F7 — Extra JWT thiếu backend mật mã trong bản cài runtime sạch

> **Trạng thái:** P2 đã vá trong worktree sau e5a5b5c; wheel runtime sạch đạt
> 15/15 ca trên mỗi bộ resolver/sàn ngày 2026-10-17; full suite đạt trên cả hai bộ dependency.
> **Thuộc bản:** wheel dựng từ e5a5b5c, metadata 0.8.3; không phải bản phát hành mới.
> **Thay:** bổ sung ca cài đặt JWT bất đối xứng còn thiếu trong nghiệm thu Windows.
> **Bị thay bởi:** chưa có.

## Bằng chứng trước vá

Venv `venv-wheel` được cài sạch bằng wheel `[web,jwt]` không có cryptography.
PyJWT chỉ đăng ký HS256/HS384/HS512/none. Tài liệu starters lại hướng dẫn
RS256 và mô tả RSA/EC/EdDSA sau khi cài extra jwt. Pyproject chỉ khai
cryptography >=50.0.0 ở dev; kiểm trên môi trường all/dev đã che mất thiếu sót.

Phép kiểm mới `.claude/scripts/check_wheel_jwt_runtime.py` cài **chỉ wheel[jwt]**
vào venv mới, chạy ngoài checkout bằng Python isolated, không system-site-packages.
Fixture được tạo bằng khóa thử riêng, có chữ ký hợp lệ, audience/issuer/exp.
Kiểm verify token đối chứng, ký/verify vòng kín và từ chối chữ ký bị sửa.

Lượt resolver trên wheel cũ: cài đặt và pip check đều đạt, nhưng **12/15 ca lỗi**:
RS256/384/512, PS256/384/512, ES256/256K/384/512, Ed25519/Ed448 đều trả
AuthenticationException khi verify token hợp lệ. Ba ca HMAC đạt. Đây là lỗi
đóng gói/runtime capability, không phải token hay key sai và không phải bypass.

Hướng vá: extra jwt kéo PyJWT[crypto] và giữ sàn cryptography >=50.0.0 đã có
căn cứ advisory trong dev. Dev vốn kéo all→jwt nên không cần khai bản sao sàn
cryptography ở dev. Không thay code signer/verifier hoặc mở thuật toán yếu hơn.

Nguồn PyJWT chính chủ xác nhận backend crypto cần cho RSA/ECDSA và cách khai
extra: [PyJWT installation](https://pyjwt.readthedocs.io/en/stable/installation.html).

## Nghiệm thu bổ sung

| Phép kiểm | Kết quả |
|---|---|
| Wheel cũ, resolver | 3 HMAC đạt; 12 ca bất đối xứng lỗi; cài đặt/pip check vẫn đạt |
| Wheel cũ, PyJWT đúng sàn 2.15.0 | Cùng 3 đạt/12 lỗi, không có backend crypto |
| Wheel cuối, resolver: PyJWT 2.15.1 / cryptography 50.0.2 | **15/15 đạt**, pip check đạt, import từ site-packages của venv riêng |
| Wheel cuối, đúng sàn: PyJWT 2.15.0 / cryptography 50.0.0 | **15/15 đạt**, pip check đạt, không system-site-packages/dev extra |
| Nhóm JWT/WebSocket/API surface/root | **290 passed**, không sửa signer/verifier để né lỗi |
| Toàn bộ source sau bổ sung, bộ sàn mới | **2.884 passed, 25 skipped, 1 deselected**, 274,92 giây |
| Toàn bộ source sau bổ sung, resolver mới | **2.884 passed, 25 skipped, 1 deselected**, 319,40 giây |
| Audit toàn bộ dependency của hai runtime wheel sạch | Không có advisory được báo; cả hai exit 0 |
| Mypy/Ruff, import/cú pháp/coverage/register | Đạt; mypy 0/250, coverage EN/VN thiếu 0/317 |

Extra jwt hiện khai `pyjwt[crypto]>=2.15.0` và `cryptography>=50.0.0`.
Dev vốn kéo all→jwt nên đã gỡ bản sao floor ở dev; core không tự kéo crypto
khi ứng dụng không chọn JWT. Không đổi thuật toán cho phép hay số phiên bản.

15 ca gồm HS256/384/512, RS256/384/512, PS256/384/512,
ES256/256K/384/512 và hai kiểu khóa Ed25519/Ed448 cho EdDSA. Mỗi ca kiểm
token đối chứng ký bằng PyJWT, ký/verify bằng framework và từ chối chữ ký sửa.
Script còn kiểm nhánh lỗi YAML không echo credential, và từ chối kết quả
thiếu/không đủ ca; không chỉ đếm cài đặt thành công.

Kết quả cũ của e5a5b5c vẫn là lịch sử: HS256 smoke trước đó **không chứng minh**
các họ khóa bất đối xứng. Artifact cuối ở thư mục riêng để không lẫn wheel cũ
cùng metadata 0.8.3. Các ví dụ starters EN/VN đã ghi rõ backend runtime.

Log/output ở `%TEMP%\xime-framework-fixes-20261017\jwt-extra-red*`;
khóa trong fixture chỉ là khóa thử sinh mới, không đọc khóa/cert ứng dụng.

Output nghiệm thu cuối: `artifacts-completion/`, `wheel-completion/results.json`,
`wheel-completion.log`, `jwt-packaging-regression.log`, `floor-f7.log` và
`full-completion.log`, `full-completion.xml`, `full-completion-resolved.log`,
`full-completion-resolved.xml`, `wheel-resolver-advisories.json`,
`wheel-jwt-floors-advisories.json`. Lệnh chạy lại (output phải là thư mục mới):

```powershell
python .claude/scripts/check_wheel_jwt_runtime.py --wheel <wheel-vua-build> --output <thu-muc-temp-moi>
```
