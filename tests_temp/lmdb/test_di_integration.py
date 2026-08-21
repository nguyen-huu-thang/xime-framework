"""Đi ĐÚNG con đường tài liệu hướng dẫn, không phải con đường tiện nhất cho test.

⭐ Mọi test khác trong thư mục này tự dựng `LmdbEnvironment(runtime)` rồi
`MyTable(env)` bằng tay - nhanh và gọn, nhưng **không tiến trình thật nào làm
vậy**. Người dùng thật khai `dependency.scan(...)` rồi để DI dựng, và đó là con
đường bộ test này đo.

Bài học 0.7.0: ba lỗi mức Cao của bản đó đều nằm ở CHỖ NỐI, và 1427 test cũ
không bắt được cái nào vì test luôn đi đường tắt mà người dùng không có. Một
trong ba là `dependency.register(ModbusClient)` chết ngay tại dòng lệnh mà tài
liệu bảo gõ.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xime.core.bootstrap import Application
from xime.core.config import BindingConfig
from xime.starters.lmdb import LmdbEnvironment, store_registry

from .store_sample.tables import LoginRateLimit, WebhookDedup
from .store_sample.usecase import (
    InvalidCredentials,
    LoginUseCase,
    TooManyFailures,
    WebhookUseCase,
)

pytestmark = pytest.mark.asyncio


def _binding() -> BindingConfig:
    cfg = BindingConfig()
    # Đúng hai dòng tài liệu bảo viết trong config/dependency.py
    cfg.scan("xime.starters.lmdb")
    cfg.scan("tests_temp.lmdb.store_sample")
    return cfg


@pytest.fixture
def resources(tmp_path: Path) -> str:
    """Một thư mục resources thật với application.yml thật."""
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir()
    store_path = (tmp_path / "store").as_posix()
    (resources_dir / "application.yml").write_text(
        "lmdb:\n"
        f"  path: {store_path}\n"
        "  map_size: 1MB\n"
        "  total_max: 32MB\n",
        encoding="utf-8",
    )
    return str(resources_dir)


@pytest.fixture(autouse=True)
def _clean_registry():
    yield
    store_registry.reset()


class TestWiring:
    async def test_di_builds_the_environment_and_every_table(self, resources: str):
        async with Application(binding=_binding(), resources_dir=resources) as app:
            assert isinstance(app.get(LmdbEnvironment), LmdbEnvironment)
            assert isinstance(app.get(LoginRateLimit), LoginRateLimit)
            assert isinstance(app.get(WebhookDedup), WebhookDedup)

    async def test_every_table_shares_one_environment(self, resources: str):
        """Một tiến trình mở mỗi file đúng một lần, dù có bao nhiêu bảng.

        Nếu mỗi bảng tự mở environment riêng thì hai bảng cùng file sẽ giữ hai
        bản đồ khác nhau, và trần `total_max` đếm sai.
        """
        async with Application(binding=_binding(), resources_dir=resources) as app:
            env = app.get(LmdbEnvironment)
            assert app.get(LoginRateLimit)._env is env
            assert app.get(WebhookDedup)._env is env

    async def test_a_table_is_a_singleton(self, resources: str):
        async with Application(binding=_binding(), resources_dir=resources) as app:
            assert app.get(LoginRateLimit) is app.get(LoginRateLimit)

    async def test_use_cases_receive_their_table_by_injection(self, resources: str):
        async with Application(binding=_binding(), resources_dir=resources) as app:
            usecase = app.get(LoginUseCase)
            assert isinstance(usecase, LoginUseCase)
            assert usecase._rate_limit is app.get(LoginRateLimit)

    async def test_nothing_opens_a_file_before_the_first_use(
        self, resources: str, tmp_path: Path
    ):
        """Luật 2.7: dựng DI không được chiếm tài nguyên - mở phải LƯỜI.

        Bốn tiến trình mở bốn bộ file cho những bảng ba phần tư trong số đó
        không bao giờ dùng là lãng phí im lặng, và không ai thấy cho tới lúc
        đếm file.
        """
        async with Application(binding=_binding(), resources_dir=resources) as app:
            env = app.get(LmdbEnvironment)
            assert env.allocated_bytes() == 0
            assert not (tmp_path / "store").exists()

            await app.get(WebhookDedup).get("k")  # lần dùng đầu tiên
            assert env.allocated_bytes() > 0


class TestEndToEnd:
    async def test_rate_limit_locks_out_after_the_threshold(self, resources: str):
        async with Application(binding=_binding(), resources_dir=resources) as app:
            login = app.get(LoginUseCase)

            for _ in range(3):
                with pytest.raises(InvalidCredentials):
                    await login.login("thang", "1.2.3.4", "sai")

            with pytest.raises(TooManyFailures):
                await login.login("thang", "1.2.3.4", "dung-mat-khau")

    async def test_a_successful_login_clears_the_counter(self, resources: str):
        """Vế đối chứng: hãm nhịp phải MỞ RA được, không chỉ đóng lại."""
        async with Application(binding=_binding(), resources_dir=resources) as app:
            login = app.get(LoginUseCase)

            with pytest.raises(InvalidCredentials):
                await login.login("hoa", "5.6.7.8", "sai")
            assert await login.login("hoa", "5.6.7.8", "dung-mat-khau") == "hoa"

            for _ in range(3):
                with pytest.raises(InvalidCredentials):
                    await login.login("hoa", "5.6.7.8", "sai")
            with pytest.raises(TooManyFailures):
                await login.login("hoa", "5.6.7.8", "sai")

    async def test_the_lockout_is_per_key_not_global(self, resources: str):
        async with Application(binding=_binding(), resources_dir=resources) as app:
            login = app.get(LoginUseCase)

            for _ in range(3):
                with pytest.raises(InvalidCredentials):
                    await login.login("thang", "1.2.3.4", "sai")

            # Cùng tài khoản, IP khác -> khoá riêng
            assert await login.login("thang", "9.9.9.9", "dung-mat-khau") == "thang"

    async def test_a_repeated_webhook_is_handled_once(self, resources: str):
        async with Application(binding=_binding(), resources_dir=resources) as app:
            hook = app.get(WebhookUseCase)

            assert await hook.handle("evt-1") is True
            assert await hook.handle("evt-1") is False
            assert await hook.handle("evt-2") is True
            assert hook.handled == ["evt-1", "evt-2"]


class TestShutdown:
    async def test_stopping_the_application_closes_every_file(self, resources: str):
        app = Application(binding=_binding(), resources_dir=resources)
        await app.start()
        env = app.get(LmdbEnvironment)
        await app.get(WebhookDedup).set("k", b"v")
        assert env.allocated_bytes() > 0

        await app.stop()

        assert env.allocated_bytes() == 0

    async def test_data_survives_a_restart_of_the_application(self, resources: str):
        """Kho cố ý sống qua lần restart app - cache còn ấm sau mỗi lần deploy.

        ⚠ Ngược với bus, thứ xoá vùng nhớ khi tắt. Hai quyết định ngược nhau,
        mỗi cái đúng với bản chất của mình.
        """
        async with Application(binding=_binding(), resources_dir=resources) as app:
            await app.get(WebhookDedup).set("evt-1", b"da-xu-ly")

        store_registry.reset()

        async with Application(binding=_binding(), resources_dir=resources) as app:
            assert await app.get(WebhookDedup).get("evt-1") == b"da-xu-ly"


class TestMisconfiguration:
    async def test_a_missing_path_stops_startup(self, tmp_path: Path):
        """Thiếu `lmdb.path` phải nổ lúc KHỞI ĐỘNG, không phải lúc request đầu tiên."""
        resources_dir = tmp_path / "resources"
        resources_dir.mkdir()
        (resources_dir / "application.yml").write_text("env: test\n", encoding="utf-8")

        from xime.core.exception.framework import StartupException

        with pytest.raises(StartupException, match="Missing LMDB Store Path"):
            async with Application(binding=_binding(), resources_dir=str(resources_dir)):
                pass
