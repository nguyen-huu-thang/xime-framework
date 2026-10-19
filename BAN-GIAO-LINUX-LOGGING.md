# Bàn giao phiên Linux: kiểm thử và hoàn thiện logging Xime

> **Trạng thái:** ĐÃ NHẬN KẾT QUẢ LINUX; giữ đề bài làm lịch sử. Đánh giá tiếp nhận ngày 2026-10-19 ở `NGHIEM-THU-LOGGING.md`.
> **Thuộc bản:** source Windows hiện tại của đợt Trust / dữ liệu mẫu / logging, G1–G4; metadata vẫn 0.8.3, thay đổi chưa phát hành.
> **Thay cái gì:** đề bài Linux hiện hành cho logging file G3 và native gRPC G4; thay phần hướng dẫn Linux ngắn trong `KIEM-THU-GRPC-HANDSHAKE.md`.
> **Bị thay bởi:** [nghiệm thu logging và tiếp nhận bản vá Linux](NGHIEM-THU-LOGGING.md).

## 1. Nhiệm vụ và quyền làm tiếp

Chủ dự án dùng Windows và Linux trên cùng máy. Nguồn mới nằm ở
**`D:\code\xime\xime framework`**. Phiên Windows chỉ viết tài liệu này, không chép
source, không chạy Linux. Phiên Linux tự tìm ổ D đang mount và cây test Linux cũ,
sao lưu rồi nhận source mới vào đúng cây test đó. Không chạy test trên NTFS.

Yêu cầu mới của chủ dự án: **“viết file hướng dẫn cho phiên bên linux test, và
có thể phát triển, viết thêm nếu bên đó có gì khác”**. Đây là quyền tiếp tục
kiểm thử và sửa lỗi liên quan đến đợt logging trong **bản sao thử nghiệm Linux**,
kể cả thêm test, harness và tài liệu. Không phải chuyến chỉ báo cáo rồi chờ duyệt
từng bản vá. Dù `AGENTS.md` yêu cầu hỏi trước khi sửa, chủ dự án đã giao việc này;
không cần hỏi lại cho bản vá nằm đúng phạm vi dưới đây.

Được làm:

- Sửa lỗi tương thích Linux/POSIX của file writer, lock, queue, collector native,
  parser, bootstrap và phối hợp lifecycle/multiprocess liên quan trực tiếp.
- Bổ sung phép đo còn thiếu; sửa harness/test khi chứng minh chính phép đo sai.
- Cập nhật hướng dẫn sử dụng và báo cáo theo kết quả thực tế.
- Tạo cấu hình test riêng trong vùng làm việc; bật file/native cho fixture để đo.

Ranh giới:

- Chỉ sửa cây test Linux; **không ghi ngược lên ổ D hoặc source Windows**.
- Không dùng Git để nhận mã hay bàn giao; không add/commit/push/tag, không bump
  version, không phát hành PyPI, không triển khai VPS hoặc sửa thư mục build.
- Không sửa consumer, Trust/Identity, lịch Trust, nghiệp vụ Kho/Sổ thu chi hay
  DB/schema thật trong chuyến này. Có thể chạy regression consumer nếu có đủ
  source và môi trường test riêng; ghi rõ phần không có. Lỗi ngoài phạm vi thì
  viết tái hiện và đề xuất để chủ dự án quyết sau.
- Giữ grpcio chính thức và thiết kế đã duyệt. Không thay bằng proxy, tự build
  grpcio, thêm dependency runtime hoặc đổi API công khai/chính sách TLS để né lỗi.
- Không bật/tắt dịch vụ đang dùng của người khác. Chỉ tạo loopback listener,
  cert/key tự ký và tài nguyên test riêng; dọn đúng tài nguyên mình tạo.

## 2. Đọc gì và hiện trạng nào là đúng

Đọc theo thứ tự:

1. `CLAUDE.md`, `AGENTS.md`, Claude memory gần nhất và hướng dẫn cha áp dụng.
   Memory/bảng test cũ là lịch sử, kiểm lại với source.
