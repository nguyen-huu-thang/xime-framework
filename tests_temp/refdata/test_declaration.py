"""Khai một bảng: tham số class, và cái gì xảy ra khi khai sai.

⭐ Cấu hình đi bằng **tham số class** (PEP 487) chứ không phải thuộc tính trong
thân class, để cấu hình không bao giờ nằm chung không gian tên với thứ ứng dụng
thêm vào. Cùng quy ước đã chốt cho `Store`.
"""

from __future__ import annotations

import pytest

from xime.core.exception.framework import StartupException
from xime.core.refdata import (
    DEFAULT_MAX_BYTES,
    RefData,
    configure_refdata,
    refdata_registry,
    specs_of,
)

from .refdata_sample.tables import AppRegistryRefData, JwtKeyRefData


class TestClassParameters:
    def test_name_and_max_bytes_land_on_the_class(self) -> None:
        assert JwtKeyRefData.name == "jwt-keys"
        assert JwtKeyRefData.max_bytes == 4096

    def test_max_bytes_has_a_default(self) -> None:
        class WithoutSize(RefData, name="no-size"):
            pass

        assert WithoutSize.max_bytes == DEFAULT_MAX_BYTES

    def test_configuration_never_collides_with_the_class_body(self) -> None:
        # Đây là toàn bộ lý do dùng tham số class: `name` đi vào
        # `__init_subclass__`, không bao giờ thành một thuộc tính do app khai,
        # nên app không thể vô tình đè lên nó.
        class WithBody(RefData, name="with-body", max_bytes=128):
            limit = 99
            keys: list[str] = []

        assert WithBody.name == "with-body"
        assert WithBody.limit == 99


class TestForgettingTheName:
    """Quên khai `name` thì class **không vào DI được**, chứ không chạy vô danh."""

    def test_a_class_without_a_name_stays_abstract(self) -> None:
        class Forgot(RefData):
            pass

        assert Forgot.__abstractmethods__

    def test_an_intermediate_base_may_omit_the_name_on_purpose(self) -> None:
        # Cùng cơ chế, và đó là điểm hay của nó: một lớp nền dùng chung của ứng
        # dụng không khai tên thì vẫn abstract, y như một bảng thật sự quên.
        class AppBase(RefData[dict]):
            def decode(self, raw: memoryview) -> dict:
                return {}

        class Concrete(AppBase, name="concrete"):
            pass

        assert AppBase.__abstractmethods__
        assert not Concrete.__abstractmethods__
        assert Concrete.name == "concrete"


class TestInvalidDeclarations:
    @pytest.mark.parametrize("bad", ["", "-leading", "co dau cach", "a" * 65])
    def test_a_name_that_cannot_be_a_shared_memory_name_is_rejected(
        self, bad: str
    ) -> None:
        with pytest.raises(ValueError, match="Invalid RefData Name"):

            class Bad(RefData, name=bad):
                pass

    @pytest.mark.parametrize("bad", [0, -1, True, 1.5, "4096"])
    def test_a_max_bytes_that_is_not_a_positive_int_is_rejected(
        self, bad: object
    ) -> None:
        with pytest.raises(ValueError, match="Invalid RefData max_bytes"):

            class Bad(RefData, name="ok-name", max_bytes=bad):  # type: ignore[arg-type]
                pass


class TestConfigureRefdata:
    def test_it_records_the_declared_classes(self) -> None:
        configure_refdata([JwtKeyRefData, AppRegistryRefData])
        assert refdata_registry.classes() == (JwtKeyRefData, AppRegistryRefData)

    def test_calling_twice_REPLACES_instead_of_appending(self) -> None:
        # Cùng hành vi với mọi `configure_*` khác. Cộng dồn thì một test chạy
        # sau kế thừa bảng của test chạy trước, và lỗi đó chỉ hiện ra theo thứ
        # tự chạy.
        configure_refdata([JwtKeyRefData])
        configure_refdata([AppRegistryRefData])
        assert refdata_registry.classes() == (AppRegistryRefData,)

    def test_an_instance_is_rejected_with_the_reason(self) -> None:
        with pytest.raises(StartupException, match="Not A RefData Class"):
            configure_refdata([object()])  # type: ignore[list-item]

    def test_a_class_that_forgot_its_name_is_rejected_HERE(self) -> None:
        # Bắt ở đây để thông báo nói đúng chỗ sai, thay vì một lỗi "cannot
        # instantiate abstract class" ở giữa lượt dựng container - xa chỗ sai
        # thật cả về stack trace lẫn về thời điểm.
        class Forgot(RefData):
            pass

        with pytest.raises(StartupException, match="Without A Name"):
            configure_refdata([Forgot])


class TestSpecs:
    def test_specs_are_read_off_the_CLASS_not_an_instance(self) -> None:
        # Cha không dựng DI, nên nó chỉ có class trong tay. Đó là lý do `name`
        # và `max_bytes` phải là tham số class chứ không phải thứ tính ra trong
        # `__init__`.
        specs = specs_of((JwtKeyRefData, AppRegistryRefData))
        assert [(s.name, s.max_bytes) for s in specs] == [
            ("jwt-keys", 4096),
            ("app-registry", 2048),
        ]

    def test_two_classes_claiming_one_table_at_two_sizes_is_rejected(self) -> None:
        class First(RefData, name="dup", max_bytes=128):
            pass

        class Second(RefData, name="dup", max_bytes=256):
            pass

        with pytest.raises(ValueError, match="different sizes"):
            specs_of((First, Second))
