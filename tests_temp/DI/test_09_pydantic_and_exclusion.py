"""Two rules about what may enter DI, and the line between them.

RULE 1 - a Pydantic model never enters DI, not even inside a scanned package.
Its constructor is ``def __init__(self, **data: Any)``. Constructor injection
matches dependencies BY PARAMETER NAME, and ``**data`` has no name to match, so
there is nowhere to plug a wire in. That is structural, not a convention.

RULE 2 - a ``@dataclass`` DOES enter DI, and that is deliberate. ``@dataclass``
generates ``__init__(self, repo: Repo)``, which is exactly constructor
injection written another way. The framework can tell dataclasses apart
(``dataclasses.is_dataclass``) and chooses not to, because DI's boundary is
"can it be built", not "what did the author mean" - and because excluding them
would fail SILENTLY: a service written as a dataclass would vanish from DI
without a word, whereas a misplaced data dataclass fails loudly at startup with
its own name in the message.

The tests come in PAIRS on purpose. A patch that skips "anything awkward" would
pass the must-be-skipped half alone; only the must-still-fail half pins the line
where it belongs.

RULE 3 - the exclusion list is a DEFAULT, overridable per app, and "never
declared" must stay distinguishable from "declared empty".
"""
import sys
import types
from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from xime.core.bootstrap.orchestrator import StartupOrchestrator
from xime.core.config.binding import BindingConfig
from xime.core.config.runtime import RuntimeConfig
from xime.core.container import XimeContainer
from xime.core.container.scanner import PackageScanner
from xime.core.exception import UnregisteredDependencyException
from xime.core.metadata.type_utils import is_pydantic_model

NL = chr(10)


def _lam_package(ten: str, *classes: type) -> str:
    """Dựng một package giả trong sys.modules rồi gắn class vào nó."""
    pkg = types.ModuleType(ten)
    pkg.__path__ = []
    pkg.__package__ = ten
    sys.modules[ten] = pkg
    for cls in classes:
        cls.__module__ = ten
        setattr(pkg, cls.__name__, cls)
    return ten


class Repo:
    def __init__(self) -> None:
        self.n = 0


class TestPydanticModelKhongVaoDI:

    def test_model_co_field_bat_buoc_bi_bo_qua(self):
        class TaoPhongRequest(BaseModel):
            ten: str
            gia: int

        pkg = _lam_package("t09_pydantic_bat_buoc", TaoPhongRequest)
        assert TaoPhongRequest not in PackageScanner().scan(pkg)

    def test_model_toan_field_mac_dinh_cung_bi_bo_qua(self):
        """Dựng được không phải là lý do để vào DI - nó vẫn không nhận được dependency."""
        class CauHinhGoi(BaseModel):
            trial_days: int = 14

        pkg = _lam_package("t09_pydantic_mac_dinh", CauHinhGoi)
        assert CauHinhGoi not in PackageScanner().scan(pkg)

    def test_khoi_dong_xong_khi_dto_nam_trong_package_duoc_quet(self):
        """Đây là ca thật đã làm chết startup ở nhiều app: DTO để cạnh controller."""
        class PhongRequest(BaseModel):
            ten: str

        class PhongService:
            def __init__(self, repo: Repo) -> None:
                self.repo = repo

        pkg = _lam_package("t09_dau_cuoi", PhongRequest, PhongService, Repo)
        c = XimeContainer().scan(pkg).build()
        c.get_all_in_order()
        assert isinstance(c.get(PhongService).repo, Repo)

    def test_is_pydantic_model_nhan_ca_lop_con(self):
        class Cha(BaseModel):
            x: int = 0

        class Con(Cha):
            pass

        assert is_pydantic_model(Cha) is True
        assert is_pydantic_model(Con) is True
        assert is_pydantic_model(Repo) is False


