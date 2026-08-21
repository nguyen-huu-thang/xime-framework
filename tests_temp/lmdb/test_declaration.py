"""Cách khai một bảng: tham số class, và những thứ phải nổ lúc khai.

Bộ test này canh cơ chế PEP 487 + ABC làm nền cho toàn bộ starter: lớp nền
abstract nên DI scanner bỏ qua, subclass khai `name` thành concrete nên được
đăng ký, và quên khai `name` thì KHÔNG vào DI - nổ lúc khởi động chứ không âm
thầm chạy với một bảng không tên.
"""

from __future__ import annotations

import inspect

import pytest

from xime.core.container.scanner import PackageScanner
from xime.starters.lmdb import NEVER, CounterStore, Store, StoreError
from xime.starters.lmdb._store import DEFAULT_TTL


class TestClassParameters:
    def test_declares_name_ttl_and_parts(self):
        class Sample(Store, name="sample", ttl=900, parts=4):
            pass

        assert Sample.name == "sample"
        assert Sample.ttl == 900
        assert Sample.parts == 4

    def test_ttl_defaults_to_one_hour_and_parts_to_one(self):
        class Sample(Store, name="sample-defaults"):
            pass

        assert Sample.ttl == DEFAULT_TTL == 3600
        assert Sample.parts == 1

    def test_never_is_accepted_as_a_ttl(self):
        class Sample(Store, name="sample-never", ttl=NEVER):
            pass

        assert Sample.ttl == NEVER

    def test_counter_store_carries_the_int_type_so_subclasses_need_no_brackets(self):
        """`CounterStore` là `Store[int]`, nên bảng đếm không phải viết ngoặc.

        Đây là lý do tách lớp nền theo kiểu thay vì bắt mọi bảng viết
        `Store[int]`: kiểu nằm trong TÊN lớp nền nên `get()` khai thẳng
        `int | None`.
        """
        assert CounterStore.__orig_bases__ == (Store[int],)

        class Hits(CounterStore, name="hits"):
            pass

        assert Hits.ttl == DEFAULT_TTL

    def test_configuration_never_becomes_a_body_attribute(self):
        """Cấu hình đi bằng tham số class nên nó KHÔNG nằm trong thân class.

        Đây là lý do chọn PEP 487 thay vì thuộc tính trần: thân class chỉ còn
        docstring và hành vi, nên thứ app viết thêm không thể va tên với cấu
        hình của framework.
        """

        class Sample(Store, name="sample-body", ttl=120):
            pass

        assert "name" not in Sample.__dict__ or Sample.__dict__["name"] == "sample-body"
        assert "ttl" not in vars(Sample) or vars(Sample)["ttl"] == 120


class TestAbstractness:
    """Cặp test: lớp nền phải abstract, subclass khai tên phải concrete."""

    def test_base_classes_are_abstract(self):
        assert inspect.isabstract(Store)
        assert inspect.isabstract(CounterStore)

    def test_subclass_with_a_name_is_concrete(self):
        class Sample(Store, name="concrete"):
            pass

        assert not inspect.isabstract(Sample)

    def test_subclass_without_a_name_stays_abstract(self):
        """Quên khai `name` thì class KHÔNG vào DI.

        Vế còn lại của cặp trên. Không có nó thì một cách sửa sai kiểu "luôn
        gán name mặc định" cũng qua được test, và một bảng không tên sẽ chạy im
        lặng.
        """

        class Forgotten(Store):
            pass

        assert inspect.isabstract(Forgotten)

    def test_intermediate_base_without_a_name_stays_abstract(self):
        """Lớp trung gian dùng chung của app cũng được phép không khai tên."""

        class AppBase(Store):
            def encode(self, value):  # noqa: ANN001, ANN201
                return b""

        class Real(AppBase, name="real"):
            pass

        assert inspect.isabstract(AppBase)
        assert not inspect.isabstract(Real)


class TestScannerVisibility:
    """Cặp test ở tầng DI thật, không phải chỉ inspect.isabstract."""

    def test_scanner_skips_the_base_classes(self):
        found = PackageScanner().scan("xime.starters.lmdb")
        names = {cls.__name__ for cls in found}
        assert "Store" not in names
        assert "CounterStore" not in names

    def test_scanner_registers_the_environment_and_cleanup_job(self):
        found = PackageScanner().scan("xime.starters.lmdb")
        names = {cls.__name__ for cls in found}
        assert "LmdbEnvironment" in names
        assert "StoreCleanupJob" in names

    def test_scanner_registers_NOTHING_else(self):
        """⚠ `__all__` của một starter là danh sách DI, không chỉ là danh sách export.

        Ca thật, đo 2026-08-20: `LmdbConfig` từng nằm trong `__all__` và nó là
        dataclass có trường đầu `path: str`, nên container đi tìm binding cho
        `str` và MỌI app scan starter này chết lúc khởi động với
        "Unregistered Dependency: str".

        Cùng hình dạng với phát hiện C2 của kiểm toán 0.7.0
        (`dependency.register(ModbusClient)` chết đúng tại dòng lệnh tài liệu
        bảo gõ), và nó chỉ lộ ra ở test đi qua DI THẬT - mọi test dựng đối tượng
        bằng tay đều xanh.
        """
        found = PackageScanner().scan("xime.starters.lmdb")
        assert {cls.__name__ for cls in found} == {"LmdbEnvironment", "StoreCleanupJob"}

    def test_the_classes_kept_out_of_all_are_still_importable(self):
        """Vế đối chứng: không đăng ký KHÁC với không export được.

        Không có vế này thì một cách sửa sai kiểu "xoá luôn import" cũng qua
        được test trên, và người dùng mất đường bắt ngoại lệ của kho.
        """
        from xime.starters.lmdb import (  # noqa: F401
            LmdbConfig,
            StoreError,
            StoreFullError,
            StoreUnavailableError,
        )


class TestValidation:
    @pytest.mark.parametrize("bad", ["", "../escape", "a/b", ".hidden", "has space"])
    def test_rejects_a_name_that_could_escape_the_store_root(self, bad):
        with pytest.raises(StoreError, match="Invalid Store Name"):
            type("Bad", (Store,), {}, name=bad)

    @pytest.mark.parametrize("good", ["a", "rate-limit", "rate_limit", "v1.cache", "A9"])
    def test_accepts_ordinary_table_names(self, good):
        cls = type("Good", (Store,), {}, name=good)
        assert cls.name == good

    @pytest.mark.parametrize("bad", [0, -1, "900", True, None])
    def test_rejects_a_ttl_that_is_not_a_positive_number(self, bad):
        with pytest.raises(StoreError, match="Invalid Store TTL"):
            type("Bad", (Store,), {}, name="bad-ttl", ttl=bad)

    @pytest.mark.parametrize("bad", [0, -3, 1.5, "4", True])
    def test_rejects_a_partition_count_below_one(self, bad):
        with pytest.raises(StoreError, match="Invalid Store Partition Count"):
            type("Bad", (Store,), {}, name="bad-parts", parts=bad)
