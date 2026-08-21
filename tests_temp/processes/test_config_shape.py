"""Một hình dạng cấu hình, hai cách viết: `process:` và `processes:`.

> **`process:` là một khối. `processes:` là nhiều khối có tên. Bên trong hai cái
> giống hệt nhau.**

Đi từ một tiến trình sang nhiều: đổi `process:` thành `processes:`, thụt vào một
cấp, đặt tên, nhân bản khối, thêm `shared` ở cổng muốn dùng chung, và đổi `run()`
thành `share_load().run()`. Không sửa lại gì bên trong.
"""

from __future__ import annotations

import pytest

from xime.core.bootstrap._processes import (
    SINGLE_PROCESS_ID,
    build_topology,
    parse_single,
)
from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException


def _read(raw: dict):
    return RuntimeConfig.from_dict(raw).get


WEB = [("web", "default")]


class TestTheSingleProcessBlock:
    def test_one_process_can_open_two_web_ports(self):
        """Đúng mô hình chốt: lặp `use(WebAdapter(...))` là hai server web, và
        chuyện đó **không liên quan gì** tới số tiến trình."""
        topo = build_topology(
            _read(
                {
                    "process": {
                        "web": {
                            "public": {"host": "0.0.0.0", "port": 8086},
                            "admin": {"host": "127.0.0.1", "port": 8081},
                        }
                    }
                }
            ),
            [("web", "public"), ("web", "admin")],
            share_load=False,
        )

        block = topo.by_id(SINGLE_PROCESS_ID)
        assert block.spec_for("web", "public").port == 8086
        assert block.spec_for("web", "admin").port == 8081
        assert block.spec_for("web", "admin").host == "127.0.0.1"

    def test_the_inner_shape_is_identical_to_a_processes_block(self):
        """⭐ Phép đo của câu *"bên trong hai cái giống hệt nhau"*.

        Nếu hai hình dạng lệch nhau dù chỉ một khoá thì việc đi từ một sang
        nhiều thôi không còn là *thêm một cấp*, và người đọc phải học hai thứ.
        """
        inner = {"web": {"d": {"host": "127.0.0.1", "port": 8086}}}

        single = build_topology(_read({"process": inner}), [("web", "d")], share_load=False)
        multi = build_topology(
            _read({"processes": {"main": {"primary": True, **inner}}}),
            [("web", "d")],
            share_load=True,
        )

        one = single.blocks[0].spec_for("web", "d")
        many = multi.blocks[0].spec_for("web", "d")
        assert (one.host, one.port, one.options) == (many.host, many.port, many.options)

    def test_the_single_block_is_implicitly_primary(self):
        """Nên adapter hạng đơn nhất (scheduler) vẫn chạy ở app một tiến trình."""
        topo = parse_single({"web": {"d": {"port": 1}}})
        assert topo.blocks[0].primary is True
        assert topo.primary_id == SINGLE_PROCESS_ID


class TestKeysThatMeanNothingWithOneProcess:
    """*"Chỗ nào không dùng thì bỏ đi"* - và framework **bắt lỗi**, không bỏ qua.

    Một khoá bị bỏ qua im lặng là chỗ để người ta tin vào thứ không xảy ra.
    """

    def test_primary_is_refused(self):
        with pytest.raises(StartupException, match="primary In A Single-Process") as exc:
            parse_single({"primary": True, "web": {"d": {"port": 1}}})
        assert "always the primary" in str(exc.value)

    def test_count_is_refused(self):
        with pytest.raises(StartupException, match="count In A Single-Process"):
            parse_single({"count": 3, "web": {"d": {"port": 1}}})

    def test_shared_is_refused(self):
        """Đúng câu chủ dự án nêu: muốn trùng cổng thì phải **từ hai tiến trình
        trở lên**, và trùng ở đúng vị trí `use` mang id đó."""
        with pytest.raises(StartupException, match="shared In A Single-Process") as exc:
            parse_single({"web": {"d": {"port": 1, "shared": True}}})
        assert "at least two processes" in str(exc.value)

    def test_shared_false_is_refused_too(self):
        """Vế đối chứng: kiểm **sự có mặt của khoá**, không kiểm giá trị.

        `shared: false` cũng vô nghĩa ở đây, và cho nó qua là dạy người đọc rằng
        khoá đó có ý nghĩa - rồi họ đổi thành `true` và ngạc nhiên.
        """
        with pytest.raises(StartupException, match="shared In A Single-Process"):
            parse_single({"web": {"d": {"port": 1, "shared": False}}})