class TestDataclassVanVaoDI:
    """Nửa còn lại của cặp. Thiếu lớp này thì "bỏ qua mọi thứ khó" cũng xanh."""

    def test_dataclass_lam_service_van_duoc_dang_ky_va_inject(self):
        @dataclass
        class PhongService:
            repo: Repo

        pkg = _lam_package("t09_dataclass_service", PhongService, Repo)
        c = XimeContainer().scan(pkg).build()
        assert isinstance(c.get(PhongService).repo, Repo)

    def test_dataclass_du_lieu_thuan_VAN_no_lon(self):
        """Nổ lúc khởi động kèm tên class là hành vi ĐÚNG - đừng "sửa" nó."""
        @dataclass
        class KetQuaPhong:
            ten: str

        pkg = _lam_package("t09_dataclass_du_lieu", KetQuaPhong)
        with pytest.raises(UnregisteredDependencyException):
            XimeContainer().scan(pkg).build()


class TestGhiDeDanhSachLoaiTru:

    def test_mac_dinh_van_loai_sau_doan(self):
        class DomainService:
            def __init__(self) -> None:
                pass

        pkg = _lam_package("t09_mac_dinh.domain.model", DomainService)
        goc = _lam_package("t09_mac_dinh_goc")
        sys.modules[goc].__path__ = []
        assert PackageScanner()._is_excluded_module(pkg) is True

    def test_khai_danh_sach_rieng_THAY_THE_mac_dinh(self):
        s = PackageScanner(frozenset(["legacy"]))
        assert s._is_excluded_module("app.legacy.thing") is True
        assert s._is_excluded_module("app.domain.thing") is False

    def test_khai_RONG_thi_khong_loai_gi(self):
        s = PackageScanner(frozenset())
        assert s._is_excluded_module("app.domain.thing") is False
        assert s._is_excluded_module("app.dto.thing") is False

    def test_khong_khai_KHAC_khai_rong(self):
        """Đối chứng của luật 03: hai trạng thái phải cho hai kết quả khác nhau."""
        khong_khai = PackageScanner(None)
        khai_rong = PackageScanner(frozenset())
        assert khong_khai._is_excluded_module("app.domain.x") is True
        assert khai_rong._is_excluded_module("app.domain.x") is False


class TestBindingConfigChoBietAppDaKHAI_HAY_CHUA:

    def test_chua_khai_thi_la_None(self):
        assert BindingConfig().excluded_segments is None

    def test_khai_rong_KHAC_chua_khai(self):
        b = BindingConfig()
        b.exclude_segments()
        assert b.excluded_segments == ()
        assert b.excluded_segments is not None

    def test_goi_lan_sau_thay_the_lan_truoc(self):
        b = BindingConfig()
        b.exclude_segments("a")
        b.exclude_segments("b", "c")
        assert b.excluded_segments == ("b", "c")


class TestContainerNoiDenTanScanner:
    """Canh CHỖ NỐI, không canh hàm.

    Ba lớp trên chứng minh PackageScanner cư xử đúng khi ĐƯỢC TRUYỀN danh sách.
    Lớp này chứng minh danh sách thật sự ĐI TỚI nó: gỡ đường dây trong
    XimeContainer.build() hoặc trong orchestrator ra thì lớp này đỏ, còn ba lớp
    kia vẫn xanh. Cùng cái bẫy đã cắn repo này ở đợt uvloop 0.8.1.

    Phải dùng package THẬT trên đĩa: bộ lọc chỉ chạy khi duyệt module CON, mà
    package giả trong sys.modules có __path__ rỗng nên không có module con nào.
    """

    @staticmethod
    def _dung_cay(tmp_path, ten: str):
        MA_DOMAIN = (
            "class DomainService:" + NL
            + "    def __init__(self) -> None:" + NL
            + "        self.n = 0" + NL
        )
        MA_APP = (
            "class AppService:" + NL
            + "    def __init__(self) -> None:" + NL
            + "        self.n = 0" + NL
        )
        goc = tmp_path / ten
        (goc / "domain").mkdir(parents=True)
        (goc / "__init__.py").write_text("", encoding="utf-8")
        (goc / "domain" / "__init__.py").write_text("", encoding="utf-8")
        (goc / "domain" / "thing.py").write_text(MA_DOMAIN, encoding="utf-8")
        (goc / "service.py").write_text(MA_APP, encoding="utf-8")
        sys.path.insert(0, str(tmp_path))
        return ten

    @staticmethod
    def _don(ten: str):
        sys.path.pop(0)
        for m in [k for k in sys.modules if k == ten or k.startswith(ten + ".")]:
            del sys.modules[m]

    def _ten_class(self, container) -> set[str]:
        return {type(o).__name__ for o in container.get_all_in_order()}

    def test_mac_dinh_thi_domain_bi_loai(self, tmp_path):
        ten = self._dung_cay(tmp_path, "t09_day_a")
        try:
            found = self._ten_class(XimeContainer().scan(ten).build())
            assert "AppService" in found
            assert "DomainService" not in found
        finally:
            self._don(ten)

    def test_khai_RONG_thi_domain_duoc_quet(self, tmp_path):
        """Đây là dòng chứng minh exclude_segments() đi hết đường tới scanner."""
        ten = self._dung_cay(tmp_path, "t09_day_b")
        try:
            found = self._ten_class(
                XimeContainer().scan(ten).exclude_segments().build()
            )
            assert "AppService" in found
            assert "DomainService" in found
        finally:
            self._don(ten)

    def test_khai_doan_khac_thi_domain_het_bi_loai(self, tmp_path):
        ten = self._dung_cay(tmp_path, "t09_day_c")
        try:
            found = self._ten_class(
                XimeContainer().scan(ten).exclude_segments("legacy").build()
            )
            assert "DomainService" in found
        finally:
            self._don(ten)