2. `KE-HOACH-ON-DINH-UNG-DUNG.md` và
   `.claude/docs/sap-toi/ke-hoach-trust-du-lieu-mau-va-logging.md`, nhất là mục 6 và 7.5.
3. `docs/vn/logging.md`, `docs/vn/grpc-handshake-logging.md`.
4. `KIEM-THU-GRPC-HANDSHAKE.md` cùng `tests_temp/logging/`,
   `tests_temp/grpc_handshake/` và `xime/observability/`.

`KIEM-THU-LINUX.md` và `.claude/docs/nhap/ban-giao-kiem-thu-linux.md` là chuyến
kiểm toán cũ đã nhận kết quả 2026-10-17. Có thể tham khảo cách giữ bằng chứng,
nhưng **không dùng đề bài, manifest hay số test cũ làm mốc của chuyến này**.

Thiết kế hiện tại:

- File logging dùng Python `logging`, writer riêng với queue hữu hạn; supervisor
  giữ writer chung của cụm. File xoay vòng, append qua restart, có khóa OS.
- **Log ứng dụng và sự kiện gRPC đã chuẩn hóa ghi chung file của dịch vụ**,
  ví dụ `runtime/logs/kho.jsonl`; phân biệt qua logger/event/fields. Không thêm
  file riêng bắt buộc cho native. Mỗi dịch vụ dùng tên file riêng.
- Terminal/file có công tắc và level riêng. `logging.file.enabled` và
  `grpc.handshake_logging.enabled` độc lập. Bật file chưa tự thu được IP handshake.
- Native collector phải chuẩn bị trước import grpc/config ở mỗi process.
  Pipe/reader sống **suốt đời process OS**; Application stop/start chỉ tháo/gắn
  sink, listener và drain. Đổi công tắc native cần restart process.
- Không restore FD2 khi grpcio còn được nạp. `probe.py`/`matrix.py` cũ đo thiết kế
  restore đã bị thay; verdict `not_ready` của chúng không phải verdict G4 mới.
- File nhận LogRecord gRPC đã lọc/chuẩn hóa. Raw stderr C-core và passthrough
  vẫn có đường riêng; công tắc Python console không bao trùm mọi native stderr.

Windows đã kiểm: native suite cuối **30 passed**; full regression tại checkpoint
trước các guard bổ sung **2933 passed / 25 skipped / 1 deselected**. Bảy consumer
có sửa main **2715 passed / 16 skipped**. Đây không phải số nghiệm thu Linux;
phải ghi collection và kết quả thực tế của source nhận được.

## 3. Nhận source vào cây test Linux — phiên Linux tự thực hiện

Dùng tài khoản thường, không chạy pytest bằng root: root có thể đọc được file
`chmod 000`, làm sai phép thử quyền. Xác định mount thật bằng `lsblk -f`,
`findmnt`; không mặc định ổ D là `/mnt/d`. Xác nhận đúng thư mục test cũ; nếu
không xác định được duy nhất thì hỏi đường dẫn trước khi ghi đè.

Trong Bash, thay hai đường dẫn mẫu rồi chạy từng nhóm lệnh và kiểm đầu ra:

```bash
set -euo pipefail
umask 077
NGUON="/DIEM-MOUNT-THAT/code/xime/xime framework"
DICH="/DUONG-DAN-THAT/thu-muc-test-framework"
NGUON="$(realpath -e -- "$NGUON")"
DICH="$(realpath -e -- "$DICH")"
test "$(id -u)" -ne 0
test "$DICH" != / && test "$DICH" != "$HOME"
case "$DICH/" in "$NGUON/"*) exit 2;; esac
case "$NGUON/" in "$DICH/"*) exit 2;; esac
test -f "$NGUON/BAN-GIAO-LINUX-LOGGING.md"
test -f "$NGUON/xime/observability/_grpc_native.py"
test -f "$DICH/pyproject.toml" && test -d "$DICH/xime"
findmnt -T "$NGUON"
findmnt -T "$DICH"
df -h "$DICH"
du -sh "$DICH"
```

