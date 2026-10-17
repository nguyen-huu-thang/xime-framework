# Bàn giao nghiệm thu phần còn lại trên Linux

> **Trạng thái:** ĐÃ NHẬN KẾT QUẢ 2026-10-17; giữ đề bài làm lịch sử của chuyến.
> **Thuộc bản:** source sau `78c0fa8`, tiếp nối `e5a5b5c`; metadata `0.8.3`, chưa phát hành các bản vá này.
> **Thay cái gì:** đề bài chuyến Linux cho Bước 7 của kế hoạch kiểm toán đã duyệt; không tiếp tục các đề bài Linux tháng 8–9.
> **Bị thay bởi:** [đánh giá tiếp nhận](../kiem-toan/nghiem-thu-linux-framework.md) và báo cáo thô đã chép về Windows.

## 1. Đọc đầu tiên: quyền làm việc và mốc hiện tại

Bạn là phiên Linux, có thể chưa biết cuộc trò chuyện bên Windows. Chủ dự án dùng
hai hệ điều hành trên cùng máy. Nhiệm vụ: nhận source Windows hiện tại, thay source
cũ trong thư mục test Linux, chạy các cổng còn thiếu, viết báo cáo và để chủ dự án
tự đóng ZIP mang về ổ D. **Không cần Git để chuyển mã.**

Đọc `CLAUDE.md`, `AGENTS.md`, `.claude/AGENTS.md` và ngữ cảnh Claude gần nhất của
cây nhận; đọc hướng dẫn cha khi áp dụng. Các bảng phiên bản/test cũ trong Claude
memory là lịch sử. Mốc kiểm toán hiện tại nằm ở:

1. [Kế hoạch đã duyệt](../sap-toi/ke-hoach-va-loi-kiem-toan-framework.md), mục 11.
2. [Đối chiếu từng yêu cầu](../kiem-toan/doi-chieu-nghiem-thu-ke-hoach.md).
3. [Nghiệm thu Windows](../kiem-toan/nghiem-thu-windows-framework.md).

Windows đã sửa F1 JWT, F2/F6 file Range, F3 cleanup transaction, F4 checker config,
F5 TLS mặc định, mypy và tài liệu API. Bổ sung cuối sửa runtime crypto của extra
JWT và che credential khi YAML hỏng. **Không làm lại kế hoạch từ đầu.**

| Mốc Windows cuối | Bằng chứng đã có, không phải kết quả Linux |
|---|---|
| Source | `78c0fa8` sau `e5a5b5c`; version vẫn `0.8.3` nên version không chứng minh đúng source |
| Full framework, hai tập dependency | Mỗi tập 2.884 passed / 25 skipped / 1 deselected; 2.910 collected |
| `_alive(current_pid)` | Một test chạy riêng đạt; Windows gộp có hạn chế; Linux phải thử gộp bình thường |
| Lint/type/docs | Ruff sạch; mypy 0 lỗi/250 file; 410 imports, 438 Python blocks; EN/VN 0/317 tên thiếu |
| Wheel JWT sạch | 15 ca × 2 môi trường resolver/sàn; chỉ cài wheel `[jwt]`, không dev |
| Consumer | 12 suite chạy tuần tự: 6.557 passed/8 skipped; config/đồ thị DI đạt; không chứng minh startup/DB live |

Chép đè cây test Linux đã được yêu cầu. **Sao lưu trước; giữ mọi `.git` file/thư mục**.
Không dùng `clone/pull/checkout/reset/clean/stash/add/commit/push/tag` cho chuyến này.
Git cũ phía Linux không đại diện cho source vừa nhận. Không đọc `git diff` với HEAD
cũ rồi kết luận đó là thay đổi bạn vừa làm.

Chỉ test và viết báo cáo/harness trong thư mục kết quả. Phát hiện lỗi framework thì
ghi tái hiện, mức ảnh hưởng và đề xuất; **chờ duyệt trước khi sửa source** theo
`AGENTS.md`. Không tự đổi test/skip để có màu xanh. Không bump version, phát hành,
sửa consumer hay cấu hình/DB/cert thật. Mọi phép thử mới dùng loopback và tài nguyên
test riêng. Không bật/tắt dịch vụ của phiên khác.

