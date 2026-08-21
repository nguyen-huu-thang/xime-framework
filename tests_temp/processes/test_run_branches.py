"""`add_config()`, `share_load()`, và ba nhánh của `run()`.

Năm ca của nhánh supervisor cũng nằm ở đây - ba trong năm là *nổ với một câu chỉ
đường*, và chúng chỉ có giá trị nếu câu chỉ đường thật sự xuất hiện.
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest

from xime.core.bootstrap._processes import PROCESS_ID_ENV
from xime.core.bootstrap._supervisor import main_attribute_of
from xime.core.bootstrap.adapter import SCALING_REPLICATED, Adapter
from xime.core.bootstrap.application import Application
from xime.core.config.binding import BindingConfig
from xime.core.exception.framework import StartupException


def _config_module(name: str = "fake_config") -> types.ModuleType:
    module = types.ModuleType(name)
    module.dependency = BindingConfig()
    return module


def _resources(tmp_path: Path, body: str) -> str:
    directory = tmp_path / "resources"
    directory.mkdir(exist_ok=True)
    (directory / "application.yml").write_text(body, encoding="utf-8")
    return str(directory)


class Fake(Adapter, scaling=SCALING_REPLICATED):
    adapter_kind = "web"
    share_port_by = "inherit"

    def __init__(self, server_id: str = "default") -> None:
        self.adapter_id = server_id
        self.slot = None

    def assign_slot(self, slot) -> None:
        self.slot = slot

    async def start(self, app) -> None:  # pragma: no cover - không chạy
        ...

    async def serve(self) -> None:  # pragma: no cover - không chạy
        ...

    async def stop(self) -> None:  # pragma: no cover - không chạy
        ...


# ---------------------------------------------------------------------------
# add_config
# ---------------------------------------------------------------------------


class TestAddConfig:
    def test_a_module_with_dependency_becomes_the_binding(self):
        module = _config_module()
        app = Application(resources_dir="nonexistent")

        assert app.add_config(module) is app
        assert app._binding is module.dependency

    def test_a_string_is_refused_with_the_right_shape_in_the_message(self):
        """Gõ tên module vào là lỗi hay gặp nhất, nên thông báo phải chỉ đường."""
        app = Application(resources_dir="nonexistent")

        with pytest.raises(StartupException, match="Expects A Module") as exc:
            app.add_config("app.config")

        assert "import config" in str(exc.value)

    def test_a_module_without_dependency_is_refused(self):
        app = Application(resources_dir="nonexistent")

        with pytest.raises(StartupException, match="Has No dependency"):
            app.add_config(types.ModuleType("empty"))

    def test_a_non_binding_dependency_is_refused(self):
        module = types.ModuleType("wrong")
        module.dependency = "not a BindingConfig"
        app = Application(resources_dir="nonexistent")

        with pytest.raises(StartupException, match="Has No dependency"):
            app.add_config(module)


# ---------------------------------------------------------------------------
# Nhánh 1: không gọi share_load() - 31 app hiện tại
# ---------------------------------------------------------------------------


class TestSingleProcessBranchIsUntouched:
    def test_no_processes_block_and_no_share_load_runs_the_old_path(
        self, tmp_path, monkeypatch
    ):
        app = Application(resources_dir=_resources(tmp_path, "server:\n  port: 8080\n"))
        called: list[str] = []
        monkeypatch.setattr(
            "asyncio.run", lambda coro, **_: (coro.close(), called.append("asyncio.run"))
        )

        app.run()

        assert called == ["asyncio.run"]

    def test_a_processes_block_without_share_load_is_an_error(self, tmp_path):
        """Sửa nhầm nhánh thì không gì báo, và người vận hành ngồi sửa một khối
        không ai đọc."""
        app = Application(
            resources_dir=_resources(
                tmp_path, "processes:\n  main:\n    primary: true\n"
            )
        )

        with pytest.raises(StartupException, match="Without share_load"):
            app.run()


# ---------------------------------------------------------------------------
# Năm ca của nhánh supervisor
# ---------------------------------------------------------------------------


class TestSupervisorCases:
    def test_case_3_share_load_without_any_adapter_is_an_error(self, tmp_path):
        """Im lặng sinh bốn tiến trình cùng ngủ vô hạn là thứ tốn cả buổi để
        hiểu, và không ca dùng thật nào biện minh cho nó."""
        app = Application(
            resources_dir=_resources(
                tmp_path, "processes:\n  main:\n    primary: true\n"
            )
        )
        app.add_config(_config_module())

        with pytest.raises(StartupException, match="Without Any Adapter"):
            app.share_load().run()

    def test_case_4_share_load_without_a_processes_block_is_an_error(self, tmp_path):
        """Khai *chia tải đi* mà không nói *chia thế nào*: một tiến trình? hai?
        mấy cổng? Không mặc định nào đoán được."""
        app = Application(resources_dir=_resources(tmp_path, "server:\n  port: 1\n"))
        app.add_config(_config_module())
        app.use(Fake())

        with pytest.raises(StartupException, match="Without A processes Block"):
            app.share_load().run()

    def test_share_load_without_add_config_is_an_error(self, tmp_path):
        """Con không tự dò được package config, nên nó sẽ khởi động với DI rỗng
        và không route nào, **im lặng**."""
        app = Application(
            resources_dir=_resources(
                tmp_path,
                "processes:\n  main:\n    primary: true\n    web:\n"
                "      default: { port: 8086 }\n",
            )
        )
        app.use(Fake())

        with pytest.raises(StartupException, match="Requires add_config"):
            app.share_load().run()

    def test_case_5_one_block_still_builds_a_supervisor(self, tmp_path, monkeypatch):
        """Không tự bỏ supervisor khi chỉ có một con.

        Phương án ngược có một cách hỏng cụ thể: hạ `count` từ 4 xuống 1 lúc gỡ
        lỗi thì app **mất khả năng tự dựng lại khi chết** và không gì báo. Muốn
        một tiến trình không có cha thì đã có đường rẻ hơn: đừng gọi
        `share_load()`.
        """
        app = Application(
            resources_dir=_resources(
                tmp_path,
                "processes:\n  main:\n    primary: true\n    web:\n"
                "      default: { port: 8086 }\n",
            )
        )
        app.add_config(_config_module())
        app.use(Fake())

        seen: list[tuple] = []
        monkeypatch.setattr(
            "xime.core.bootstrap._supervisor.run_supervisor",
            lambda a, topo, adapters: seen.append((topo.ids, list(adapters))),
        )
        monkeypatch.delenv(PROCESS_ID_ENV, raising=False)

        app.share_load().run()

        assert seen and seen[0][0] == ("main",)

    def test_case_2_adapters_that_bind_nothing_still_get_a_supervisor(
        self, tmp_path, monkeypatch
    ):
        """Ca DỄ hơn ca 1, không phải khó hơn: bỏ hẳn truyền fd và `SO_REUSEPORT`.

        Nó không phải giả thuyết - chuyển `SchedulerRunner` thành adapter đơn
        nhất (giai đoạn 6) sinh ra đúng hình dạng này.
        """

        class Outbound(Fake):
            adapter_kind = "mqtt"
            share_port_by = "none"

        app = Application(
            resources_dir=_resources(
                tmp_path,
                "processes:\n  main:\n    primary: true\n    mqtt:\n"
                "      nha-may: { client_id: xime-1 }\n",
            )
        )
        app.add_config(_config_module())
        app.use(Outbound("nha-may"))

        seen: list = []
        monkeypatch.setattr(
            "xime.core.bootstrap._supervisor.run_supervisor",
            lambda a, topo, adapters: seen.append(topo.ids),
        )
        monkeypatch.delenv(PROCESS_ID_ENV, raising=False)

        app.share_load().run()

        assert seen == [("main",)]


# ---------------------------------------------------------------------------
# Nhánh 3: worker
# ---------------------------------------------------------------------------


class TestWorkerBranch:
    def test_the_env_var_selects_the_worker_branch(self, tmp_path, monkeypatch):
        """Chạy tay một tiến trình để gỡ lỗi là một đường vào hợp lệ:

            XIME_PROCESS_ID=api-2 python -m app.main
        """
        app = Application(
            resources_dir=_resources(
                tmp_path,
                "processes:\n"
                "  main:\n    primary: true\n    web: { default: { port: 8086 } }\n"
                "  api-2:\n    web: { default: { port: 8087 } }\n",
            )
        )
        app.add_config(_config_module())
        adapter = Fake()
        app.use(adapter)

        monkeypatch.setenv(PROCESS_ID_ENV, "api-2")
        monkeypatch.setattr("asyncio.run", lambda coro, **_: coro.close())

        app.share_load().run()

        assert adapter.slot is not None
        assert adapter.slot.process_id == "api-2"
        assert adapter.slot.spec.port == 8087
        assert adapter.slot.primary is False
        assert adapter.slot.sock is None

    def test_a_typo_in_the_env_var_is_an_error(self, tmp_path, monkeypatch):
        app = Application(
            resources_dir=_resources(
                tmp_path,
                "processes:\n  main:\n    primary: true\n"
                "    web: { default: { port: 8086 } }\n",
            )
        )
        app.add_config(_config_module())
        app.use(Fake())

        monkeypatch.setenv(PROCESS_ID_ENV, "mian")

        with pytest.raises(StartupException, match="Unknown Process Id"):
            app.share_load().run()

    def test_the_worker_runs_the_startup_checks_too(self, tmp_path, monkeypatch):
        """Một phép kiểm chỉ chạy ở một trong hai đường vào là một phép kiểm sẽ
        vắng mặt đúng lúc người ta cần nó nhất - ở đây không có cha nào kiểm hộ."""
        app = Application(
            resources_dir=_resources(
                tmp_path,
                "processes:\n  main:\n    primary: true\n"
                "    web: { publik: { port: 8086 } }\n",
            )
        )
        app.add_config(_config_module())
        app.use(Fake("public"))

        monkeypatch.setenv(PROCESS_ID_ENV, "main")

        with pytest.raises(StartupException, match="Unknown Endpoint"):
            app.share_load().run()


# ---------------------------------------------------------------------------
# Cấm đối số cổng
# ---------------------------------------------------------------------------


# ⛔ Lớp `TestPortInCodeIsRefused` ĐÃ XOÁ ở 0.8.
#
# Nó canh chốt chặn *"truyền cổng trong code thì nổ"*, mà chốt đó nay là **mã
# chết**: đối số `host`/`port`/`ssl`/`path` không còn tồn tại, nên Python từ chối
# sẵn ở tầng chữ ký. Đó chính là cái được của *"làm lại một lần cho tử tế"* -
# thứ thay thế nằm ở `tests_temp/multi_server/test_multi_server.py`
# (`TestAdaptersNoLongerTakeAnAddress`), và nó kiểm **chữ ký**, không kiểm một
# thông báo lỗi.


class TestTheCanonicalMainShape:
    """Khuôn `main.py` chốt ở mục 5.1 của thiết kế, với **adapter thật**.

        app.use(WebAdapter()).use(GrpcAdapter("internal")).use(GrpcAdapter("external"))

    ⚠ Hình dạng này **không dựng nổi trước 0.8**: `GrpcAdapter("internal")` ném
    `ValueError` ngay ở constructor vì thiếu cổng. Đó là lý do phép kiểm đó
    chuyển xuống `start()` - `share_load()` được gọi SAU `use()`, nên lúc dựng
    object không ai biết cổng sẽ tới từ đối số hay từ khối `processes:`.
    """

    def test_three_servers_take_their_ports_from_the_processes_block(
        self, tmp_path, monkeypatch
    ):
        from xime.adapters.grpc import GrpcAdapter
        from xime.adapters.web import WebAdapter

        app = Application(
            resources_dir=_resources(
                tmp_path,
                "processes:\n"
                "  main:\n"
                "    primary: true\n"
                "    web:  { default:  { host: 0.0.0.0,   port: 8086, shared: true } }\n"
                "    grpc:\n"
                "      internal: { host: 127.0.0.1, port: 9095 }\n"
                "      external: { host: 0.0.0.0,   port: 9096 }\n",
            )
        )
        app.add_config(_config_module())
        web = WebAdapter()
        internal = GrpcAdapter("internal")
        external = GrpcAdapter("external")
        app.use(web).use(internal).use(external)

        monkeypatch.setenv(PROCESS_ID_ENV, "main")
        monkeypatch.setattr("asyncio.run", lambda coro, **_: coro.close())

        app.share_load().run()

        assert web._slot.spec.port == 8086
        assert web._slot.spec.shared is True
        assert internal._slot.spec.port == 9095
        assert internal._slot.spec.host == "127.0.0.1"
        assert external._slot.spec.port == 9096
        assert external._slot.spec.host == "0.0.0.0"


# ---------------------------------------------------------------------------
# Tìm biến giữ Application trong __main__
# ---------------------------------------------------------------------------


class TestMainAttribute:
    def test_the_module_level_name_is_found(self, monkeypatch):
        app = Application(resources_dir="nonexistent")
        fake_main = types.ModuleType("__main__")
        fake_main.app = app
        monkeypatch.setitem(__import__("sys").modules, "__main__", fake_main)

        assert main_attribute_of(app) == "app"

    def test_an_application_hidden_inside_a_function_is_an_error(self, monkeypatch):
        """⭐ Phép kiểm này cưỡng chế đúng thứ mô hình đòi: `app`, `add_config()`
        và `use()` phải ở **mức module**, vì con chạy lại `main.py`.

        Đặt chúng trong `if __name__` thì con có một app không adapter nào và DI
        rỗng - cách hỏng đó không có triệu chứng, ở đây nó thành một dòng chữ.
        """
        app = Application(resources_dir="nonexistent")
        fake_main = types.ModuleType("__main__")
        monkeypatch.setitem(__import__("sys").modules, "__main__", fake_main)

        with pytest.raises(StartupException, match="Not A Module-Level Variable"):
            main_attribute_of(app)

    def test_two_applications_do_not_get_mixed_up(self, monkeypatch):
        """Tìm bằng danh tính (`is`), không bằng kiểu."""
        first = Application(resources_dir="nonexistent")
        second = Application(resources_dir="nonexistent")
        fake_main = types.ModuleType("__main__")
        fake_main.first_app = first
        fake_main.second_app = second
        monkeypatch.setitem(__import__("sys").modules, "__main__", fake_main)

        assert main_attribute_of(second) == "second_app"