Đích phải là filesystem Linux có ngữ nghĩa POSIX như ext4/btrfs/xfs, không phải
NTFS/exFAT/CIFS. Kiểm tiến trình đang dùng đích và đủ dung lượng trước khi thay.
Không chép lên source đang chạy. Sao lưu cả cây cũ, kể cả Git và file chưa commit:

```bash
WORK="$(mktemp -d "$(dirname "$DICH")/xime-linux-logging.XXXXXX")"
printf '%s\n' "$NGUON" > "$WORK/nguon.txt"
printf '%s\n' "$DICH" > "$WORK/dich.txt"
tar -czf "$WORK/cay-linux-cu.tar.gz" -C "$DICH" .
tar -tzf "$WORK/cay-linux-cu.tar.gz" > "$WORK/cay-linux-cu.files.txt"
```

Nếu backup lỗi thì dừng trước khi chép. Backup có thể chứa cấu hình riêng; không
đưa nó vào gói kết quả. Giữ nguyên mọi file/thư mục `.git` ở mọi cấp. Không dùng
Git cũ để suy ra thay đổi của lượt Linux vì source Windows chưa commit.

```bash
R=(rsync -a --checksum --delete --no-perms --no-owner --no-group
   --exclude-from="$NGUON/.claude/scripts/chuyen-may/kiem-thu-linux.rsync-exclude"
   --exclude='/ket-qua-linux-logging/' --exclude='/runtime/')
"${R[@]}" --dry-run --itemize-changes "$NGUON/" "$DICH/" > "$WORK/chep-xem-truoc.log"
cat "$WORK/chep-xem-truoc.log"
```

Đọc dry-run: `--delete` chỉ được xóa source thừa trong **đúng cây test đã sao lưu**,
tránh trộn module cũ với mới. Exclude bảo vệ Git, venv/cache và runtime/log cũ;
**không thêm `--delete-excluded`**. Vẫn chép `.claude/docs`, `.claude/scripts`,
`tests_temp` và `docs`, kể cả file bị gitignore. Không tái sử dụng venv cũ.

```bash
"${R[@]}" --itemize-changes "$NGUON/" "$DICH/" > "$WORK/chep-thuc-te.log"
"${R[@]}" --dry-run --itemize-changes "$NGUON/" "$DICH/" > "$WORK/doi-chieu-sau-chep.log"
test ! -s "$WORK/doi-chieu-sau-chep.log"
mkdir -p "$WORK/incoming"
"${R[@]}" "$DICH/" "$WORK/incoming/"
cd "$DICH"
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$DICH/ket-qua-linux-logging/$RUN"
mkdir -p "$OUT/logs" "$OUT/xml" "$OUT/harness" "$OUT/artifacts"
cp "$WORK/"*.log "$OUT/"
printf '%s\n' "$OUT/BAO-CAO.md" > "$DICH/ket-qua-linux-logging/DOC-BAO-CAO-O-DAY.txt"
```

`$WORK/incoming` là bản nhận trước khi sửa, dùng đối chiếu cuối chuyến. Không sửa
bản này. Tạo bảng hash byte gốc để xác định source nhận; không lấy version 0.8.3
hay manifest của chuyến trước làm bằng chứng:

```bash
python3 - "$WORK/incoming" > "$OUT/source-nhan.sha256" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
skip = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
files = [p for name in ("xime", "tests_temp", "docs")
         for p in (root / name).rglob("*")
         if p.is_file() and not (set(p.relative_to(root).parts) & skip)
         and p.suffix not in {".pyc", ".pyo"}]
files += [root / name for name in (
    "pyproject.toml", "BAN-GIAO-LINUX-LOGGING.md",
    "KE-HOACH-ON-DINH-UNG-DUNG.md", "KIEM-THU-GRPC-HANDSHAKE.md",
    ".claude/docs/sap-toi/ke-hoach-trust-du-lieu-mau-va-logging.md")]
for path in sorted(files):
    print(hashlib.sha256(path.read_bytes()).hexdigest(),
          path.relative_to(root).as_posix(), sep="  ")
PY
sha256sum --check "$OUT/source-nhan.sha256" > "$OUT/logs/source-nhan-check.log"
```