## 2. Tìm nguồn, xác nhận đích và sao lưu cây cũ

Không chạy test trực tiếp trên NTFS: các phép kiểm chmod/Unix socket/symlink sẽ
không còn đo đúng điều kiện Linux. Dùng tài khoản thường, **không chạy pytest bằng
root**; root đọc được file `chmod 000` và làm sai phép thử quyền đọc.

```bash
lsblk -f
findmnt -t ntfs,ntfs3,fuseblk
```

Tìm đường dẫn tương ứng `D:\code\xime\xime framework`. `/mnt/d/...` và
`/media/<user>/<volume>/...` chỉ là ví dụ. Tìm đúng thư mục test cũ theo ngữ cảnh
Linux; nếu có nhiều thư mục không phân biệt được thì hỏi đường dẫn, không đoán.
Chạy trong Bash, thay hai giá trị sau bằng đường dẫn đã tìm được:

```bash
set -euo pipefail
umask 077
NGUON="/DIEM-MOUNT-THAT/code/xime/xime framework"
DICH="/DUONG-DAN-THAT/thu-muc-test-framework"
NGUON="$(realpath -e -- "$NGUON")"
DICH="$(realpath -e -- "$DICH")"
test "$(id -u)" -ne 0
test "$DICH" != / && test "$DICH" != "$HOME"
case "$DICH/" in "$NGUON/"*) echo 'Dich nam trong nguon'; exit 2;; esac
case "$NGUON/" in "$DICH/"*) echo 'Nguon nam trong dich'; exit 2;; esac
test -f "$NGUON/KIEM-THU-LINUX.sha256"
test -f "$NGUON/pyproject.toml" && test -d "$NGUON/xime"
test -f "$DICH/pyproject.toml" && test -d "$DICH/xime"
test -f "$NGUON/.claude/scripts/chuyen-may/kiem-thu-linux.rsync-exclude"
printf 'NGUON=%s\nDICH=%s\n' "$NGUON" "$DICH"
findmnt -T "$NGUON"
findmnt -T "$DICH"
df -h "$DICH" "$(dirname "$DICH")"
du -sh "$DICH"
```

Đọc kết quả thật: đích phải là filesystem Linux có ngữ nghĩa POSIX, chẳng hạn
ext4/btrfs/xfs; không phải NTFS/exFAT/CIFS. Đích phải là đúng cây test framework,
không phải workspace cha/home/ổ mount. Kiểm tiến trình hiện có dùng cây đích và
dung lượng trống trước khi thay; không chép lên source đang được phiên khác dùng.

Tạo vùng làm việc ở **ngoài đích**, cùng filesystem Linux. Sao lưu toàn bộ cây cũ,
kể cả `.git`, file chưa commit và kết quả cũ; không cần tạo commit/stash để sao lưu.
Các lệnh dưới không xóa bản sao lưu:

```bash
WORK="$(mktemp -d "$(dirname "$DICH")/xime-linux-handoff.XXXXXX")"
printf '%s\n' "$NGUON" > "$WORK/nguon.txt"
printf '%s\n' "$DICH" > "$WORK/dich.txt"
tar -czf "$WORK/cay-linux-cu.tar.gz" -C "$DICH" .
tar -tzf "$WORK/cay-linux-cu.tar.gz" > "$WORK/cay-linux-cu.files.txt"
printf 'SAO LUU: %s\n' "$WORK/cay-linux-cu.tar.gz"
```

Nếu backup không hoàn thành hoặc không đủ chỗ thì dừng trước đồng bộ. Backup có
thể chứa cấu hình riêng của Linux; để ở vùng riêng này, không đưa vào ZIP kết quả.

## 3. Chép đè và đối chiếu source, trừ Git

Loại trừ `.git` ở **mọi cấp**, venv/cache/build dựng lại được và cấu hình riêng máy
(`pypi_token.py`, `.env*`, cấu hình connector cục bộ). Vẫn chép **`.claude/docs`,
`.claude/scripts`, tests_temp và docs**, kể cả nội dung Git bỏ qua. Danh sách loại
trừ nằm trong file đi kèm; không thay bằng `git clone` hoặc chỉ chép file tracked.

