"""Sinh file con trỏ cảnh báo bảo mật vào .claude/ của từng repo bị ảnh hưởng.

Nguyên tắc: file trong repo con CHỈ nói phần dính tới chính nó, mọi thứ còn lại
trỏ về báo cáo gốc ở repo framework.
"""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(r"D:/code")
MASTER = r"D:\code\xime\xime framework\.claude\docs\kiem-toan-bao-mat-0.7.md"
FNAME = "canh-bao-bao-mat-2026-08-01.md"

HEADER = f"""# Cảnh báo bảo mật - kiểm toán 2026-08-01

> **Thông tin gốc nằm ở một chỗ duy nhất, đừng chép lại vào đây:**
> `{MASTER}`
>
> Ở đó có: mô hình mối đe dọa, 24 phát hiện đầy đủ kèm `file:dòng`, 12 PoC chạy
> được (`.claude/scripts/bao-mat/`), phần "đã kiểm và ĐẠT", và bảng thứ tự vá.
>
> File này chỉ trả lời một câu: **repo NÀY dính cái gì, ở dòng nào.**
>
> Trạng thái 2026-08-01: **CHƯA VÁ GÌ CẢ.** Cập nhật dòng này khi vá.
"""

FOOTER_COMMON = """
## Ba điều dễ hiểu nhầm, đọc trước khi sửa

1. **Đây không phải lỗi của framework Xime.** Phần lớn phát hiện ở repo này là lỗi
   *cấu hình* và *cách dùng*, không phải lỗi thư viện. Nâng phiên bản `xime` không
   sửa được gì trong bảng trên.
2. **Đừng sửa lẻ từng repo.** Hầu hết mục dưới đây là bản sao của cùng một khuôn.
   Sửa ở `Application Layer/saas-foundation/template` trước, rồi lan xuống, kẻo
   app thứ 22 lại mang y nguyên lỗi cũ.
3. **Đã có kế hoạch vá chung, đừng vá lẻ ngoài nó.**
   `D:\\code\\xime\\xime framework\\.claude\\docs\\ke-hoach-va-bao-mat-2026-08-01.md`
   - 5 đợt, code cụ thể từng mục, cách kiểm chứng, và 4 quyết định đã chốt của
   chủ dự án. Đổi lẻ cấu hình xác thực của một app có thể làm gãy luồng đăng
   nhập dùng chung.

   Hai điều trong kế hoạch đó ảnh hưởng trực tiếp tới repo này:
   `xime` cài **editable** và **không app nào có venv riêng**, nên một lần sửa
   framework là chạm cả 31 app ngay; và `xime.__version__` đang trả `0.6.3` trong
   khi code thật là `0.7.0`, nên **đừng dùng nó để xác nhận bản vá đã vào chưa**.
"""

# ---------------------------------------------------------------------------
# Mô tả từng phát hiện, viết một lần dùng nhiều nơi
# ---------------------------------------------------------------------------
A1 = ("A1", "🔴 NGHIÊM TRỌNG", "{backend}/app/config/jwt.py (nhánh `if keyset is None: return`)",
      "Không lấy được khóa verify JWT thì **không cài middleware xác thực** rồi vẫn chạy -> toàn bộ API công khai. "
      "`application.yml` bị gitignore nên clone sạch rồi chạy là rơi trúng nhánh này.")
A2 = ("A2", "🟠 CAO", "{backend}/resources/application.yml (`cors.allow_origin_regex`)",
      "Regex chú thích là \"IP LAN\" nhưng khớp **mọi IPv4 công cộng** (`http://203.0.113.66` khớp), "
      "kèm `allow_credentials: true` + `allow_methods: [\"*\"]`. Kẻ tấn công chỉ cần một VPS, không cần tên miền.")
A3S = ("A3", "🟠 CAO", "backend/resources/application.yml:19 + app/service/authentication_service.py:30,79",
       "Ký JWT HS256 bằng `\"dev-secret-CHANGE-IN-PRODUCTION-use-32chars-minimum\"` - **giá trị này nằm trong git**, "
       "`application-production.yml` (cũng trong git) KHÔNG đè nó, và app đã deploy ở `shop.scime.click`. "
       "Biết secret là ký được token cho bất kỳ `uid` nào. Coi như **đã lộ**: đổi secret VÀ vô hiệu token đang sống.")