## 4. Môi trường và lưu bằng chứng

Ưu tiên CPython **3.12**, venv mới ngoài source. Nếu có thêm 3.13/3.14 thì đo riêng;
thiếu 3.12 phải ghi chưa kiểm exact floor. Không thay Python hệ thống.

```bash
unset PYTHONHOME PYTHONPATH XIME_ENV APP_ENV XIME_PROCESS_ID
unset GRPC_TRACE GRPC_VERBOSITY _XIME_HANDSHAKER_TRACE
export PYTHONDONTWRITEBYTECODE=1
python3.12 -m venv "$WORK/venv-resolver"
PY="$WORK/venv-resolver/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -e '.[dev]' > "$OUT/logs/install-resolver.log" 2>&1
"$PY" -m pip freeze --all > "$OUT/resolver-freeze.txt"
"$PY" -m pip check > "$OUT/logs/pip-check-resolver.log" 2>&1
uname -a > "$OUT/linux.txt"
cat /etc/os-release >> "$OUT/linux.txt"
findmnt -T "$DICH" > "$OUT/filesystem.txt"
"$PY" -c 'import sys,ssl,grpc,xime; print(sys.version); print(ssl.OPENSSL_VERSION); print(grpc.__version__); print(xime.__file__)' > "$OUT/python-import.txt"
```

Xác nhận `xime.__file__` nằm trong `$DICH/xime`, không phải PyPI hoặc checkout cũ.
Giữ lệnh, thời điểm, thời lượng, exit code, stdout/stderr và JUnit. Không đổ toàn
bộ môi trường vào log. Hàm sau chạy tiếp sau test lỗi để thu bằng chứng; phải đọc
`.exit`, thành công của hàm không đồng nghĩa phép chạy thành công:

```bash
runlog() {
  local ten="$1"; shift
  local bat_dau=$SECONDS ma
  date -u +%FT%TZ > "$OUT/logs/$ten.started.txt"
  printf '%q ' "$@" > "$OUT/logs/$ten.command.txt"
  printf '\n' >> "$OUT/logs/$ten.command.txt"
  if "$@" > "$OUT/logs/$ten.stdout" 2> "$OUT/logs/$ten.stderr"; then ma=0; else ma=$?; fi
  printf '%s\n' "$ma" > "$OUT/logs/$ten.exit"
  printf '%s\n' "$((SECONDS-bat_dau))" > "$OUT/logs/$ten.seconds"
  printf '%s: exit=%s\n' "$ten" "$ma"
}
```

## 5. Thứ tự kiểm thử và điểm dừng

### A. Đo bản nhận trước khi sửa

```bash
runlog collect "$PY" -m pytest tests_temp --collect-only -q
runlog logging-resolver "$PY" -m pytest tests_temp/logging tests_temp/bootstrap/test_application_logging.py -q -ra -p no:cacheprovider --basetemp "$WORK/pytest-logging" --junitxml "$OUT/xml/logging-resolver.xml"
runlog native-resolver "$PY" -m pytest tests_temp/grpc_handshake -q -ra -p no:cacheprovider --basetemp "$WORK/pytest-native" --junitxml "$OUT/xml/native-resolver.xml"
runlog lifetime-resolver "$PY" tests_temp/grpc_handshake/lifetime_probe.py --native --file --all-faults --rate 10000 --workdir "$WORK/probe-resolver"
```

**Điểm dừng A:** ghi baseline vào `BAO-CAO.md`, phân loại lỗi sản phẩm/môi trường/
harness. Nếu lỗi thuộc phạm vi đã giao, tiếp tục sửa theo mục 6; không chờ duyệt
lại. Nếu sai source hoặc môi trường chưa cài được, xử lý việc đó trước khi kết luận.