Kiểm nguồn **trước** khi chép; nếu lệch, báo Windows làm tươi bảng kiểm từ cây đã
chốt, không tự sinh lại bảng kiểm trên Linux:

```bash
(cd "$NGUON" && sha256sum --check KIEM-THU-LINUX.sha256) > "$WORK/kiem-nguon.log" 2>&1
R=(rsync -rlt --delete --no-perms --no-owner --no-group
   --exclude-from="$NGUON/.claude/scripts/chuyen-may/kiem-thu-linux.rsync-exclude")
"${R[@]}" --dry-run --itemize-changes "$NGUON/" "$DICH/" > "$WORK/chep-xem-truoc.log"
cat "$WORK/chep-xem-truoc.log"
```

Đọc danh sách trước khi thực thi: chỉ tác động cây test đã kiểm. `--delete` dọn
source cũ đã bị xóa/đổi tên ở Windows, tránh sót module cũ. `.git` bị exclude nên
được bảo vệ; **không thêm `--delete-excluded`**. Venv/cache cũ bị exclude cũng được
giữ nhưng không được dùng để nghiệm thu. Bản sao lưu vẫn giữ source cũ.

```bash
"${R[@]}" --itemize-changes "$NGUON/" "$DICH/" > "$WORK/chep-thuc-te.log"
cd "$DICH"
sha256sum --check KIEM-THU-LINUX.sha256 > "$WORK/kiem-ban-chep.log" 2>&1
cmp "$NGUON/KIEM-THU-LINUX.sha256" "$DICH/KIEM-THU-LINUX.sha256"
sha256sum KIEM-THU-LINUX.sha256 > "$WORK/danh-tinh-source.sha256"
```

Chỉ tiếp tục khi các lệnh kiểm đạt, không chỉ thấy dòng cuối có chữ OK. Bảng kiểm
chuyến này dùng **SHA-256 đầy đủ trên byte gốc**, không chuẩn hóa CRLF: rsync chép
nguyên byte được. Nó bao phủ toàn bộ payload hiện tại trừ chính bảng kiểm và các
mục loại trừ. File `ke-khai.txt` của chuyến cũ không phải mốc lần này.

Tạo kết quả mới, không trộn kết quả cũ vào lượt này:

```bash
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$DICH/ket-qua-kiem-thu-linux/$RUN"
mkdir -p "$OUT/logs" "$OUT/xml" "$OUT/harness" "$OUT/artifacts"
cp "$WORK/"*.log "$WORK/"*.sha256 "$OUT/"
cp KIEM-THU-LINUX.sha256 "$OUT/source-nhan.sha256"
cp .claude/docs/nhap/mau-bao-cao-kiem-thu-linux.md "$OUT/BAO-CAO.md"
printf '%s\n' "$OUT/BAO-CAO.md" > "$DICH/ket-qua-kiem-thu-linux/DOC-BAO-CAO-O-DAY.txt"
printf '%s\n' "$WORK" > "$OUT/vung-lam-viec.txt"
```

## 4. Môi trường test và cách giữ bằng chứng

Ưu tiên **CPython 3.12** (sàn được hỗ trợ), venv mới ở `$WORK`, không tái dùng venv
Linux cũ hoặc binary Windows. Nếu chưa có 3.12, có thể bổ sung interpreter riêng
người dùng bằng công cụ sẵn có; không thay Python hệ thống. Chạy được 3.13/3.14 thì
ghi riêng, phần 3.12 vẫn CHƯA KIỂM nếu không có interpreter ấy.

```bash
unset PYTHONHOME PYTHONPATH
PYTHON=python3.12
"$PYTHON" --version
"$PYTHON" -m venv "$WORK/venv-resolver"
PY="$WORK/venv-resolver/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -e '.[all,dev]' > "$OUT/logs/install-resolver.log" 2>&1
"$PY" -m pip freeze --all > "$OUT/resolver-freeze.txt"
"$PY" -m pip check > "$OUT/logs/pip-check-resolver.log" 2>&1
uname -a > "$OUT/linux.txt"
cat /etc/os-release >> "$OUT/linux.txt"
lscpu > "$OUT/cpu.txt"
free -h > "$OUT/ram.txt"
findmnt -T "$DICH" > "$OUT/filesystem.txt"
"$PY" -c 'import sys,ssl,xime; print(sys.version); print(ssl.OPENSSL_VERSION); print(xime.__file__)' > "$OUT/python-openssl-import.txt"
export PYTHONDONTWRITEBYTECODE=1
```

