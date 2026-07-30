# Changelog

Tất cả thay đổi đáng chú ý của Xime Framework được ghi ở đây.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/), phiên bản theo
[Semantic Versioning](https://semver.org/lang/vi/).

## [0.7.0] - 2026-07-30

**Fieldbus công nghiệp: adapter Modbus TCP và OPC UA.** Xime nhắm tới công
nghiệp / IIoT, và MQTT (0.5) chỉ nói chuyện được với thiết bị **đã biết nói
MQTT**. Máy móc thật trong nhà máy - PLC, biến tần, đồng hồ đo - nói hai giao
thức khác. Chủ dự án đã chốt **không dùng edge gateway**, nên hai adapter này
là con đường duy nhất tới tầng tiếp xúc.

Đây là **mô hình giao tiếp thứ ba** của framework: web/gRPC/socket là
request/response, MQTT là pub/sub, còn ở đây **framework là bên chủ động** đi
đọc thiết bị theo nhịp. Vì vậy có decorator riêng (`@poll`/`@on_change`) chứ
không tái dùng `@subscribe`.

Tương thích ngược hoàn toàn: không có gì thay đổi với ứng dụng không dùng hai
extra mới. Test: **1454 passed, 5 skipped** (+231 test so với 0.6.3).

Bản này cũng mang theo kết quả một đợt **kiểm toán toàn bộ mã nguồn trước khi
đẩy lên PyPI** - xem hai mục `Fixed` và `Changed` bên dưới. Mọi lỗi trong đó đều
được tái hiện bằng thực nghiệm trước khi vá, và đều có từ các bản **đã phát hành**
(0.6.3 trở về trước).

### Added

- **Adapter Modbus TCP** (`xime/adapters/modbus/`, extra `xime[modbus]`).

  - **Device Model khai báo** - trục chính của cả bản này. Modbus **không mang
    thông tin kiểu**: mỗi lần đọc chỉ trả về mảng word 16-bit thô, và việc ghép
    hai word thành `float32` (đúng thứ tự byte, đúng thứ tự word, đúng hệ số
    scale) là nguồn bug số một khi làm việc với PLC - sai bước nào cũng ra một
    con số trông rất hợp lý chứ không ra lỗi. `@device(unit=...)` +
    `Holding/Input/Coil/Discrete` khai kiến thức đó một lần, dùng cho cả bốn
    chiều: client đọc, client ghi, polling, và làm slave.
  - **Địa chỉ có hai đường vào tường minh, không bao giờ đoán**: `Holding(2)` là
    địa chỉ giao thức 0-based, `Holding(modicon=40003)` là số in trên datasheet.
    Nếu một tham số nhận nhập nhèm cả hai thì trên thiết bị có hơn 40002 thanh
    ghi, `Holding(40001)` sẽ đọc nhầm thanh ghi **mà không có lỗi nào báo**.
  - **Lập kế hoạch đọc theo `max_gap`** (`_planner.py`) - đây là chuyện **đúng
    sai**, không phải tối ưu: đọc một block lớn từ địa chỉ nhỏ nhất tới lớn nhất
    thì chỉ cần một địa chỉ ở giữa không tồn tại là slave trả
    `ILLEGAL DATA ADDRESS` và hỏng **cả** lần đọc, dù mọi field khai đều hợp lệ.
    Planner gom field gần nhau, tách field xa nhau, tự chia khi vượt trần giao
    thức (125 thanh ghi / 2000 bit), và nổ lúc startup nếu một field đơn lẻ lớn
    hơn trần đó.
  - **`@poll` / `@on_change`** + `ModbusAdapter`: một vòng lặp cho mỗi cặp
    `(model, interval)` nên hai handler cùng model, cùng nhịp không gây hai lần
    đọc; `@on_change` quan sát giá trị vòng poll đã lấy (bám vòng **nhanh
    nhất**) chứ không tự gửi lệnh; lần đọc đầu chỉ là **mốc** (bắn ở đó nghĩa là
    mọi handler kêu lúc khởi động - nhiễu, không phải tin tức); `deadband` lọc
    nhiễu đo cho giá trị analog; nhịp không trôi (trừ thời gian chu kỳ khỏi lần
    sleep sau); một chu kỳ lỗi được log rồi chạy tiếp.
  - **Chế độ slave** (`ModbusServerAdapter`, `@serve` / `@on_write`): mỗi
    `@device(unit=N)` là một `SimDevice` riêng nên một tiến trình đóng vai nhiều
    thiết bị sau một cổng. Giá trị **đẩy theo nhịp** (hỏi handler lúc master đọc
    sẽ để code nghiệp vụ chạy trong đường phản hồi giao thức), lệnh ghi tới qua
    **hook**. Địa chỉ ngoài vùng khai báo cố ý để trống -> master nhận
    `ILLEGAL DATA ADDRESS` thay vì một số 0 trông có vẻ hợp lệ.
  - **Thiết bị đánh địa chỉ bằng TÊN LOGIC** (`modbus.devices.<tên>`), đúng
    khuôn `client_id` của MQTT và `server_id` của gRPC/web.
  - Ba nhóm exception tách riêng vì cách phản ứng khác nhau:
    `ModbusConnectionError` (thử lại được) / `ModbusDeviceError` (thiết bị từ
    chối, thử lại vô ích - kèm diễn giải mã lỗi thành lời) / `ModbusCodecError`.

- **Adapter OPC UA** (`xime/adapters/opcua/`, extra `xime[opcua]`).

  - **Node Model** (`@node_model` + `Node("ns=2;s=Tank.Level")`) - ở đây model
    **không phải để giải mã** (OPC UA đã mang kiểu) mà để **đặt tên** cho
    NodeId. NodeId được kiểm dạng ngay lúc định nghĩa class.
  - **`OpcuaClient`**: `read` / `read_node` / `read_model` / `write` /
    `write_model`. `read_model` gộp mọi node vào **một** request - OPC UA round
    trip có độ trễ thật, đọc lẻ mười node là nhân độ trễ lên mười lần.
  - **`@on_node_change` + `OpcuaAdapter`**: subscription thật, không polling.
    Giá trị đầu tiên chỉ là **mốc** (mặc định `initial=False`) để giống hệt quy
    tắc `@on_change` của Modbus; `deadband` dùng chung một hàm so sánh với
    Modbus nên hai adapter hành xử giống nhau. Handler chạy trong task riêng vì
    `asyncua` giao thông báo qua callback **đồng bộ** - await thẳng trong đó sẽ
    chặn vòng nhận của thư viện.
  - **Bảo mật đủ ba mức** None / Sign / SignAndEncrypt (`Basic256Sha256`).
    Thiếu cert khi chọn Sign/SignAndEncrypt thì **nổ lúc startup**, không âm
    thầm tụt xuống kết nối không bảo vệ. Server đặt ở mức `Sign` vẫn nhận client
    mang `SignAndEncrypt`. Có **`application_uri`** cho cả client lẫn server: ở
    hai mức bảo mật này, server đối chiếu URI client khai lúc mở session với URI
    trong SubjectAltName của cert, mà `asyncua` để mặc định URI của chính nó và
    không tự đọc từ cert - thiếu tuỳ chọn này thì cert tự sinh gần như chắc chắn
    bị từ chối với `BadCertificateUriInvalid`, một thông báo không hề nhắc tới URI.
  - **Kiểu của node phía server suy từ annotation trong model.** Biến OPC UA lấy
    kiểu dữ liệu từ giá trị lúc tạo và về sau không nhận giá trị khác kiểu, nên
    `running: bool = Node(...)` phải tạo ra node kiểu Boolean chứ không phải
    Double. Không suy được kiểu và cũng không có `default=` thì **nổ lúc khởi
    động kèm tên node**, chứ không đoán rồi để lần đẩy đầu tiên chết lặng lẽ
    trong `BadTypeMismatch`.
  - **Chế độ server** (`OpcuaServerAdapter`, `@serve_nodes` / `@on_node_write`):
    cùng cách chia như server Modbus. Node có `@on_node_write` thì **client làm
    chủ giá trị**, vòng refresh không ghi đè - nếu ghi đè thì framework đá nhau
    với người vừa đặt giá trị và mọi thông báo ghi đều mơ hồ.

- **`encode_field(..., allow_read_only=True)`** trong codec Modbus: ở vai
  **slave**, input register và discrete input chính là thứ phải công bố, trong
  khi ở vai client thì tuyệt đối không được ghi. Cờ tường minh thay vì đổi tạm
  thuộc tính của field.

- **Tài liệu**: `docs/{vn,en}/modbus.md` và `docs/{vn,en}/opcua.md`.

### Fixed

Những lỗi dưới đây có từ các bản **đã phát hành** (0.6.3 trở về trước), tìm ra
trong đợt kiểm toán trước khi đẩy PyPI. Mỗi lỗi đều được tái hiện bằng thực
nghiệm trước khi vá, và đều có test canh.

- **Web app không cài extra `[jwt]` sập lúc khởi động** (có từ **0.2.0**, còn
  nguyên ở cả 10 bản đã lên PyPI). `WebAdapter` đọc registry JWT ở **mọi** lần
  khởi động chỉ để xem `configure_jwt()` có được gọi hay không, mà import
  submodule đó lại kéo theo `__init__` của package, vốn `import jwt` ở mức
  module. Hệ quả: `pip install xime[web]` rồi chạy một app **không hề đụng tới
  JWT** vẫn chết với `ModuleNotFoundError: No module named 'jwt'`. PyJWT nay
  được nạp lười (`starters/jwt/_pyjwt.py`); app thật sự gọi `configure_jwt()`
  thì adapter dò PyJWT **ngay lúc khởi động** chứ không đợi request đầu tiên
  mang token.

- **`Application.use()` chỉ chặn được trùng adapter ở ba trong sáu loại.** Chốt
  chặn đọc thuộc tính `_server_id`, mà `MqttAdapter` đặt tên định danh của mình
  là `_client_id` (Modbus/OPC UA mới thêm ở bản này cũng vậy). Đăng ký hai
  adapter cho cùng một `client_id` được chấp nhận im lặng - trong khi broker MQTT
  chỉ cho **một** phiên trên mỗi client id và đá phiên cũ ra, nên hai adapter
  đánh nhau trong vòng lặp reconnect. Cả sáu loại adapter nay đều được chặn.

- **Scheme `Bearer` nay không phân biệt hoa thường** (RFC 7235). Client gửi
  `bearer <token>` từng nhận 401 kèm thông báo "Missing authorization token" -
  nói header không có trong khi nó nằm ngay đó.

- **`__all__` không còn phá `mypy --strict` của người dùng.** Gói ship `py.typed`
  và khai classifier `Typing :: Typed`, nhưng `__all__` bị dùng để điều khiển DI
  scanner nên chính những dòng import mà tài liệu hướng dẫn lại bị báo "does not
  explicitly export attribute". Đã đánh dấu re-export theo chuẩn PEP 484 - cơ
  chế DI **không đổi một chút nào**.

- **Import thiếu extra nay nói rõ phải cài gì.** `xime.adapters.grpc`,
  `xime.starters.sqlalchemy` và `xime.starters.jwt` từng ném
  `ModuleNotFoundError` trần. Riêng `No module named 'jwt'` còn dẫn người dùng
  đi sai đường rất tệ: trên PyPI có một package tên đúng là `jwt`, khác hẳn
  PyJWT, nên `pip install jwt` cài nhầm thư viện rồi hỏng theo cách khó lần ra.

- **Tài liệu nêu API không tồn tại.** Toàn bộ mục JWT trong `docs/*/starters.md`
  mô tả một API khác hẳn thực tế (`JwtConfig`, `JwtSigner`, `JwtVerifier`,
  `configure_jwt_middleware` - không cái nào tồn tại), và bốn chỗ khác trỏ
  `xime.config` / `xime.lifecycle` / `xime.event` / `xime.context` thay vì
  `xime.core.*`. Đã viết lại theo API thật; nay **cả 343 dòng import trong toàn
  bộ tài liệu đều chạy được**, có script kiểm chứng.

- Lỗi lúc đóng socket server không còn bị nuốt im lặng (nay `logger.debug` kèm
  traceback), khớp với cách mọi adapter khác xử lý teardown.

### Changed

- **Tham số constructor có giá trị mặc định nay là tham số KHÔNG bắt buộc.**
  Container đọc mọi annotation là một dependency, nên trước đây một chữ ký hoàn
  toàn bình thường lại không đăng ký nổi:

  ```python
  class ModbusClient:
      def __init__(self, device: str = "default") -> None: ...

  dependency.register(ModbusClient)
  # cũ: UnregisteredDependencyException - Dependency: str
  # mới: OK, device = "default"
  ```

  Không thứ gì trong một DI container cấp `str` bao giờ, mà developer đã tuyên bố
  tham số đó không bắt buộc bằng cách cho nó giá trị mặc định. Tương đương
  `@Autowired(required=false)` của Spring. Áp cho cả tham số của factory method
  trong `dependency.configure(...)`.

  **Fail-fast vẫn nguyên ở chỗ quan trọng:** tham số **không** có mặc định mà
  thiếu implementation thì startup vẫn nổ - đó là đa số áp đảo dependency thật.
  **Đánh đổi đã cân nhắc:** tham số `Protocol` có mặc định mà thiếu binding giờ
  nhận mặc định thay vì nổ.

- **Thứ tự dựng singleton nay xác định giữa các lần chạy.** `DependencyGraph`
  duyệt theo thứ tự khai báo thay vì duyệt `set` của type - thứ tự duyệt `set`
  phụ thuộc `id()` nên đổi theo từng process, khiến thứ tự chạy `post_construct()`
  giữa các singleton **độc lập với nhau** đổi theo từng lần chạy. Order nào cũng
  hợp lệ, nhưng một bug phụ thuộc order sẽ chỉ tái hiện thỉnh thoảng.

- **Hai server adapter (Modbus, OPC UA) nay chặn trên số handler ghi chạy đồng
  thời** (`max_concurrency`, mặc định 16) và **từ chối `refresh <= 0`**. Master
  ghi nhanh hơn handler nói chuyện với database rất nhiều; trước đây mỗi lệnh ghi
  sinh một task không giới hạn. Phía master đã có chặn trên này từ đầu.

- **Extra `[web]` kéo thêm `python-multipart`.** Helper upload file có tài liệu
  (`save_upload`) cần nó, mà FastAPI chỉ đưa gói này vào extra `standard` của
  chính nó - `pip install xime[web]` không có, nên upload chết lúc chạy với
  "Form data requires python-multipart to be installed".

- **Floor dependency nay là con số đã cài thử, không phải phỏng đoán.**
  `fastapi>=0.110.1` (0.110.0 ghim starlette 0.36.3, `TestClient` của nó gọi
  `httpx.Client(app=...)` - đã bị xoá ở httpx 0.28, nên mọi test app tự viết cho
  route của mình đều chết `TypeError`), `pydantic>=2.5` (2.0-2.4 ra trước Python
  3.12, chính là mốc `requires-python` của Xime, nên không interpreter được hỗ
  trợ nào cài nổi), `pyyaml>=6.0.1` (6.0 không build được trên CPython hiện
  đại). Đã chạy **full suite với đúng bộ floor này**.

- **sdist chỉ còn mã nguồn và tài liệu**: 400 file / 620 KB xuống 230 file /
  354 KB. Trước đây gói phát hành nuốt cả `.claude/` (39 file tài liệu chiến
  lược nội bộ + đường dẫn máy cá nhân) và `tests_temp/` (130 file), vì hatchling
  mặc định đóng gói **mọi thứ không bị `.gitignore` che**. Nay khai whitelist
  neo vào gốc dự án, nên thư mục mới thêm vào repo mặc định nằm ngoài gói.

### Notes

Bốn chỗ API của `pymodbus` đã đổi so với thiết kế 2026-06-23, đều đã xác minh
trên `pymodbus 3.14.0` trước khi viết code (chi tiết:
`.claude/docs/ke-hoach-0.7.md`):

- `pymodbus.payload` (`BinaryPayloadDecoder`/`Builder`) **đã bị xóa** - thay
  bằng classmethod `ModbusClientMixin.convert_from_registers/to_registers`. Vì
  là classmethod nên codec **unit-test được hoàn toàn không cần network**.
- Tham số slave nay tên là **`device_id`** (keyword-only).
- `convert_*` chỉ có `word_order`, **không có `byte_order`** - Xime tự cài đặt
  phần hoán byte trong từng thanh ghi (`swap_bytes`).
- `ModbusServerContext`/`ModbusDeviceContext` **đã deprecated, sẽ xóa ở
  pymodbus v4** - phần slave viết thẳng theo `SimData`/`SimDevice` ngay từ đầu.
  `SimDevice.id` map đúng vào `unit_id`.

Với `asyncua`, framework đọc bằng `read_attributes()` chứ **không** dùng
`read_values()`: hàm sau vứt bỏ StatusCode của từng node, nên gõ sai một NodeId
trả về `None` **im lặng**, trông y hệt một node chưa có giá trị.

Floor phiên bản: `pymodbus>=3.14`, `asyncua>=2.0`. Classifier vẫn
`Development Status :: 3 - Alpha` (0.7 còn thêm tính năng lớn).

## [0.6.3] - 2026-07-29

Bản vá tương thích ngược hoàn toàn, tập trung **gỡ chặn cho các app đang chạy
trên platform**. Ba việc chính: **`PEER_APP_ID`** (cert mTLS của tiến trình
thuộc một app nay mang định danh app trong SAN, framework đọc ra và đặt vào
`request_context` để service phía sau phân giải được Subject loại APPLICATION),
**TLS cho web adapter** (platform cố ý không có gateway, không có nó thì app
Python không phục vụ được Internet) và **khối chỉ đọc `read_only()`** (usecase
không ghi thôi phải bọc transaction). Kèm hai điểm hardening ghi nhận từ kiểm
toán 0.6 và vá metadata gói. Test: **1223 passed, 5 skipped** (+98 test so với
0.6.2; skip thứ 5 là ca phân quyền file chỉ chạy trên POSIX).

### Added

- **Khối chỉ đọc `read_only()`** - trước bản này mọi truy cập database, kể cả một
  câu `SELECT`, đều phải nằm trong `async with self.transaction():` vì
  `AsyncSessionFactory.current()` ném `RuntimeError` khi ngoài transaction. Hệ quả
  là service chỉ đọc vẫn phải nhận `TransactionManager`, và `async with
  self.transaction():` xuất hiện dày đến mức không còn mang thông tin gì - nhìn nó
  không biết được chỗ nào thật sự có ghi.
- **`ReadOnlyManager` / `ReadOnlyContext`** (`core/transaction/readonly.py`,
  export ở `xime.core.transaction`) - Protocol cho khối chỉ đọc, **cùng cấp** với
  `TransactionManager` chứ không phải method của nó:

  ```python
  async with self.read_only():
      product = await self.products.find_or_fail(product_id)
  ```

  Tách thành binding riêng để về sau trỏ đường đọc sang **read replica** / mức
  isolation khác / decorator cache chỉ bằng một dòng `bind`, không sửa code
  nghiệp vụ. Là method của `TransactionManager` thì nó dính chặt vào engine của
  đường ghi.
- **`SqlAlchemyReadOnlyManager` / `SqlAlchemyReadOnlyContext`**
  (`starters/sqlalchemy/readonly.py`) - implementation, bind cạnh
  `TransactionManager`. Bốn đặc điểm:
  - **Không bao giờ commit.** Thoát khối là hủy, dù thành công hay lỗi. Nên lỡ
    sửa entity trong khối chỉ đọc thì thay đổi không xuống được database. Framework
    **không báo lỗi** ca này - xem mục Ranh giới bên dưới.
  - **Lồng nhau thì mượn session đang chạy** và thoát ra không làm gì. Nhờ vậy một
    service chỉ đọc ghép được vào usecase có ghi mà không mở connection thứ hai,
    và không đóng nhầm session của transaction bao ngoài.
  - **`expunge_all()` trước `rollback()`** để entity còn dùng được sau khi ra khỏi
    khối. Rollback làm expire mọi object trong session, đọc thuộc tính sau đó sẽ
    ném `DetachedInstanceError` - kiểm chứng bằng cách xóa đúng dòng đó, hai test
    chuyển đỏ. Quan hệ chưa eager-load thì vẫn lỗi, y như async SQLAlchemy thường.
  - **Không gọi `begin()` tường minh**, để SQLAlchemy autobegin: khối không đọc gì
    thì không lấy connection nào khỏi pool (đo bằng `pool.checkedout()` trong test).
  - **Ranh giới đã chốt:** framework **không chặn** việc sửa entity đọc được từ
    khối chỉ đọc - thay đổi bị bỏ đi im lặng, không lỗi, không log. Chặn được thì
    phải hook SQLAlchemy event và trả phí runtime cho mọi lời đọc, trái nguyên tắc
    minimal magic; bù bằng quy tắc tài liệu (entity đọc trong `read_only()` chỉ để
    **trả về hoặc render**, muốn sửa thì mở `transaction()` và **load lại**).
  - **Tương thích ngược:** đường transaction cũ không đổi một dòng nào; chỗ duy
    nhất bị nới là `AsyncSessionFactory.current()` (nay khối chỉ đọc cũng đặt được
    session vào ContextVar), còn `RuntimeError` khi gọi repository ngoài mọi khối
    thì giữ nguyên. App không bind `ReadOnlyManager` chạy y như cũ - có test boot
    `Application` thật cho cả hai trường hợp.
- **`FakeReadOnlyManager`** (`xime.testing`) - bản no-op đối xứng với
  `FakeTransactionManager`, cho test không cần database.

- **TLS/HTTPS cho web adapter** - trước bản này `uvicorn.Config` được dựng không
  tham số ssl nào nên mọi app Xime chỉ chạy HTTP thuần. Kiến trúc platform cố ý
  không có gateway/reverse proxy, mỗi service tự kết thúc TLS.
  - **`ServerTlsConfig`** (`core/config/runtime.py`, export ở `xime.core.config`
    và `xime.adapters.web`) - khối `server.ssl` trong `application.yml`:
    `certfile`, `keyfile`, `keyfile_password`, `ca_certs`, `cert_reqs`,
    `ciphers`. **Để trống = HTTP thuần, hành vi cũ y nguyên.**
  - **`cert_reqs` dùng chữ** (`"none"` / `"optional"` / `"required"`) thay vì số
    `ssl.CERT_*`: operator đọc `cert_reqs: required` trong YAML là hiểu, đọc
    `cert_reqs: 2` thì không. Framework map sang hằng stdlib; sai chính tả bị
    Pydantic từ chối ngay.
  - **Fail-fast khi cấu hình sai.** uvicorn báo lỗi không thể debug cho cert khai
    nửa vời: thiếu `keyfile` ra `SSLError: [SSL] PEM lib`, thiếu `certfile` ra
    `AssertionError` **rỗng message**. Nay `_tls_kwargs()` kiểm trước và ném
    `StartupException` nêu key + đường dẫn + `server_id`: khai một nửa, file
    không tồn tại, không phải file thường, hoặc **tồn tại mà không đọc được**
    (certbot ghi `privkey.pem` chỉ cho root - lỗi hay gặp nhất khi triển khai).
    Không bao giờ im lặng rơi về HTTP: server tưởng HTTPS mà thật ra HTTP là lỗ
    hổng bảo mật.
  - **Chỉ forward option thực sự được cấu hình.** uvicorn đặt mặc định
    `ssl_cert_reqs = CERT_NONE` và `ssl_ciphers` là chuỗi khác rỗng, nên truyền
    `None` không phải "dùng mặc định" mà ghi đè mất (kiểm chứng:
    `ssl_cert_reqs=None` ném `ValueError: None is not a valid VerifyMode`).
  - **Multi-server: `WebAdapter(..., ssl=ServerTlsConfig(...))`**, để trống thì
    **kế thừa `server.ssl`**. Kế thừa là có chủ đích - server phụ âm thầm chạy
    HTTP khi server chính đã HTTPS là lỗ hổng không ai để ý; muốn tắt thì truyền
    `ssl=ServerTlsConfig()` tường minh.
  - Cert phải là cert **CA công cộng** (certbot...). Cert do CA nội bộ Trust cấp
    là để service nhận diện nhau qua mTLS, trình duyệt không tin.
  - Test `tests_temp/web/test_tls.py` (29 pass + 1 skip), gồm một ca **gọi HTTPS
    thật** vào uvicorn đang chạy với client tin đúng cert tự ký. Thiết kế, phần
    đã bỏ và hướng nâng cấp: `.claude/docs/tls-cho-web-adapter.md`.

- **`PEER_APP_ID` - định danh APPLICATION đọc từ SAN của client cert.** Một app
  có nhiều tiến trình, mỗi tiến trình một cert riêng (CN riêng) nhưng chung một
  định danh app; cert mang định danh đó dưới dạng SAN URI `xime-app://<Base62 33
  ký tự>`. Framework nay trích ra và lưu cạnh `PEER_CN`:
  - **`current_app_id()`** (`core/security/peer.py`) - trả định danh app của
    caller hoặc `None`, đối xứng `current_caller()`. Export ở `xime.core.security`
    cùng hằng `PEER_APP_ID`.
  - **`_read_peer_app_id()`** (`adapters/grpc/interceptors/_context.py`) - đọc
    property `x509_subject_alternative_name` của `auth_context()`. Khác CN, SAN
    là property **nhiều giá trị** (cert thường còn mang DNS, IP, spiffe) nên
    duyệt mọi entry, bỏ qua entry không liên quan. Chấp nhận cả URI trần lẫn dạng
    có tiền tố loại (`URI:xime-app://...`) bằng cách tìm chuỗi con thay vì so đầu
    chuỗi. Lưu **phần sau scheme** - đúng dạng platform dùng ở REST path và JWT
    `sub`, consumer không phải tự cắt.
  - **Fail-soft tuyệt đối** như `PEER_CN`: không mTLS, thiếu entry, giá trị không
    decode được UTF-8, hay định danh sai độ dài đều trả `None` chứ không ném. Một
    cert lạ không bao giờ được phép làm hỏng request. Entry hỏng bị bỏ qua chứ
    không che mất entry hợp lệ đứng sau.
  - **Ranh giới giữ nguyên:** framework chỉ cấp sự thật thô, không giải mã Base62,
    không kiểm app có tồn tại, không kiểm quyền - authorization vẫn ở ứng dụng.
  - `_set_peer_cn` đổi tên thành `_set_peer_identity` (hàm nội bộ) và set cả hai
    key trong một chỗ, nên hai đường gọi unary/streaming không phải sửa riêng.
    **Hành vi `PEER_CN` không đổi** - có service đang dựa vào nó.

### Fixed

- **Cờ `xime.di.dynamic-binding` ép kiểu chặt** (B1, ghi nhận khi kiểm toán 0.6).
  Trước đây đọc bằng `bool(runtime.get(...))`, trong khi mọi cờ khác đi qua model
  Pydantic. Hệ quả: operator viết `dynamic-binding: "false"` (chuỗi có nháy trong
  YAML) sẽ **bật nhầm** tính năng, vì `bool("false")` là `True`. Thêm
  **`RuntimeConfig.get_bool(key, default)`** dùng lại chính bộ parse boolean của
  Pydantic (`true/false`, `yes/no`, `on/off`, `1/0`, không phân biệt hoa thường)
  và ném `StartupException` nêu rõ key + giá trị khi gặp thứ không phải boolean -
  cờ sai phải nổ lúc startup, không hành xử tuỳ tiện về sau. `get()` giữ nguyên
  hành vi trả giá trị thô.
- **Metadata gói `pyproject.toml`**: thêm classifier `Typing :: Typed` (repo vẫn
  ship `xime/py.typed` mà chưa khai báo) và chuyển license sang PEP 639
  (`license = "MIT"` + `license-files`, thay dạng bảng `{ file = "LICENSE" }`) để
  PyPI hiện tag license. Kèm `requires = ["hatchling>=1.27"]` vì bản cũ hơn không
  hiểu metadata PEP 639. Wheel dựng thử xác nhận `License-Expression: MIT` +
  `License-File: LICENSE`.

### Documentation

- **Caveat thứ tự `post_construct` của `DynamicProxy`** (B2, ghi nhận khi kiểm
  toán 0.6). Khi bật dynamic binding, consumer phụ thuộc proxy chứ không phụ thuộc
  impl, nên dependency graph không có cạnh consumer -> impl và thứ tự
  `post_construct` giữa hai bên là không xác định. Mọi `post_construct` vẫn chạy
  đủ lúc startup nên request sau đó không ảnh hưởng; rủi ro duy nhất là consumer
  gọi vào impl ngay trong `post_construct` của chính nó. Đã ghi vào docstring kèm
  hướng xử lý (làm lười lúc dùng lần đầu). Không đổi code.
- **Tài liệu transaction viết lại** (`docs/{vn,en}/transaction.md`,
  `.claude/rules/transaction.md`) - mục "API tương lai" trước đây hứa
  `transaction.read_only()`; nay đã hiện thực nhưng **dưới dạng manager riêng cùng
  cấp**, các mục đó được sửa cho khớp và bổ sung phần cảnh báo "đọc ngoài
  transaction thì đừng sửa".

## [0.6.2] - 2026-06-30

Thêm **starter `mail`** - gửi email qua SMTP theo đúng khuôn mẫu starter sẵn có
(`storage`/`cache`): một Protocol `MailService` + backend `SmtpMailService`, app
bind trong `config/dependency.py`. Tương thích ngược hoàn toàn. Test starter:
17 passed.

### Added

- **Starter `mail` (`xime.starters.mail`)** - gửi email bất đồng bộ qua SMTP:
  - **`MailService` (Protocol)** - contract trung lập: `async def send(message:
    EmailMessage) -> None`. Logic đồng bộ (await tới khi gửi xong, thành công ->
    return, thất bại -> raise `MailSendError`, có timeout nội bộ) - dùng cho email
    bảo mật (OTP, reset mật khẩu). Gửi nền là việc của app (tự bọc
    `asyncio.create_task(...)`), starter không ôm hàng đợi.
  - **`SmtpMailService` (backend)** - hiện thực qua **`aiosmtplib`** (async, không
    chặn event loop; extra `xime[mail]`, import lười). Đọc `mail.from` và
    `mail.smtp.*` (`host` bắt buộc -> `ValueError` fail-fast; `port` mặc định 587,
    `timeout` 10s, `use_tls` true) từ `RuntimeConfig`. Mỗi `send()` mở một kết nối
    SMTP mới rồi đóng (bền hơn pool cho lượng email giao dịch/OTP). Tự chọn
    STARTTLS (587) hoặc TLS ngầm (465) theo cổng.
  - **`EmailMessage`** - value object `@dataclass(frozen=True, slots=True)`: `to`,
    `subject`, `html`, `text`, `cc`, `reply_to`, `sender` (override `mail.from`).
    Validate lúc tạo: `to` không rỗng và có ít nhất một trong `html`/`text`. Có cả
    hai -> `multipart/alternative`.
  - **Exception** `MailError` (base) + `MailSendError` (gửi thất bại: SMTP từ
    chối, timeout, mất kết nối; giữ lỗi gốc ở `__cause__`) - mẫu
    `storage._exceptions`.
  - Dùng: `dependency.scan("xime.starters.mail")` +
    `dependency.bind({ MailService: SmtpMailService })`.

### Fixed

Hardening sau kiểm toán toàn diện 0.6.2 (chi tiết: `.claude/docs/kiem-toan-0.6.md`).
Không có lỗi gãy chức năng; toàn bộ là nhất quán / hardening nhỏ. Test: 1125 passed,
4 skipped.

- **`EmailMessage.to`/`cc` thật sự bất biến**: `__post_init__` snapshot sang
  `tuple` nên mutate list gốc của caller không ảnh hưởng message frozen (trước
  đây `frozen=True` chỉ chặn gán lại, không chặn `msg.to.append(...)`).
- **Mail SMTP `username`/`password` dùng `is not None`** thay falsy-check: chuỗi
  rỗng cấu hình tường minh vẫn truyền tới server; chỉ giá trị thật sự vắng mới bỏ
  qua xác thực.
- **Version fallback đồng bộ**: `xime.__version__` fallback `0.6.1` -> `0.6.2`;
  generator SDK gRPC (`_codegen.py`) nay ủy quyền `xime.__version__` để chỉ còn
  một literal version duy nhất (trước trả lệch `"0.5.0"`).
- **Error message middleware marker sang tiếng Anh** cho nhất quán; xóa sentinel
  `_NO_DEFAULT` thừa; bỏ tạo `DynamicProxy` thừa khi interface đã có override.

## [0.6.1] - 2026-06-29

Bản vá nhỏ cho web adapter: middleware tự viết lấy được dependency từ DI container
và runtime config qua marker, nên **app không phải subclass `WebAdapter`** nữa;
thêm helper CORS hạng nhất. Bổ sung `CrudRepository` cho starter SQLAlchemy để app
hết phải tự viết base repository. Tương thích ngược hoàn toàn, không đổi API cũ.
Toàn bộ test: 1101 passed, 4 skipped.

### Added

- **`CrudRepository[T]` (starter SQLAlchemy)** - lớp repository nền generic cho
  sẵn CRUD chung như `JpaRepository`/`CrudRepository` của Spring Data:
  `find` · `find_or_fail` · `find_all` · `exists` · `count` · `save` · `save_all`
  · `delete`. App chỉ cần `class CategoryRepository(CrudRepository[Category]):
  model = Category` rồi viết thêm query đặc thù bằng `select()` - hết lặp lại
  `BaseRepository` ở mỗi dự án. `model` khai báo dạng abstract property nên chính
  `CrudRepository` là abstract (`inspect.isabstract` = True) -> DI scanner bỏ qua
  lớp nền; chỉ subclass concrete (đã set `model`) mới thành singleton, không sinh
  singleton thừa. Mọi method đọc session đang hoạt động qua `AsyncSessionFactory`
  nên phải gọi trong `async with self.transaction():`. `find_or_fail` ném
  `EntityNotFoundError` (lỗi runtime cục bộ của starter) khi không có bản ghi.
- **Middleware lấy dependency từ DI / runtime config (web adapter)** - hai marker
  `Inject(SomeType)` và `FromConfig("a.b", default)` dùng làm giá trị option khi
  gọi `configure_middleware(...)`. Framework phân giải marker lúc `build_app`
  (sau khi DI container đã dựng): `Inject` lấy singleton từ container,
  `FromConfig` đọc `RuntimeConfig` theo dot-notation (thiếu thì về default). Nhờ
  vậy middleware tự viết (vd JWT middleware cần auth/user/blacklist service) khai
  báo gọn trong `config/web.py`, **không phải subclass `WebAdapter`** để tự gọi
  `xime_app.get(...)`. Giá trị không phải marker giữ nguyên (tương thích ngược).
- **`configure_cors(...)`** - helper hạng nhất bật CORS cho web adapter theo
  pattern `configure_*`. Tham số để trống tự đọc từ `RuntimeConfig` khóa
  `cors.<tên>` (qua `FromConfig`), thiếu nốt thì về mặc định Starlette - Operator
  chỉnh CORS qua `application.yml` mà không đụng code. CORS đăng ký như user
  middleware nên nằm ngoài JwtAuth (preflight OPTIONS xử lý trước xác thực).

## [0.6.0] - 2026-06-23

Bản DI: **tự viết lớp lưu/dựng singleton** (gỡ hẳn thư viện `dependency-injector`)
và **dynamic interface binding** (một interface bind nhiều implementation, đổi
được lúc runtime). Không đổi API người dùng đang dùng; dự án cũ chạy nguyên không
phải sửa. Toàn bộ test: 1084 passed, 4 skipped.

### Added

- **Dynamic interface binding** - `bind` nay chấp nhận value là **tuple nhiều
  implementation** (phần tử đầu = mặc định) bên cạnh value một class như cũ.
  Bật/tắt bằng cờ runtime `xime.di.dynamic-binding` trong `application.yml` (mặc
  định **tắt**). Khi tắt, tuple hành xử y hệt bind phần tử đầu (impl phụ không
  dựng) - bằng đúng kiến trúc cũ. Khi bật: mọi impl là singleton eager (chạy
  `PostConstruct`/`PreDestroy`), consumer nhận một **proxy trong suốt**
  (`DynamicProxy`) nên giữ nguyên code, và một **`Switcher`** (inject được) đổi
  implementation **toàn cục** lúc runtime qua `use(Interface, Impl)` /
  `reset(Interface)` / `reset()`. Validate fail-fast: mọi impl trong tuple phải
  thỏa Protocol. `Switcher` luôn inject được; khi cờ tắt, `use/reset` báo lỗi rõ.

### Changed

- **Gỡ phụ thuộc `dependency-injector`** - lớp lưu/dựng singleton ở
  `core/container/registry.py` viết lại bằng dict thuần (key là chính class) +
  `RLock` double-checked locking. API public (`XimeContainer`,
  `DependencyRegistry.register/get`) không đổi. Lý do: Xime eager-build mọi
  singleton lúc startup rồi giữ reference qua constructor injection, không gọi
  provider mỗi request - nên ưu thế Cython của thư viện không phát huy, trong khi
  vẫn tốn phí sinh tên (md5 + regex) mỗi class và một lớp gián tiếp mỗi `get()`.
  Bản tự viết bỏ cả hai: `get()` warm là đúng một `dict.get`, lock chỉ chạm khi
  cache miss (gần như chỉ lúc startup). Benchmark đối chiếu: build ~8x, warm
  `get()` ~2x nhanh hơn backend cũ. Đã gỡ `dependency-injector` khỏi
  `pyproject.toml` - Xime không còn phụ thuộc thư viện DI bên thứ ba nào.
- Bump version `0.5.0` -> `0.6.0`.

## [0.5.0] - 2026-06-22

Bản kiểm toán toàn diện + hai mảng tính năng mới: **adapter MQTT** (messaging/IoT)
và **làm việc với file** (storage starter + streaming web). Toàn bộ test: 1051
passed, 4 skipped (2 skip là test tích hợp MQTT/S3 - chạy khi có broker/MinIO).
Chi tiết kiểm toán: `.claude/docs/kiem-toan-0.5.md`.

### Added

- **Adapter MQTT** (`pip install xime[mqtt]`, `aiomqtt` import lười): pub/sub
  một chiều (`@subscribe`) + **RPC over MQTT v5** (`@rpc`, qua `ResponseTopic` +
  `CorrelationData`). `MqttPublisher` (DI singleton) để publish; auto-reconnect +
  re-subscribe; xử lý message giới hạn đồng thời (`max_concurrency`, backpressure);
  định tuyến bằng **MQTT v5 Subscription Identifier** để filter chồng lấn không
  double-dispatch; teardown `request_context`/`clear_security()` nhất quán mọi adapter.
- **Starter `storage`** (Protocol `StorageService`): hai dạng truy cập song song
  - `put`/`get` (bytes) cho object nhỏ và `put_stream`/`open_stream` (stream) cho
  object lớn; `delete`/`exists`/`stat`/`url`. Value là bytes thô, framework không
  áp đặt định dạng. Key được chuẩn hóa chung (từ chối rỗng/tuyệt đối/`..`) cho mọi
  backend.
- **Backend `localfs`** (`LocalFileStorage`): lưu file dưới `storage.local.root`,
  chống path traversal 3 lớp, ghi nguyên tử (`.part` + `os.replace`), stream qua
  `asyncio.to_thread` (không cần `aiofiles`).
- **Backend `s3`** (`pip install xime[s3]`, `aioboto3` import lười): `S3ClientProvider`
  (vòng đời client ở `post_construct`/`pre_destroy`) + `S3FileStorage` (multipart
  upload, ranged GET, presigned `url()`); tương thích MinIO (`addressing_style`).
- **Streaming file ở web adapter** (`xime.adapters.web.files`): `stream_object`
  (HTTP Range 200/206/416, `Content-Range`, `ETag`, đọc lười không nạp hết RAM) và
  `save_upload` (đọc `UploadFile` theo chunk -> `put_stream`, giới hạn `max_bytes`
  -> 413).
- **JWT `audience`/`issuer`** (`JwtMiddlewareConfig`): ép khớp `aud`/`iss` khi cấu
  hình; middleware phơi toàn bộ claim qua `request_context[JWT_CLAIMS]` để app
  authorize tiếp.

### Fixed

- **Context bleeding ở web HTTP middleware** (dental-clinic #001): chuyển
  `RequestContextMiddleware` và `JwtAuthMiddleware` từ `BaseHTTPMiddleware` sang
  **pure-ASGI middleware** -> set/clear `ContextVar` cùng context với handler, hết
  rò identity giữa các request.
- **JWT từ chối token có claim `aud`**: trước đây `jwt.decode` không truyền
  `audience` khiến PyJWT reject mọi token mang `aud` (401). Nay đặt
  `verify_aud=False` khi chưa cấu hình audience và ép khớp khi có.
- **`MqttPublisher` treo vô hạn** khi không adapter nào phục vụ client_id: nay
  fail-fast `RuntimeError` rõ ràng.
- **HTTP Range sai cú pháp trả 416**: nay bỏ qua header rác và phục vụ full 200
  (đúng RFC 7233); chỉ 416 cho range hợp lệ-nhưng-không-thoả.
- **Scanner nuốt lỗi import thật của submodule**: nay re-raise lỗi import thật
  (thiếu dependency, circular...), chỉ bỏ qua khi module thực sự vắng.
- **`get_protocol_methods` bỏ dunder**: nay giữ dunder mang ý nghĩa contract
  (`__call__`, `__aenter__`, `__aexit__`...) để binding validation đầy đủ hơn.
- **MQTT `#`/`+` cấp đầu khớp `$SYS`**: nay không khớp topic hệ thống `$...`.
- **Socket `STREAM_START` payload hỏng làm rớt connection**: nay gửi frame ERROR.
- **`XimeGrpcChannel` task đóng channel nền có thể bị GC**: nay giữ strong-ref.
- **OpenAPI `public_paths` không chuẩn hóa trailing slash** như JWT middleware:
  nay đồng nhất.
- **MQTT RPC: lỗi gửi reply che lỗi gốc**: nay reply lỗi là best-effort, luôn
  giữ lỗi nghiệp vụ gốc trong log.

### Changed

- **`scheduler` extra**: `apscheduler>=3.6` -> `apscheduler>=4.0.0a6` cho khớp code
  dùng API v4 (`AsyncScheduler`/`run_until_stopped`/`add_schedule`); `>=3.6` cho
  phép cài 3.x stable thiếu API v4 -> `ImportError` lúc chạy.
- Thêm extra `s3`, `mqtt`; gộp vào `all`.
- Bump version `0.4.0` -> `0.5.0`.

## [0.4.0] - 2026-06-20

Bản cross-cutting + starters: thêm danh tính peer mTLS cho gRPC và hai starter
còn thiếu (`cache`, `redis`). Không đụng lõi DI. Toàn bộ test: 929 passed,
2 skipped.

### Added

- **Danh tính peer mTLS cho gRPC -> request_context**: `RequestContextInterceptor`
  nay đọc Common Name của client certificate đã verify (qua `auth_context()`) và
  lưu vào `request_context` dưới key trung tính `peer_cn`. **Fail-soft**: không
  mTLS / không có CN / lỗi đọc -> không set key, request vẫn chạy. Thêm helper
  `current_caller()` (`xime.core.security`) trả CN thô; authorization vẫn ở app.
- **Starter `cache`**: Protocol `CacheService` (`get`/`set`/`delete`/`exists`),
  value là `bytes` thô (framework không áp đặt serialize), TTL theo giây,
  `None` = không hết hạn. Tách hoàn toàn khỏi backend.
- **Starter `redis`** (`pip install xime[redis]`): `RedisClientProvider` (đọc
  `redis.url` + `redis.max_connections` từ `application.yml`, `pre_destroy` đóng
  connection pool) và `RedisCacheService` (implement `CacheService`). `redis`
  được import lười để module vẫn import được khi chưa cài extra.

### Changed

- Bump version `0.3.0` -> `0.4.0`.

## [0.3.0] - 2026-06-19

Bản hardening: vá bug đã xác nhận, tăng an toàn mặc định và khép kín mảng gRPC
client. Không thêm tính năng lớn. Toàn bộ test: 899 passed, 2 skipped.

### Added

- **Retry policy cho gRPC client (`grpc.clients.<id>.retry`)**: `GrpcRetryConfig`
  với `enabled` / `max_attempts` / `initial_backoff_ms` / `max_backoff_ms` /
  `backoff_multiplier` / `retryable_status`. Tắt mặc định; chỉ retry call UNARY
  (stream không replay được an toàn); mặc định chỉ retry `UNAVAILABLE`; backoff
  mũ có cap; mỗi lần thử có deadline riêng.
- **`tls.server_id` cho gRPC client**: chọn certificate provider theo `server_id`
  trong thiết lập multi-server (mặc định `"default"`).

### Fixed

- **gRPC client cert rotation không thread-safe** (backlog #7): thêm
  `threading.Lock` quanh đoạn check-and-replace trong
  `XimeGrpcChannel._dynamic_channel()` để hai luồng song song không cùng dựng
  channel rồi rò một cái.
- **`wire_dynamic_certificates()` hardcode `server_id="default"`** (backlog #8):
  giờ tra provider theo `server_id` của từng channel.
- **Endpoint gRPC code-first viết `def` thay vì `async def`** (backlog #9): nay
  fail fast bằng `StartupException` lúc startup (kể cả `async def` có `yield`),
  thay vì crash `TypeError` lúc RPC đầu tiên.
- **Interceptor lỗi gRPC abort hai lần** (notification/data note #2): re-raise
  `grpc.aio.AbortError` như terminal để không abort lần hai khi interceptor/
  handler bên trong đã abort.
- **Interceptor lỗi để lộ `str(exc)` ra client** (notification/data note #1a):
  lỗi chưa map nay trả message chung `"Internal server error"`; lỗi đã map vẫn
  giữ message có chủ đích.

### Changed

- Bump version `0.2.0` -> `0.3.0`.

## [0.2.0] - 2026-06-14

Bản hoàn thiện đầu tiên: core (DI / lifecycle / config / context / event bus /
security / transaction), các adapter (web, gRPC code-first + client SDK + mTLS
động, socket) và các starter (sqlalchemy, jwt, scheduler).

[0.6.1]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/nguyen-huu-thang/xime-framework/releases/tag/v0.2.0