A3O = ("A3", "🟡 TRUNG", "backend/resources/application.yml (`jwt.secret`) + app/service/authentication_service.py",
       "Dùng **đúng cùng một chuỗi ký** với 5 app Monolithic còn lại: "
       "`\"dev-secret-CHANGE-IN-PRODUCTION-use-32chars-minimum\"`, và code còn có literal đó làm fallback. "
       "Chưa deploy nên chưa nguy hiểm như `shop`, nhưng phải đổi TRƯỚC khi deploy, mỗi app một giá trị ngẫu nhiên riêng.")
A4 = ("A4", "🟡 TRUNG", "{backend}/resources/application.yml (`auth.jwt.public_paths`)",
      "`/docs`, `/redoc`, `/openapi.json` mở công khai -> toàn bộ bản đồ API đọc được không cần đăng nhập. "
      "Tự nó không phải lỗ hổng, nhưng nó rút ngắn giai đoạn thăm dò xuống gần bằng không.")
A5 = ("A5", "🟡 TRUNG", "backend/app/security/jwt_middleware.py (`if not auth_header: ... return`)",
      "Không có header Authorization thì request **đi tiếp ẩn danh**; mỗi controller phải tự nhớ kiểm tra. "
      "Một route mới quên kiểm là một route công khai, và không có gì báo.")
A6 = ("A6", "🟡 TRUNG", "backend/resources/application-production.yml:4 (chú thích)",
      "Chú thích bảo để secret vào `application-secret.yml`. **Framework không bao giờ nạp file đó** "
      "(`YamlConfigLoader` chỉ đọc `application.yml` + `application-{env}.yml`), và file đó không tồn tại. "
      "Đây là nguyên nhân trực tiếp của A3.")
A7 = ("A7", "⚪ THẤP", "{backend}/resources/application.yml (`payment.callback_secret`)",
      "Bí mật HMAC xác thực webhook payment là literal đoán được từ tên app "
      "(`s3cr3t-callback-<tên app>`). Biết khuôn là ký được callback giả \"đã thanh toán\".")

FW_NOTE_APP = """
## Phát hiện thuộc framework nhưng chạm tới repo này

Không sửa ở đây, sửa ở repo `xime framework`. Liệt kê để biết mà tránh:

- **F8** - tải file có tên tiếng Việt (`Hóa đơn.pdf`) trả **HTTP 500**. Nếu repo này
  có tính năng tải file về, đây là lỗi đang xảy ra, không phải nguy cơ.
- **F2** - `save_upload` tin `Content-Type` do client khai, `stream_object` phát lại
  nguyên vẹn -> **XSS lưu trữ** khi backend là S3/MinIO. Chỉ chạm nếu repo này có upload.
- **F11** - `configure_jwt` của framework không ép `audience` mặc định. Repo này KHÔNG
  dùng `configure_jwt` (dùng `TrustJwtAuthMiddleware` tự viết, có ép `aud`/`iss`), nên
  không dính - ghi lại để không ai "sửa nhầm cho chắc".
- **F3** - sàn dependency trong `pyproject.toml` của framework cho phép bộ thư viện có
  26 CVE. Máy dev đang cài bản mới nên không dính; rủi ro nằm ở lần dựng môi trường mới.
"""