Xác nhận `xime.__file__` nằm trong **`$DICH/xime`**, không phải gói 0.8.3 trên PyPI
hay checkout cũ. Nếu pip cần index riêng có credential, không ghi URL có mật khẩu
vào báo cáo. Không dùng `env`/`set` để đổ toàn bộ biến môi trường vào log.

Mỗi phép chạy cần lệnh, thời điểm, thời lượng, exit code, log và XML nếu là pytest.
Hàm sau giữ exit code thật dù muốn chạy tiếp để phân loại lỗi; luôn đọc `.exit`,
**không dùng thành công của hàm ghi log để kết luận test đạt**:

```bash
runlog() {
  local ten="$1"; shift
  local bat_dau=$SECONDS ma
  printf '%q ' "$@" > "$OUT/logs/$ten.command.txt"
  printf '\n' >> "$OUT/logs/$ten.command.txt"
  if "$@" > "$OUT/logs/$ten.log" 2>&1; then ma=0; else ma=$?; fi
  printf '%s\n' "$ma" > "$OUT/logs/$ten.exit"
  printf '%s\n' "$((SECONDS-bat_dau))" > "$OUT/logs/$ten.seconds"
  printf '%s: exit=%s; log=%s\n' "$ten" "$ma" "$OUT/logs/$ten.log"
}
```

## 5. Thứ tự nghiệm thu bắt buộc

### 5.1. Full suite Linux với loop pytest mặc định

Trước lượt đầu, đọc hai test integration MQTT/S3 để bảo đảm biến môi trường không
trỏ dịch vụ thật. Khi chưa có test service riêng, dùng cổng loopback đã xác nhận
không có listener, đặt `XIME_TEST_MQTT_HOST/PORT`, `XIME_TEST_S3_ENDPOINT` tương ứng
để chúng skip rõ lý do. Không tự kết nối 1883/9000 chỉ vì ở đó có dịch vụ.

```bash
runlog collect "$PY" -m pytest tests_temp --collect-only -q
runlog full-asyncio "$PY" -m pytest tests_temp -q -ra -p no:cacheprovider \
  --basetemp "$WORK/pytest-asyncio" --junitxml "$OUT/xml/full-asyncio.xml"
```

**Không deselect `_alive(current_pid)` trên Linux.** Không thêm `-k` hay `--ignore`
vào full suite để khớp con số. So collected, passed, failed, error, skipped,
deselected và **từng lý do skip**. Windows thu thập 2.910 ca là mốc tham khảo, không
ép Linux phải có đúng số passed/skipped ấy. Giải thích thay đổi collection do
platform/importorskip/dependency, không coi mất collection là xanh.

POSIX phải thực chạy: `lmdb/test_file_mode.py`, quyền của `storage/test_local_storage.py`,
`link/test_cleanup.py` (`/dev/shm`), Unix socket và `SO_PEERCRED`, socket inheritance,
`web/test_khoa_accept.py::...test_linux_never_switches`,
`web/test_tls.py` đọc key `chmod 000`. Liệt kê node ID thực thu thập nếu cần, không
dùng dấu `...` làm node ID trong lệnh. Dọn shared memory/socket **do lượt này tạo**;
không quét/xóa `/dev/shm` của ứng dụng khác.

### 5.2. uvloop thật: đối chứng trong pytest và trong ứng dụng

`uvicorn[standard]` thường kéo uvloop trên Linux; phải kiểm import và **loop đang
chạy**, không suy từ pip freeze. Đặt harness sau trong `$OUT/harness`, không sửa
source/test gốc:

```bash
cat > "$OUT/harness/plugin_uvloop.py" <<'PY'
import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
PY
cat > "$OUT/harness/test_loop_thuc.py" <<'PY'
import asyncio
import os
import pytest

@pytest.mark.asyncio
async def test_loop_thuc():
    loop = asyncio.get_running_loop()
    ten = type(loop).__module__ + "." + type(loop).__qualname__
    print("LOOP_THUC=" + ten, flush=True)
    assert ten.startswith("uvloop.") == (os.environ["LOOP_MONG_DOI"] == "uvloop")
PY
runlog loop-asyncio env LOOP_MONG_DOI=asyncio "$PY" -m pytest \
  -c "$DICH/pyproject.toml" "$OUT/harness/test_loop_thuc.py" -q -s -p no:cacheprovider
runlog loop-uvloop env LOOP_MONG_DOI=uvloop PYTHONPATH="$OUT/harness" "$PY" -m pytest \
  -c "$DICH/pyproject.toml" "$OUT/harness/test_loop_thuc.py" -q -s -p plugin_uvloop -p no:cacheprovider
```

Hai log phải in hai loại loop khác nhau và cả hai test đạt. Cách đặt policy này
đã được sửa sau bài học plugin fixture bị pytest-asyncio che khuất ở chuyến cũ.
Đây **chỉ là harness test**; sản phẩm dùng `loop_factory`, không đổi sang policy.
Nếu bản pytest-asyncio/Python mới không nhận policy, xác minh API của phiên bản
thực cài rồi chỉnh harness theo loop factory được hỗ trợ; giữ đối chứng hai chiều.
Chưa chứng minh loop thật thì ghi CHƯA KIỂM, không gọi full suite đó là uvloop.

Khi hai đối chứng đạt, chạy toàn bộ trên cùng tập dependency:

```bash
runlog full-uvloop env PYTHONPATH="$OUT/harness" "$PY" -m pytest tests_temp \
  -q -ra -p plugin_uvloop -p no:cacheprovider \
  --basetemp "$WORK/pytest-uvloop" --junitxml "$OUT/xml/full-uvloop.xml"
```

Các nhãn asyncio/uvloop ở trên mô tả loop của pytest; tiến trình con của framework
vẫn tự chọn factory theo môi trường. Không suy rằng mọi worker trong lượt
`full-asyncio` đã chạy asyncio thường.

Kiểm thêm đường `Application.run()` thật: một HTTP worker và cụm ít nhất hai
worker dùng chung listener, HTTPS/WSS, Unix socket/peer credentials. Tận dụng
fixture hiện có trong `tests_temp/processes`, `tests_temp/web/test_tls_reload.py`
và `tests_temp/socket`; app/harness bổ sung để ở thư mục kết quả. Thu log thực thi
`event loop: uvloop.Loop` **của từng worker**, request thành công, HTTPS handshake,
trao đổi WebSocket và shutdown sạch. Probe factory trả khác None chưa đủ.
Nếu fixture đang bắt/nuốt stdout thì harness phải giữ log con hoặc phản hồi loại
loop trực tiếp từ worker, không suy từ log tiến trình cha. Không cần benchmark lại.

### 5.3. TLS và symlink kiểu Certbot trên filesystem Linux

Full suite đã bao phủ phần lớn ma trận. Dùng XML/node IDs để chỉ ra bằng chứng,
chỉ chạy lại nhóm khi cần log rõ hơn hoặc sau khi có thay đổi/failure:

| Phép đo | Bằng chứng cần có |
|---|---|
| RSA/ECDSA × TLS 1.2/1.3 × default/explicit ciphers | Startup, reload A→B→C; SNI/no-SNI; client kiểm CA/hostname thật |
| Giữ context cũ | cert/key mismatch, malformed/không đọc được file; kết nối keep-alive đang có vẫn dùng được |
| mTLS CA A→B | Client CA cũ bị từ chối, client CA mới được nhận, thiếu cert bị từ chối theo chế độ |
| Nhiều worker/management | `tests_temp/processes/test_cluster_lifecycle.py::TestTlsReloadCoordination`; đủ/thiếu/hỏng ACK, partial/timeout, primary promotion; public health chỉ status |
| POSIX permission | Chạy bằng user thường; key 000 bị báo lỗi quyền; không chmod key thật |

**Phần mới cần harness Linux:** dựng lineage trong `$WORK`, không dùng
`/etc/letsencrypt`. Tạo `archive/test/fullchain1.pem`, `privkey1.pem` và
`live/test/fullchain.pem`, `privkey.pem` là symlink tương đối `../../archive/test/...`.
Dùng CA/cert tổng hợp từ fixture TLS hiện có, bật watcher trên app test loopback.