### B. Các hành vi bắt buộc phải chứng minh

Không chỉ thấy một dòng chứa IP rồi kết luận đạt. Dùng fixture hiện có và thêm
ca còn thiếu khi cần; ghi node ID/lệnh và artifact cho từng nhóm:

| Nhóm | Tiêu chí nghiệm thu |
|---|---|
| Bốn tổ hợp file/native | Tắt native không tạo pipe/thread/tracer/import grpc; tắt file không tạo file/lock/writer. Khi cùng bật, log ứng dụng và native cùng một file JSONL; console độc lập. |
| Path/level/lịch sử | Path tương đối theo CWD, tự tạo parent khi bật; DEBUG chỉ file nếu console INFO; restart append; rotation/retention đúng, không xóa file dịch vụ khác. |
| POSIX lock/I/O | Instance độc lập cùng path bị chặn; khóa trả khi dừng/thoát; quyền không ghi, disk error, queue đầy có báo lỗi an toàn, không đệ quy hoặc treo. Dùng fixture/mô phỏng để kiểm disk error, không làm đầy ổ thật. |
| Handshake thật | HTTP vào TLS, thiếu client cert, TLS không phù hợp, ngắt sớm, timeout; vẫn chạy RPC mTLS hợp lệ. Lỗi trước RPC không gọi interceptor. Cause không suy diễn vượt bằng chứng native. |
| Địa chỉ | So event với socket thực: IP/port nguồn và đích, listener/server_id, PID; nhiều kết nối đồng thời, hai listener, IPv4 và IPv6 thật khi có. IPv4-mapped chuẩn hóa; không lấy địa chỉ của record trước, reason giả hoặc outbound. |
| Context/an toàn | Có UTC/service/logger/event; không tạo request ID/identity giả cho TLS chưa xác thực; không chép raw trace, native pointer, token hay private key vào sự kiện chuẩn hóa. |
| Vòng đời | Hai lần Application start/stop trong một process vẫn thu đúng; prepare cùng cấu hình idempotent, cấu hình muộn/đổi native bị chặn; không restore FD2 sau stop. Stderr thường và native warning/error/fatal không biến mất, không nhân bản/đệ quy; marker nội bộ không lộ. |
| Nhiều process | Spawn thật, hai worker, đổi primary và respawn; một writer file, JSONL hợp lệ; PID đúng worker, supervisor không nhận vơ; kiểm cả tracer Xime tự thêm và operator khai sẵn. Không đổi sang fork để làm test qua. |
| Giới hạn | Queue/rate/buffer có trần; quá tải cố ý có counter/summary tương ứng; tải thường không drop/parse/read/flush lỗi. `emitted` chưa phải ACK ghi đĩa. |
| Thoát process | Đo exit bình thường, SIGINT/SIGTERM riêng; stderr/native destructor muộn và drain có hạn, không deadlock. Ghi đúng giới hạn mất đuôi khi kill/timeout và backpressure nếu stderr ngoài bị nghẽn. |

Nợ SIGTERM app đơn đã tồn tại từ chuyến cũ: không đổi phép thử sang SIGINT rồi
báo SIGTERM đạt. Đo rõ phần logging; nếu cần thay thiết kế signal/lifecycle chung
ngoài logging thì ghi đề xuất, không mở rộng bản vá âm thầm.

Đọc JSON của lifetime probe trong `logs/lifetime-resolver.stdout`: event phải
khớp `expected` theo đủ bộ server/remote/local, đúng PID và bốn RPC hợp lệ. Kiểm
file `application.jsonl` trong vùng probe, không chỉ output collector. Chép riêng
file log đã kiểm vào artifacts; không chép toàn bộ thư mục fixture có key.

### C. Sàn grpcio thật trên Python 3.12