FW_NOTE_DATA = """
## Phát hiện thuộc framework, chạm TRỰC TIẾP tới service này

`data-service` là nơi giữ file của mọi app, nên ba phát hiện lưu trữ dưới đây quan
trọng với repo này hơn bất kỳ repo nào khác. Sửa ở repo `xime framework`:

- **F2 (Cao)** - `save_upload` tin `Content-Type` client khai; `stream_object` phát lại
  inline, không có `X-Content-Type-Options: nosniff`, không `Content-Disposition`.
  Với backend S3/MinIO thì tải lên `text/html` là **XSS lưu trữ trên origin của app**.
- **F13 (Thấp)** - localfs ghi file quyền `0644` (đọc được bởi mọi user trên máy); tên
  file tạm là `<key>.<pid>.part` nên **hai lần upload cùng key trong cùng tiến trình ghi
  đè nhau** rồi `os.replace` công bố kết quả lai; `put()` không nguyên tử dù docstring nói có.
- **F16 (Thấp)** - `save_upload` mặc định `max_bytes=None`, tức không giới hạn dung lượng.

**Đã kiểm và ĐẠT, đừng làm lại:** chống path traversal của `LocalFileStorage._resolve`
**giữ vững** trên cả khóa `..\\..\\` lẫn đường dẫn tuyệt đối Windows (PoC 7 trong báo cáo gốc).
"""


def build(findings: list, backend: str, extra: str = "") -> str:
    rows = ["| Mã | Mức | Ở đâu trong repo này | Chuyện gì |", "|---|---|---|---|"]
    for code, level, where, what in findings:
        w = where.format(backend=backend)
        # Bọc backtick phần đường dẫn, để phần chú thích trong ngoặc ra ngoài.
        if " (" in w:
            path, _, note = w.partition(" (")
            w = f"`{path}` ({note}"
        else:
            w = f"`{w}`"
        rows.append(f"| **{code}** | {level} | {w} | {what} |")
    body = HEADER + "\n## Repo này dính những gì\n\n" + "\n".join(rows) + "\n" + extra + FOOTER_COMMON
    return body


def target_dir(repo: Path) -> Path:
    """Ưu tiên .claude/docs; không có thì .claude; chưa có thì tạo .claude/docs."""
    if (repo / ".claude" / "docs").is_dir():
        return repo / ".claude" / "docs"
    if (repo / ".claude").is_dir():
        return repo / ".claude"
    return repo / ".claude" / "docs"


written = []

# --- Nhóm 1: 20 app xime dùng khuôn saas-foundation + chính template -----------
XIME_APPS = [
    "Application Layer/admin", "Application Layer/cho-thue-thiet-bi",
    "Application Layer/dai-ly-phan-phoi", "Application Layer/doi-thi-cong",
    "Application Layer/gara-oto", "Application Layer/gym",
    "Application Layer/linh-kien-dien-tu", "Application Layer/nha-tro",
    "Application Layer/noi-that-do-go", "Application Layer/san-the-thao",
    "Application Layer/shop-hoa-qua-tang", "Application Layer/spa",
    "Application Layer/studio-anh", "Application Layer/sua-chua-dien-may",
    "Application Layer/trung-tam-day-hoc",
    "Service ngang/crm", "Service ngang/giao-viec", "Service ngang/kho",
    "Service ngang/nhan-su-cham-cong", "Service ngang/so-thu-chi",
]

for rel in XIME_APPS:
    repo = ROOT / "xime" / rel
    if not repo.is_dir():
        print("BỎ QUA (không có):", repo)
        continue
    yml = repo / "backend" / "resources" / "application.yml"
    has_cb = yml.is_file() and "callback_secret" in yml.read_text(encoding="utf-8", errors="ignore")
    findings = [A1, A2, A4] + ([A7] if has_cb else [])
    d = target_dir(repo)
    d.mkdir(parents=True, exist_ok=True)
    (d / FNAME).write_text(build(findings, "backend", FW_NOTE_APP), encoding="utf-8")
    written.append(str(d / FNAME))

# --- template saas-foundation (nguồn của mọi bản sao) --------------------------
tmpl = ROOT / "xime" / "Application Layer" / "saas-foundation"
d = target_dir(tmpl)
d.mkdir(parents=True, exist_ok=True)
tmpl_extra = """
## ⚠ Repo này là NGUỒN của 20 bản sao

`template/` là thứ mọi app dọc và service ngang được clone ra từ đó. Nghĩa là:

- **A1 và A2 ở đây là gốc**, 20 chỗ còn lại chỉ là bản sao. Sửa ở đây trước.
- Nhưng sửa ở đây **không tự lan** sang app đã clone - phải sửa từng repo, hoặc viết
  một script vá hàng loạt.
- App thứ 22 clone ra sau khi vá thì sạch; app clone trước đó thì không. Ghi lại ngày
  vá template để biết ranh giới.
""" + FW_NOTE_APP
(d / FNAME).write_text(build([A1, A2, A4, A7], "template", tmpl_extra), encoding="utf-8")
written.append(str(d / FNAME))