1. Bắt tay thật lấy fingerprint/serial A; giữ một kết nối đang mở.
2. Ghi cặp B vào archive; thay hai symlink qua link tạm + `os.replace` từng link.
   Cố ý có khoảng chỉ cert đổi/key chưa đổi: context cũ phải tiếp tục phục vụ,
   retry sau đó nạp B. Không giả định hai symlink thay được trong một syscall.
3. Đợi watcher; kết nối mới nhận B, kết nối cũ sống; reload lặp B phải deduplicate.
4. Tạo cặp hỏng, link gãy hoặc key không đọc được: log/verdict nêu lỗi, không làm
   rớt context cũ; khôi phục cặp hợp lệ và kiểm tự hồi phục.
5. Bật management riêng; gọi POST `/tls/reload` với JSON `{"server_id":"default"}`
   như `docs/vn/configuration.md`. Ghi mã HTTP, từng ACK, handshake sau reload.
   Thử failure/partial để hook nhận mã lỗi thật; management chỉ bind loopback.

Lưu harness, log, serial/fingerprint và timeline. Không đưa private key vào báo cáo
hay ZIP. **Mô phỏng lineage/hook không chứng minh Certbot/ACME/DNS/VPS thật.** Chỉ
chạy hạ tầng thật nếu có tài nguyên staging và quyền rõ ràng; thiếu thì ghi riêng
CHƯA KIỂM cùng điều kiện để kiểm tiếp.

Harness symlink bổ sung nằm ngoài manifest nên phải giữ lại cùng báo cáo để
Windows đọc được mã và tái hiện; không chỉ gửi một câu “symlink đạt”.

### 5.4. Dependency minimum và tập resolver mới

Resolver mới là tập vừa cài ở 5.1–5.2, không gọi các version Windows là “latest”
vĩnh viễn. Lưu freeze và `pip check` cho mọi venv. Mỗi thử nghiệm minimum dùng venv
mới, đọc floor **từ pyproject hiện nhận**, không chép toàn bộ pin cũ trong Claude.

Thử lần lượt core và các extra `web`, `sqlalchemy`, `jwt`, `scheduler`, `socket`,
`grpc`, `redis`, `lmdb`, `s3`, `mqtt`, `mail`, `modbus`, `opcua`. Tạo constraints cho
dependency trực tiếp của nhóm: đổi `>=floor` thành `==floor`, giữ marker khi có;
bỏ self-reference `xime[...]` và tên trần không có floor như botocore. Cài checkout
với constraints đó trong môi trường riêng; test tools cài riêng khi cần. Nếu cài
`.[all,dev]` cho đủ fixture, vẫn phải giữ constraints và ghi rõ đây là minimum của
**nhóm đang ghim**, các nhóm còn lại do resolver chọn.

- Tập sàn bảo mật/hành vi đã nâng: AnyIO 4.14.2, PyJWT 2.15.0, cryptography 50.0.0,
  Uvicorn 0.48.0. Đo compatibility với core/extra liên quan; tập này khác resolver
  đáng kể thì chạy full suite riêng (có XML, freeze, pip check).
- Các sàn còn lại: tối thiểu install/import + test nhóm tương ứng trên Python
  3.12. SQLAlchemy dùng SQLite/aiosqlite; không dùng DB thật để “làm đủ”.
- Không ghim mọi sàn vào một môi trường rồi coi resolver conflict là lỗi Linux:
  ví dụ grpcio-tools cũ và protobuf mới có thể không cùng giải được. Lưu lỗi đầy đủ,
  xác định metadata/dependency nào xung đột. Nếu sàn khai báo không cài/chạy được,
  ghi phát hiện; thử một tổ hợp thấp nhất giải được và báo hai kết quả riêng.
- `pip-audit --no-deps --disable-pip` chỉ tra advisory, **không chứng minh minimum
  đã cài/chạy được**. Không nâng floor, sửa ACCEPTED hay sửa source khi chưa duyệt.

Không cần vét mọi tổ hợp phiên bản. Bảng báo cáo phải nêu từng extra đã thử, pin,
phiên bản thực cài, test và giới hạn; không gộp nhóm chưa đo thành “minimum đạt”.