class TestOrchestratorChuyenTiepDungHaiTrangThai:
    """Mắt xích CUỐI: BindingConfig -> StartupOrchestrator -> XimeContainer.

    ⚠ Bản đầu của lớp này CHÉP LẠI nhánh `if ... is not None` rồi kiểm bản chép.
    Nó xanh, và xoá nhánh thật trong orchestrator.py thì nó VẪN xanh - đúng cái
    bẫy "canh hàm chứ không canh việc hàm được gọi" đã cắn repo này ở đợt uvloop
    0.8.1. Nay nó chạy StartupOrchestrator thật.

    Ba ca vì có ba trạng thái, không phải hai: chưa khai phải IM (gọi vô điều
    kiện thì `None` thành "không loại gì", và mọi app bỗng quét cả domain/ mà
    không có gì báo), khai rỗng phải MỞ HẾT, khai có tên phải thay thế.
    """

    @staticmethod
    def _ten_class(orch) -> set[str]:
        return {type(o).__name__ for o in orch._container.get_all_in_order()}

    async def _chay(self, tmp_path, ten, khai):
        goc = tmp_path / ten
        (goc / "domain").mkdir(parents=True)
        (goc / "__init__.py").write_text("", encoding="utf-8")
        (goc / "domain" / "__init__.py").write_text("", encoding="utf-8")
        (goc / "domain" / "thing.py").write_text(
            "class DomainService:" + NL
            + "    def __init__(self) -> None:" + NL
            + "        self.n = 0" + NL,
            encoding="utf-8",
        )
        (goc / "service.py").write_text(
            "class AppService:" + NL
            + "    def __init__(self) -> None:" + NL
            + "        self.n = 0" + NL,
            encoding="utf-8",
        )
        sys.path.insert(0, str(tmp_path))
        try:
            b = BindingConfig()
            b.scan(ten)
            if khai is not None:
                b.exclude_segments(*khai)
            orch = StartupOrchestrator(b, RuntimeConfig())
            await orch.start()
            try:
                return self._ten_class(orch)
            finally:
                await orch.stop()
        finally:
            sys.path.pop(0)
            for m in [k for k in sys.modules if k == ten or k.startswith(ten + ".")]:
                del sys.modules[m]

    @pytest.mark.asyncio
    async def test_chua_khai_thi_giu_mac_dinh(self, tmp_path):
        found = await self._chay(tmp_path, "t09_orch_a", khai=None)
        assert "AppService" in found
        assert "DomainService" not in found

    @pytest.mark.asyncio
    async def test_khai_RONG_thi_quet_ca_domain(self, tmp_path):
        found = await self._chay(tmp_path, "t09_orch_b", khai=())
        assert "DomainService" in found

    @pytest.mark.asyncio
    async def test_khai_doan_khac_thi_domain_het_bi_loai(self, tmp_path):
        found = await self._chay(tmp_path, "t09_orch_c", khai=("legacy",))
        assert "DomainService" in found