# --- Base Platform/data -------------------------------------------------------
data_repo = ROOT / "xime" / "Base Platform" / "data"
d = target_dir(data_repo)
d.mkdir(parents=True, exist_ok=True)
data_extra = """
> **Lưu ý:** service này **KHÔNG** dính A1 (fail-open JWT) - nó không dùng khuôn
> `config/jwt.py` của `saas-foundation`. Đã kiểm, không phải bỏ sót.
""" + FW_NOTE_DATA
A2_data = ("A2", "🟠 CAO", "resources/application.yml (`cors.allow_origin_regex`)", A2[3])
(d / FNAME).write_text(build([A2_data], "", data_extra), encoding="utf-8")
written.append(str(d / FNAME))

# --- Monolithic/shop ----------------------------------------------------------
shop = ROOT / "Monolithic" / "shop" / "backend"
d = target_dir(shop)
d.mkdir(parents=True, exist_ok=True)
shop_extra = """
> **A3 là việc gấp nhất trong toàn bộ đợt kiểm toán** (hạng 1 trong bảng thứ tự vá của
> báo cáo gốc), vì đây là app duy nhất vừa có secret trong git vừa đã deploy thật.
>
> Sửa file thôi là **chưa đủ**: mọi token đã ký bằng secret cũ vẫn hợp lệ tới khi hết
> hạn (`refresh_ttl: 5184000` = 60 ngày). Phải đổi secret **và** vô hiệu token đang sống.

## Đã kiểm và ĐẠT ở repo này, đừng lo thừa

- `validate_token` **có** ép `audience` + `issuer` + `options={"require": [...]}`, và mỗi
  app Monolithic một `aud` riêng. Nên dùng chung secret **không** khiến token của app này
  dùng được ở app kia. (Nhưng biết secret thì tự ký token đúng `aud` là xong - ép `aud`
  chặn tái sử dụng, không chặn giả mạo.)
- `application-production.yml` **có** tắt `allow_origin_regex` (`null`) và khóa CORS về
  đúng một origin. Đây là **codebase duy nhất trong 24 chỗ** làm việc này. A2 vì vậy chỉ
  còn chạm tới môi trường dev của repo này.
"""
(d / FNAME).write_text(build([A3S, A5, A6, A4, A2], "", shop_extra), encoding="utf-8")
written.append(str(d / FNAME))

# --- 5 app Monolithic còn lại -------------------------------------------------
for name in ["auto-garage", "dental-clinic", "english-center", "rental-management", "spa"]:
    repo = ROOT / "Monolithic" / name
    if not repo.is_dir():
        print("BỎ QUA:", repo)
        continue
    d = target_dir(repo)
    d.mkdir(parents=True, exist_ok=True)
    extra = f"""
> **App này chưa deploy** (không phải repo git, không có `application-production.yml`),
> nên A3 ở đây chưa nguy hiểm như ở `shop`. Nhưng phải đổi secret **trước khi** deploy.

## Đã kiểm và ĐẠT ở repo này

- `validate_token` **có** ép `audience` + `issuer` + `require: [jti, exp, iss, aud]`,
  `aud` riêng cho app này. Dùng chung secret với 5 app kia **không** tạo lỗ hổng chéo app.
- Repo này **không** khai `cors.allow_origin_regex`, nên **không dính A2** - lỗ hổng CORS
  lớn nhất của đợt này không chạm tới đây.
"""
    (d / FNAME).write_text(build([A3O, A5], "", extra), encoding="utf-8")
    written.append(str(d / FNAME))

print(f"Đã ghi {len(written)} file:")
for w in written:
    print("  ", w)