class TestTheOneLetterTrap:
    """`process` và `processes` khác nhau **đúng một ký tự**.

    Bốn tổ hợp, và không tổ hợp nào được chạy êm mà sai.
    """

    def test_processes_without_share_load_is_refused(self):
        with pytest.raises(StartupException, match="Without share_load") as exc:
            build_topology(
                _read({"processes": {"main": {"primary": True, "web": {"d": {"port": 1}}}}}),
                WEB,
                share_load=False,
            )
        assert "`process:`" in str(exc.value)

    def test_process_with_share_load_is_refused(self):
        with pytest.raises(StartupException, match="Without A processes Block") as exc:
            build_topology(
                _read({"process": {"web": {"d": {"port": 1}}}}), WEB, share_load=True
            )
        assert "rename it" in str(exc.value)

    def test_declaring_both_is_refused(self):
        with pytest.raises(StartupException, match="Both process And processes"):
            build_topology(
                _read({"process": {}, "processes": {"main": {}}}), WEB, share_load=False
            )

    def test_each_spelling_works_with_its_own_branch(self):
        """Vế đối chứng của ba test trên - không có nó thì cách sửa sai *"luôn
        nổ"* cũng qua được cả ba."""
        build_topology(_read({"process": {"web": {"default": {"port": 1}}}}), WEB, share_load=False)
        build_topology(
            _read({"processes": {"m": {"primary": True, "web": {"default": {"port": 1}}}}}),
            WEB,
            share_load=True,
        )


class TestTheFlatKeysStillWork:
    """58/69 file cấu hình trong workspace dùng `server:`, nên đây là hiện thực
    đông nhất - và nó **không phải một nhánh xử lý thứ hai**.

    ⭐ Dịch xong thì từ đó trở đi chỉ còn một đường code, và khoá phẳng **không
    thể trôi lệch** vì nó chỉ diễn tả nổi một điểm phục vụ mỗi loại.
    """

    def test_server_port_becomes_the_default_web_cell(self):
        topo = build_topology(
            _read({"server": {"host": "0.0.0.0", "port": 8086}}), WEB, share_load=False
        )
        spec = topo.blocks[0].spec_for("web", "default")
        assert (spec.host, spec.port) == ("0.0.0.0", 8086)

    def test_server_ssl_comes_along(self):
        topo = build_topology(
            _read({"server": {"port": 1, "ssl": {"certfile": "/c.pem"}}}),
            WEB,
            share_load=False,
        )
        assert topo.blocks[0].spec_for("web", "default").options["ssl"] == {
            "certfile": "/c.pem"
        }

    def test_grpc_port_becomes_the_default_grpc_cell(self):
        topo = build_topology(
            _read({"grpc": {"port": 9095}}), [("grpc", "default")], share_load=False
        )
        assert topo.blocks[0].spec_for("grpc", "default").port == 9095

    def test_no_config_at_all_still_produces_a_cell(self):
        """App chưa có `application.yml` vẫn khởi động được - adapter tự dùng
        mặc định của nó, y như trước 0.8."""
        topo = build_topology(_read({}), WEB, share_load=False)
        assert topo.blocks[0].spec_for("web", "default") is not None

    def test_a_second_web_endpoint_needs_the_process_block(self):
        """Khoá phẳng chỉ diễn tả nổi MỘT điểm phục vụ, nên điểm thứ hai không
        có chỗ nào lấy địa chỉ. Nói ra, kèm đúng khuôn phải viết."""
        with pytest.raises(StartupException, match="Needs The process Block") as exc:
            build_topology(_read({"server": {"port": 1}}), [("web", "admin")], share_load=False)
        assert "process:" in str(exc.value)

    def test_an_outbound_adapter_keeps_its_own_id(self):
        """Vế đối chứng: luật *"chỉ id `default`"* chỉ áp cho adapter **mang địa
        chỉ**. `ModbusAdapter("inverter_1")` tra khối YAML của chính nó, và điều
        đó đã chạy từ 0.7."""
        topo = build_topology(
            _read({"modbus": {"devices": {"inverter_1": {"host": "10.0.0.1"}}}}),
            [("modbus", "inverter_1")],
            share_load=False,
        )
        assert topo.blocks[0].spec_for("modbus", "inverter_1") is not None