```bash
python3.12 -m venv "$WORK/venv-grpc-floor"
PY_FLOOR="$WORK/venv-grpc-floor/bin/python"
"$PY_FLOOR" -m pip install --upgrade pip
"$PY_FLOOR" -m pip install -e '.[dev]' 'grpcio==1.72.1' 'grpcio-tools==1.72.1' > "$OUT/logs/install-grpc-floor.log" 2>&1
"$PY_FLOOR" -m pip freeze --all > "$OUT/grpc-floor-freeze.txt"
runlog pip-check-grpc-floor "$PY_FLOOR" -m pip check
runlog native-grpc-floor "$PY_FLOOR" -m pytest tests_temp/grpc_handshake tests_temp/logging -q -ra -p no:cacheprovider --basetemp "$WORK/pytest-floor" --junitxml "$OUT/xml/native-grpc-floor.xml"
runlog lifetime-grpc-floor "$PY_FLOOR" tests_temp/grpc_handshake/lifetime_probe.py --native --file --all-faults --rate 10000 --workdir "$WORK/probe-grpc-floor"
```

Xác minh cả hai package đúng 1.72.1 và import đúng source. Nếu sàn không thu đủ
metadata trên Linux, giữ bằng chứng rồi sửa trong phạm vi collector/parser khi
có thể. Không bỏ test, tự nâng sàn hoặc thay 1.72.1 bằng phiên bản mới mà vẫn báo
đạt. Thay đổi dependency cần chủ dự án duyệt riêng. Chuyến này không yêu cầu
làm lại toàn bộ ma trận minimum của mọi extra từ chuyến kiểm toán trước.

### D. Full regression, uvloop và chi phí

Trước full suite, đọc `tests_temp/mqtt/test_integration.py` và
`tests_temp/storage/test_s3_integration.py`. Chỉ dùng broker/MinIO test riêng;
nếu không có, đặt các biến `XIME_TEST_MQTT_HOST/PORT`, `XIME_TEST_S3_ENDPOINT`
tới loopback/cổng đã xác nhận không có listener để các ca skip rõ lý do. Không
để biến sẵn có trỏ tài nguyên thật; không sửa/bỏ test integration cho xanh.

```bash
runlog full-resolver "$PY" -m pytest tests_temp -q -ra -p no:cacheprovider --basetemp "$WORK/pytest-full-resolver" --junitxml "$OUT/xml/full-resolver.xml"
runlog full-grpc-floor "$PY_FLOOR" -m pytest tests_temp -q -ra -p no:cacheprovider --basetemp "$WORK/pytest-full-floor" --junitxml "$OUT/xml/full-grpc-floor.xml"
runlog ruff "$PY" -m ruff check xime/ tests_temp/logging/ tests_temp/grpc_handshake/
runlog mypy "$PY" -m mypy xime/
runlog benchmark "$PY" tests_temp/grpc_handshake/benchmark.py --runs 5 --output-dir "$WORK/benchmark"
```

Linux full chạy cả `tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive`;
không mang deselect riêng của Windows sang đây. Ghi từng lý do skip và thay đổi
collection. Lint cả các test khác do mình thêm/sửa. Chỉ chạy lại full sau bản vá
khi cần xác nhận bản nguồn cuối, không cộng nhiều lượt thành tổng test độc lập.

Kiểm thêm **uvloop thực sự đang chạy**, cả trong pytest và worker Application.
Tham khảo mục 5.2 của `.claude/docs/nhap/ban-giao-kiem-thu-linux.md`: dùng harness
ngoài source, đối chứng asyncio/uvloop hai chiều rồi chạy native/logging và full
suite dưới loop đã chứng minh. Phiên bản pytest-asyncio mới có thể cần điều chỉnh
harness theo API đang cài. `pip freeze` có uvloop hoặc monkeypatch `sys.platform`
không chứng minh runtime đang dùng uvloop. Thu loop type thực từ worker spawn.

