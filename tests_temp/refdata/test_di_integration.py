"""Đi ĐÚNG con đường tài liệu hướng dẫn, không phải con đường tiện nhất cho test.

⭐ Mọi test khác trong thư mục này dựng `RefDataArena.create(...)` rồi
`JwtKeyRefData(arena)` bằng tay - nhanh và gọn, nhưng **không tiến trình thật
nào làm vậy**. Người dùng thật gọi `configure_refdata([...])` rồi để
`Application` mở vùng nhớ và DI dựng bảng, và đó là con đường module này đo.

Bài học 0.7.0: ba lỗi mức Cao của bản đó đều nằm ở CHỖ NỐI, và 1427 test cũ
không bắt được cái nào vì test luôn đi đường tắt mà người dùng không có. Cùng
khuôn đã cắn lại ở giai đoạn 1 của 0.8: 128 test dựng đối tượng bằng tay đều
xanh, và test đầu tiên đi qua DI thật đỏ cả 12.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xime.core.bootstrap import Application
from xime.core.config import BindingConfig
from xime.core.refdata import RefData, RefDataArena, configure_refdata

from .refdata_sample.tables import (
    AppRegistryRefData,
    JwtKeyRefData,
    KeySet,
    RawRefData,
)
from .refdata_sample.usecase import KeyLookupFailed, VerifyTokenUseCase

pytestmark = pytest.mark.asyncio

# Mọi bảng mà `scan` sẽ gặp trong package mẫu. Thiếu một cái là startup nổ,
# và đó là hành vi ĐÚNG: một bảng không được khai thì không có vùng nhớ, nên
# nó không chạy được - `TestForgettingToConfigure` đo chính chỗ đó.
_ALL = [JwtKeyRefData, AppRegistryRefData, RawRefData]


def _binding() -> BindingConfig:
    cfg = BindingConfig()
    # Đúng dòng tài liệu bảo viết trong config/dependency.py
    cfg.scan("tests_temp.refdata.refdata_sample")
    return cfg


@pytest.fixture
def resources(tmp_path: Path) -> str:
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir()
    (resources_dir / "application.yml").write_text("app:\n  name: refdata-test\n", "utf-8")
    return str(resources_dir)


class TestThroughRealDI:
    async def test_a_table_is_injected_with_its_own_type(self, resources: str) -> None:
        configure_refdata(_ALL)
        async with Application(
            binding=_binding(), resources_dir=resources
        ) as app:
            table = app.get(JwtKeyRefData)
            assert isinstance(table, JwtKeyRefData)
            # Có generic nên IDE và mypy biết `read()` trả gì - `snapshots.get
            # ("jwt-keys")` kiểu chuỗi thua hẳn ở điểm này.
            assert table.read() is None

    async def test_a_use_case_reaches_the_table_it_declared(
        self, resources: str
    ) -> None:
        configure_refdata(_ALL)
        async with Application(
            binding=_binding(), resources_dir=resources
        ) as app:
            use_case = app.get(VerifyTokenUseCase)
            with pytest.raises(KeyLookupFailed):
                use_case.public_key("k1")
            await use_case.rotate(KeySet({"k1": "pem-1"}))
            assert use_case.public_key("k1") == "pem-1"

    async def test_a_single_process_app_is_its_own_primary(
        self, resources: str
    ) -> None:
        # Không `share_load()` thì đúng một tiến trình, và nó publish được -
        # nếu không thì mọi app hiện tại mất khả năng dùng RefData.
        configure_refdata(_ALL)
        async with Application(
            binding=_binding(), resources_dir=resources
        ) as app:
            arena = app.get(RefDataArena)
            assert arena.primary is True

    async def test_two_tables_get_two_separate_blocks(self, resources: str) -> None:
        # *"Các bảng nên không liên quan gì đến nhau, kể cả bộ nhớ"* - publish
        # một bảng không được chạm một byte nào của bảng kia.
        configure_refdata(_ALL)
        async with Application(
            binding=_binding(), resources_dir=resources
        ) as app:
            keys = app.get(JwtKeyRefData)
            apps = app.get(AppRegistryRefData)
            await keys.publish(KeySet({"a": "1"}))
            assert apps.read() is None
            assert keys.generation == 1 and apps.generation == 0

    async def test_shutdown_releases_the_shared_memory(self, resources: str) -> None:
        # `SharedMemory.close()` ném `BufferError` khi còn một lát cắt chưa
        # thả, nên đây không phải chuyện dọn dẹp cho đẹp: quên là tắt máy nổ.
        configure_refdata(_ALL)
        app = Application(binding=_binding(), resources_dir=resources)
        await app.start()
        table = app.get(JwtKeyRefData)
        await table.publish(KeySet({"a": "1"}))
        table.read()
        await app.stop()  # không được ném

    async def test_restarting_the_same_application_works(
        self, resources: str
    ) -> None:
        # Khuôn *"test xanh lần đầu, đỏ lần thứ hai"* đã cắn thật ở giai đoạn 4
        # với adapter do framework tự đăng ký. Arena bám vào vùng nhớ đã đóng
        # thì cùng hình dạng lỗi đó.
        configure_refdata(_ALL)
        app = Application(binding=_binding(), resources_dir=resources)
        for _ in range(2):
            await app.start()
            assert app.get(JwtKeyRefData).read() is None
            await app.stop()


class TestWithoutScanning:
    """`configure_refdata()` một mình đã đủ đưa bảng vào DI.

    ⭐ Mọi test trên đều `scan` cả package mẫu, nên chúng **không phân biệt
    được** đường nào đưa bảng vào container. Con đường tài liệu hướng dẫn là
    `configure_refdata`, và một ứng dụng hoàn toàn có thể để bảng ở một package
    nó không quét - lúc đó chỉ còn đúng một đường.
    """

    async def test_a_declared_table_reaches_DI_even_with_an_empty_scan(
        self, resources: str
    ) -> None:
        configure_refdata(_ALL)
        async with Application(
            binding=BindingConfig(), resources_dir=resources
        ) as app:
            assert isinstance(app.get(JwtKeyRefData), JwtKeyRefData)
            assert isinstance(app.get(AppRegistryRefData), AppRegistryRefData)

    async def test_scanning_the_same_table_twice_is_harmless(
        self, resources: str
    ) -> None:
        # Cặp với test trên: bảng được đăng ký HAI lần (một do
        # `configure_refdata`, một do `scan` gặp cùng class). Container gộp lại
        # thành một singleton, và đây là chỗ canh cho điều đó.
        configure_refdata(_ALL)
        async with Application(
            binding=_binding(), resources_dir=resources
        ) as app:
            assert app.get(JwtKeyRefData) is app.get(JwtKeyRefData)


class TestForgettingToConfigure:
    async def test_a_scanned_table_without_configure_refdata_fails_AT_STARTUP(
        self, resources: str
    ) -> None:
        # ⭐ Nó nổ với câu chỉ đúng chỗ sai, không phải với
        # "Unregistered Dependency: RefDataArena". Đó là lý do arena vẫn được
        # đăng ký khi không khai bảng nào: một arena RỖNG biết nói.
        cfg = BindingConfig()
        cfg.scan("tests_temp.refdata.refdata_sample")
        app = Application(binding=cfg, resources_dir=resources)
        with pytest.raises(KeyError, match="configure_refdata"):
            await app.start()
        await app.stop()

    async def test_declaring_it_makes_the_same_application_start(
        self, resources: str
    ) -> None:
        # Cặp với test trên: chỉ có vế "phải nổ" thì cách sửa sai *"luôn nổ"*
        # cũng qua được.
        configure_refdata(_ALL)
        async with Application(
            binding=_binding(), resources_dir=resources
        ) as app:
            assert isinstance(app.get(JwtKeyRefData), RefData)