### 5.5. Lint, types, docs, advisory và wheel thực cài

```bash
runlog ruff "$PY" -m ruff check xime --no-cache
runlog mypy "$PY" -m mypy xime --cache-dir "$WORK/mypy-cache"
runlog docs-import "$PY" .claude/scripts/check_doc_imports.py
runlog docs-code "$PY" .claude/scripts/check_doc_code.py
runlog docs-register "$PY" .claude/scripts/check_doc_register.py
runlog docs-en "$PY" .claude/scripts/check_doc_coverage.py --docs docs/en
runlog docs-vn "$PY" .claude/scripts/check_doc_coverage.py --docs docs/vn
runlog advisory-floors "$PY" .claude/scripts/check_dep_advisories.py
runlog advisory-resolver "$PY" -m pip_audit --progress-spinner off \
  --format json --output "$OUT/advisory-resolver.json"
runlog build "$PY" -m build --outdir "$OUT/artifacts"
runlog twine "$PY" -m twine check "$OUT/artifacts/"*
```

Đọc output của checker import/register: hai script này có thể in lỗi mà không
trả exit khác 0. Register có ví dụ thiếu import được bỏ qua; ghi số đã kiểm/bỏ qua,
không gọi tất cả đã chạy. Kiểm docs là điều kiện cần, không chứng minh ví dụ nghiệp
vụ đã thực thi.

Advisory: phân biệt exit 1 vì có advisory với lỗi mạng/không chạy được. APScheduler
`PYSEC-2026-282` đã được chấp nhận trong phạm vi **MemoryDataStore/LocalEventBroker
mặc định**, không suy thành external datastore/serializer an toàn. Không thêm ngoại
lệ mới hoặc xóa raw findings. Bộ dữ liệu advisory mới có thể khác Windows.

Kiểm wheel/sdist không chứa `.claude`, `tests_temp`, AGENTS/CLAUDE, credential,
venv/cache hay báo cáo. Pyproject đã whitelist; kiểm cả nội dung artifact và
METADATA Requires-Dist/Requires-Python, không chỉ `twine check`. Version vẫn 0.8.3;
**wheel phải dựng từ source nhận, không tải `xime==0.8.3` trên PyPI thay thế**.

```bash
WHEELS=("$OUT/artifacts/"*.whl)
test "${#WHEELS[@]}" -eq 1 && test -f "${WHEELS[0]}"
runlog wheel-jwt "$PY" .claude/scripts/check_wheel_jwt_runtime.py \
  --wheel "${WHEELS[0]}" --output "$WORK/wheel-jwt"
if test -f "$WORK/wheel-jwt/results.json"; then
  cp "$WORK/wheel-jwt/results.json" "$OUT/wheel-jwt-results.json"
fi
```

Helper dùng được trên Linux: tạo hai venv mới, chỉ cài wheel `[jwt]` với resolver
và sàn JWT/crypto; 15 ca HMAC/RSA/PSS/EC/EdDSA và YAML redaction, pip check/import
trong site-packages, chạy ngoài checkout. Giữ install log đã rà credential. Audit
cả hai runtime venv bằng công cụ bên ngoài môi trường cần đo, không cài pip-audit
vào runtime rồi gọi đó là tập chỉ wheel. **Không chép `synthetic-vectors.json`, key,
venv hoặc pip-cache của helper vào ZIP.**

### 5.6. MQTT, MinIO và consumer nếu có tài nguyên phù hợp

MQTT có 2 test tại `tests_temp/mqtt/test_integration.py`, dùng
`XIME_TEST_MQTT_HOST/PORT`. S3 có 4 test tại `tests_temp/storage/test_s3_integration.py`,
dùng `XIME_TEST_S3_ENDPOINT/BUCKET/ACCESS_KEY/SECRET_KEY`. Khi có thể, dựng test
service riêng, bind 127.0.0.1, dùng cổng đang trống và bucket/topic test; lưu phiên
bản/image digest, thông số không chứa secret, lệnh chạy/dừng. Nếu Docker đã có và
phù hợp thì có thể dùng container riêng; không cài daemon/đổi cấu hình hệ thống để
đẩy hết skip. S3 test ghi/xóa object `it/...`; MQTT test publish `xime/it/...`, nên
không dùng dịch vụ/bucket thật hoặc tài nguyên người khác.