Benchmark so native off/on với **file bật cả hai**, cùng workload, cùng máy và
dependency, không gán số Windows làm ngưỡng Linux. Đo thời gian/CPU; nếu cần thêm
RSS, thread/FD và backlog khi overload thì bổ sung harness. Rate limit không
loại chi phí sinh trace C-core. Chép `benchmark.json` vào artifacts, không chép
cả cây benchmark có fixture key. Không cần chạy soak nhiều ngày trên máy này;
đợt VPS thật do chủ dự án triển khai sau.

**Điểm dừng B:** mọi cổng bắt buộc có kết quả hoặc trạng thái CHƯA KIỂM kèm lý do.
Nếu phát hiện lỗi, thực hiện vòng sửa ở mục 6 rồi nghiệm thu lại bản nguồn cuối.

## 6. Khi Linux khác Windows hoặc cần viết thêm

Với mỗi vấn đề, giữ lại command/log của bản nhận, expected/actual, ảnh hưởng và
cách phân biệt sản phẩm với môi trường/harness. Viết test/tái hiện có ý nghĩa,
chứng minh đỏ trước sửa và xanh sau sửa khi khả thi. Không nới assertion, tăng
timeout tùy tiện hoặc thêm skip chỉ để khớp số đã ghi bên Windows.

Sửa nhỏ đúng cơ chế gây lỗi, giữ nhánh Windows hoạt động. Mã chạm POSIX phải có
test thật trên Linux; mã chạm nhánh chung ghi rõ Windows cần chạy lại sau khi
mang về. Cập nhật docs EN/VN nếu hành vi hoặc giới hạn sử dụng thay đổi.

Được viết thêm harness cho tình huống Linux chưa có, nhưng phải nêu nó đo gì và
đầu ra nào quyết định đạt. Nếu chạm giả định thiết kế đã duyệt, không đánh tráo
đề bài: ghi blocker và phương án để chủ dự án quyết; vẫn hoàn thành các phép đo
độc lập còn làm được. Không kết luận đã hoàn tất nếu cổng còn mở.

Sau sửa chạy test mục tiêu, logging/native ở resolver và exact floor, rồi các
full regression liên quan và lint/type trên bản cuối. Giữ kết quả trước/sau
riêng; không ghi đè bằng chứng lỗi ban đầu.

## 7. Cấu hình vận hành cần bàn giao, chưa áp dụng VPS

Kết luận đã thống nhất với chủ dự án:

- Một file chung mỗi dịch vụ: `runtime/logs/<tên-service>.jsonl`; thay tên thật,
  không hiểu ký hiệu này là nội suy YAML đã có. Path theo CWD; VPS cần giữ thư
  mục runtime qua lần thay source hoặc chọn đường dẫn tuyệt đối bền vững.
- Framework/dev mặc định file tắt, native tắt; terminal INFO độc lập.
- VPS thường xuyên: khuyến nghị file bật INFO. Đợt điều tra IP: bật thêm native
  WARNING; DEBUG của file chỉ bật khi cần. Restart process để đổi native.
- Mẫu hiện tại file tắt/level DEBUG, native tắt; không tự sửa YAML thật của
  consumer hoặc đổi default framework thành bật. Đề xuất cấu hình VPS trong
  báo cáo để chủ dự án áp dụng thủ công sau khi đọc kết quả.
- Rotation hiện tại 10 MiB + 5 bản cũ, khoảng 60 MiB mỗi dịch vụ, có sai số một
  record bị giới hạn/newline. Không cho logrotate cùng sở hữu family file này.
- IP là TCP peer server nhìn thấy, có thể là NAT/proxy; không suy ra danh tính
  hay IP gốc trước proxy. SNI không phải IP nguồn.

## 8. Báo cáo và gói mang về Windows

Tạo **`$OUT/BAO-CAO.md`**. Ghi kết luận và giới hạn trước, tối thiểu gồm:

1. Source nhận (hash, đường dẫn), source import thực; OS/kernel/filesystem,
   Python/OpenSSL/grpcio/tools/protobuf/pytest-asyncio/uvloop, dependency freeze.