Chạy hai file trên với môi trường test riêng, ghi XML/log và số ca **thực chạy**.
Thiếu service thì ghi CHƯA KIỂM vì thiếu tài nguyên, không đổi thành passed. Dừng
đúng tiến trình/container do lượt này tạo sau khi đo, giữ log cần thiết.

Không bắt buộc tìm/copy lại 12 consumer Windows trên máy này. Nếu chúng hiện có và
được phép test: đọc fixture trước, dùng bản sao/venv test, chạy **tuần tự**, kiểm
import candidate; không cài lại/sửa repo consumer, khởi động service thật hay chạy
migration/seed. Test SQLite/config/DI không được mô tả thành business flow/DB thật.
Ghi rõ những consumer không có hoặc không chạy, giữ cổng live còn mở.

## 6. Kết thúc: báo cáo, kiểm lại source và thư mục để chủ dự án ZIP

Điền [mẫu báo cáo](mau-bao-cao-kiem-thu-linux.md) đã chép vào `$OUT/BAO-CAO.md`.
Không để placeholder hoặc ghi chung “mọi thứ đạt” khi có cổng chưa đo. Tách rõ
**ĐẠT / LỖI SẢN PHẨM / LỖI MÔI TRƯỜNG-HARNESS / CHƯA KIỂM**. Failure phải có lệnh
tái hiện, traceback đủ chẩn đoán, dependency và loop thật; không sửa sản phẩm để
né lỗi fixture/filesystem/root user. Sau khi sửa harness, giữ log lỗi đầu và log
chạy lại, nói rõ lần nào mới có giá trị.

```bash
cd "$DICH"
runlog source-sau-test sha256sum --check KIEM-THU-LINUX.sha256
"${R[@]}" --dry-run --checksum --itemize-changes "$NGUON/" "$DICH/" \
  > "$OUT/source-khac-sau-test.txt"
```

Không chạy rsync thực lần nữa: nó có thể xóa bằng chứng. Bảng hash phát hiện source
đã có bị đổi/mất; dry-run thêm kiểm file nguồn thừa mới sinh. Đọc từng dòng, phân
biệt metadata/mtime với nội dung. Mục kết quả/venv/cache bị exclude theo chủ ý.
Nếu source có thay đổi, báo chính xác; khi sửa được owner duyệt, lưu before/after
và diff so với **cây incoming**, không với Git cũ. Không chép ngược lên ổ D.

Chủ dự án sẽ **tự ZIP thư mục Linux** và chuyển về D. Chuẩn bị để ZIP có source
vừa test + `$OUT` gồm báo cáo, logs, XML, freeze, bảng hash, harness, JSON advisory,
kết quả wheel, artifact nếu cần. Venv/runtime/key test để ở `$WORK` ngoài cây test.
Nếu còn venv/caches/credential cũ ở cây Linux, nêu danh sách loại trừ cho người đóng
gói; không tự xóa source/data cũ đã được exclude. **Không đưa `.git`, venv, cache,
`.env*`, token, connector local, private key, bản backup cây cũ vào ZIP**. Giữ các
log gốc riêng nếu phải tạo bản đã che credential để gửi về.

Tạo `$OUT/NOI-DUNG-GUI-VE.txt`: đường dẫn tuyệt đối cây test, báo cáo, vùng backup,
danh sách file kết quả và mục cần loại trừ. File
`ket-qua-kiem-thu-linux/DOC-BAO-CAO-O-DAY.txt` là con trỏ cho Windows khi giải nén;
nội dung phải nêu cả đường dẫn tương đối trong ZIP, không chỉ đường dẫn Linux.

Cuối phiên, báo chủ dự án đường dẫn cây Linux cần ZIP, đường dẫn báo cáo, tổng
kết quả thực đo và việc còn thiếu. **Không tự đóng gói/chuyển ZIP hay commit** khi
chủ dự án đã nói sẽ tự làm. Bên Windows sẽ đọc ZIP vào thư mục riêng để đối chiếu,
không mặc định giải nén chép đè repo Windows.