2. Bảng từng cổng A–D và từng nhóm mục 5.B: ĐẠT / LỖI SẢN PHẨM /
   LỖI MÔI TRƯỜNG-HARNESS / CHƯA KIỂM, kèm đường dẫn log/XML tương đối.
3. Kết quả bản nhận và bản cuối tách riêng; collected/pass/fail/error/skip/
   deselect, lý do skip; sàn 1.72.1 và uvloop có thực chạy hay không.
4. Mỗi lỗi: tái hiện, nguyên nhân, file sửa, thay đổi hành vi, test trước/sau;
   nhánh Windows cần kiểm lại; việc ngoài phạm vi/chưa giải quyết.
5. Chất lượng địa chỉ và JSONL chung, counter/overload/shutdown/lock; benchmark,
   FD/thread/RAM nếu đã đo; giới hạn backpressure, mất đuôi, SIGTERM còn mở.
6. Danh sách file thêm/sửa/xóa so với **incoming của chuyến này**, không so HEAD
   Git cũ; hướng dẫn tiếp nhận về Windows và cấu hình VPS được đề xuất.
7. Tiến trình/tài nguyên test đã dọn và thứ còn giữ; đường dẫn cây test, báo cáo
   và thư mục mang về. Không gọi Linux local là đã triển khai VPS/thử vài ngày.

Để chủ dự án không bỏ sót source mới hoặc mang theo venv/key, chuẩn bị vùng gửi
về bên ngoài cây test. Đây chỉ là bản chép bàn giao do **phiên Linux** tạo, không
ghi vào ổ D và không tự tạo bản phát hành:

```bash
GUI_VE="$WORK/gui-ve-windows"
mkdir -p "$GUI_VE/source-final" "$GUI_VE/ket-qua"
"${R[@]}" "$DICH/" "$GUI_VE/source-final/"
rsync -a "$OUT/" "$GUI_VE/ket-qua/"
diff_rc=0
diff -ruN --no-dereference "$WORK/incoming" "$GUI_VE/source-final" > "$GUI_VE/THAY-DOI-SO-VOI-INCOMING.diff" || diff_rc=$?
test "$diff_rc" -le 1
```

Diff exit 1 nghĩa có thay đổi; lớn hơn 1 là lỗi đọc/đối chiếu, cần xử lý. Bổ sung
`DANH-SACH-THAY-DOI.md` ghi cả file bị xóa để Windows không chép trộn rồi giữ
module lỗi thời. `source-final` chứa source/test/docs cuối, giữ `.claude/docs` và
scripts cần tái hiện; không có `.git`, venv/cache, runtime cũ hoặc backup cây cũ.

Kiểm nội dung `gui-ve-windows` trước khi giao: không có `.env`, token, cấu hình
connector cá nhân, credential thật, private key của fixture, venv/wheel hay log
ngoài phạm vi. Không chép nguyên `$WORK` hoặc basetemp/probe/benchmark. Nếu phát
hiện secret trong log bằng chứng, che bản gửi và ghi rõ cách che trong báo cáo.
Giữ JSON/JUnit/stdout/stderr cần tái hiện cùng source cuối và harness đã viết.

Tạo bảng SHA-256 của **gói trả về** sau khi kiểm nội dung:

```bash
cd "$GUI_VE"
find . -type f ! -name 'TRA-VE.sha256' -print0 | sort -z | xargs -0 sha256sum > TRA-VE.sha256
sha256sum --check TRA-VE.sha256 > "$WORK/kiem-goi-tra-ve.log"
```

**Điểm dừng cuối:** báo đường dẫn tuyệt đối `gui-ve-windows` và
`ket-qua/BAO-CAO.md`; chủ dự án tự ZIP thư mục đó và chuyển sang `D:\temp`.
Phiên Windows sẽ giải nén, đối chiếu source/diff/hash, đọc báo cáo, kiểm lại
Windows rồi tiếp nhận những thay đổi phù hợp. Không tự sync ngược, commit,
deploy hoặc phát hành trong chuyến Linux này.
