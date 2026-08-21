"""Khối `processes:` - đọc, bung `count`, và bốn phép kiểm lúc khởi động.

Phần này thuần hàm: không tiến trình, không socket, không adapter. Phần cần biết
`main.py` khai gì nằm ở `test_validation.py`.
"""

from __future__ import annotations

import pytest

from xime.core.bootstrap._processes import parse_topology
from xime.core.exception.framework import StartupException


def _one(**endpoints: dict) -> dict:
    """Một khối primary tối thiểu."""
    return {"main": {"primary": True, **endpoints}}


class TestShape:
    def test_a_single_block_parses_into_one_process(self):
        topo = parse_topology(_one(web={"default": {"port": 8086}}))

        assert topo.ids == ("main",)
        assert topo.primary_id == "main"
        spec = topo.by_id("main").spec_for("web", "default")
        assert spec.port == 8086
        assert spec.shared is False
        assert spec.listens is True

    def test_the_raw_yaml_block_reaches_the_adapter_untouched(self):
        """Framework tìm đúng ô; adapter hiểu ô đó.

        Nên mọi khoá lạ (thứ chỉ adapter đó biết) phải đi qua nguyên vẹn - đó là
        điều kiện để không phải sửa core mỗi lần một adapter thêm một khoá.
        """
        topo = parse_topology(
            _one(web={"default": {"port": 8086, "backlog": 99, "whatever": "x"}})
        )

        options = topo.by_id("main").spec_for("web", "default").options
        assert options["backlog"] == 99
        assert options["whatever"] == "x"

    def test_an_endpoint_that_binds_nothing_is_legal(self):
        """Ca 2: adapter kết nối RA (mqtt, modbus) không mở cổng nào.

        Vế đối chứng của `test_a_single_block_parses_into_one_process`: hỏi
        "cổng đâu" là hỏi sai câu với hạng adapter này.
        """
        topo = parse_topology(_one(mqtt={"nha-may": {"client_id": "xime-1"}}))

        spec = topo.by_id("main").spec_for("mqtt", "nha-may")
        assert spec.listens is False
        assert spec.options["client_id"] == "xime-1"

    def test_a_unix_path_is_an_address_too(self):
        topo = parse_topology(_one(socket={"rpc": {"path": "/run/xime/a.sock"}}))

        spec = topo.by_id("main").spec_for("socket", "rpc")
        assert spec.listens is True
        assert spec.endpoint == ("unix", "/run/xime/a.sock")


class TestPrimary:
    """Phép kiểm 1, và nó đi thành cặp: thiếu là lỗi, thừa cũng là lỗi."""

    def test_no_primary_is_an_error(self):
        with pytest.raises(StartupException, match="No primary Process"):
            parse_topology({"a": {"web": {"default": {"port": 1}}}})

    def test_two_primaries_is_an_error(self):
        with pytest.raises(StartupException, match="Multiple primary Processes"):
            parse_topology(
                {
                    "a": {"primary": True, "web": {"default": {"port": 1}}},
                    "b": {"primary": True, "web": {"default": {"port": 2}}},
                }
            )

    def test_exactly_one_primary_is_accepted(self):
        topo = parse_topology(
            {
                "a": {"primary": True, "web": {"default": {"port": 1}}},
                "b": {"web": {"default": {"port": 2}}},
            }
        )
        assert topo.primary_id == "a"
        assert topo.by_id("b").primary is False


class TestCount:
    def test_count_expands_into_deterministic_ids(self):
        """Id sinh ra là nhãn trong mọi dòng log, nên nó phải đoán trước được."""
        topo = parse_topology(
            {
                "main": {"primary": True, "web": {"default": {"port": 1, "shared": True}}},
                "workers": {
                    "count": 3,
                    "web": {"default": {"port": 1, "shared": True}},
                },
            }
        )

        assert topo.ids == ("main", "workers-1", "workers-2", "workers-3")

    def test_count_one_keeps_the_plain_name(self):
        topo = parse_topology({"main": {"primary": True, "count": 1, "web": {"d": {"port": 1}}}})
        assert topo.ids == ("main",)

    def test_count_with_a_private_port_is_an_error(self):
        """Mọi tiến trình bung ra từ một khối bind cùng một địa chỉ.

        Không tự sinh dải cổng: tự sinh là lấn sang việc của sổ đăng ký mạng, và
        người vận hành sẽ có N cổng không ai đăng ký.
        """
        with pytest.raises(StartupException, match="count With A Private Address"):
            parse_topology(
                {
                    "main": {"primary": True, "web": {"d": {"port": 1, "shared": True}}},
                    "workers": {"count": 2, "web": {"d": {"port": 1}}},
                }
            )

    def test_count_with_a_non_listening_endpoint_is_fine(self):
        """Vế đối chứng: `count` chỉ đòi `shared` ở ô CÓ địa chỉ."""
        topo = parse_topology(
            {
                "main": {"primary": True, "mqtt": {"m": {"client_id": "a"}}},
                "workers": {"count": 2, "mqtt": {"m": {"client_id": "b"}}},
            }
        )
        assert topo.ids == ("main", "workers-1", "workers-2")

    def test_primary_on_a_count_block_is_an_error(self):
        with pytest.raises(StartupException, match="primary On A count Block"):
            parse_topology(
                {"w": {"primary": True, "count": 2, "web": {"d": {"port": 1, "shared": True}}}}
            )

    def test_an_expanded_id_colliding_with_a_real_block_is_an_error(self):
        with pytest.raises(StartupException, match="Duplicate Process Id"):
            parse_topology(
                {
                    "api": {"count": 2, "web": {"d": {"port": 1, "shared": True}}},
                    "api-1": {"primary": True, "web": {"d": {"port": 1, "shared": True}}},
                }
            )


class TestSharedAddresses:
    """Phép kiểm 4 - bản vá cho chỗ *"bind thành công"* mang hai nghĩa."""

    def test_the_same_port_in_two_blocks_needs_shared_in_both(self):
        with pytest.raises(StartupException, match="Address Used By Several Processes"):
            parse_topology(
                {
                    "a": {"primary": True, "web": {"d": {"port": 8086, "shared": True}}},
                    "b": {"web": {"d": {"port": 8086}}},
                }
            )

    def test_the_same_port_declared_shared_everywhere_is_accepted(self):
        topo = parse_topology(
            {
                "a": {"primary": True, "web": {"d": {"port": 8086, "shared": True}}},
                "b": {"web": {"d": {"port": 8086, "shared": True}}},
            }
        )
        assert len(topo.blocks) == 2

    def test_different_ports_never_need_shared(self):
        topo = parse_topology(
            {
                "a": {"primary": True, "web": {"d": {"port": 8086}}},
                "b": {"web": {"d": {"port": 8087}}},
            }
        )
        assert len(topo.blocks) == 2

    def test_a_shared_port_on_two_hosts_is_an_error(self):
        """Một địa chỉ dùng chung là MỘT socket, nên chỉ có một host.

        `0.0.0.0:8086` nuốt luôn `127.0.0.1:8086` nên hai khối này va nhau lúc
        bind dù trông như hai địa chỉ khác nhau.
        """
        with pytest.raises(StartupException, match="Different Hosts"):
            parse_topology(
                {
                    "a": {
                        "primary": True,
                        "web": {"d": {"host": "0.0.0.0", "port": 8086, "shared": True}},
                    },
                    "b": {"web": {"d": {"host": "127.0.0.1", "port": 8086, "shared": True}}},
                }
            )

    def test_two_adapters_of_one_process_on_one_port_is_an_error(self):
        """`shared` nói *tôi chia cổng với tiến trình khác*, không phải *với chính tôi*."""
        with pytest.raises(StartupException, match="Duplicate Address In One Process"):
            parse_topology(
                _one(
                    web={"a": {"port": 8086}, "b": {"port": 8086}},
                )
            )

    def test_a_shared_address_cannot_be_split_across_adapter_kinds(self):
        with pytest.raises(StartupException, match="Different Adapters"):
            parse_topology(
                {
                    "a": {"primary": True, "web": {"d": {"port": 8086, "shared": True}}},
                    "b": {"grpc": {"d": {"port": 8086, "shared": True}}},
                }
            )

    def test_shared_without_an_address_is_an_error(self):
        with pytest.raises(StartupException, match="shared Without An Address"):
            parse_topology(_one(mqtt={"m": {"client_id": "x", "shared": True}}))


class TestMalformedInput:
    def test_processes_must_be_a_mapping(self):
        with pytest.raises(StartupException, match="Invalid processes Block"):
            parse_topology(["main"])

    def test_an_empty_processes_block_is_an_error(self):
        with pytest.raises(StartupException, match="Empty processes Block"):
            parse_topology({})

    def test_port_must_be_an_integer(self):
        with pytest.raises(StartupException, match="Invalid Endpoint Port"):
            parse_topology(_one(web={"d": {"port": "8086"}}))

    def test_a_boolean_is_not_a_port(self):
        """`True` là `int` trong Python. Không chặn riêng thì `port: yes` trong
        YAML lặng lẽ thành cổng số 1."""
        with pytest.raises(StartupException, match="Invalid Endpoint Port"):
            parse_topology(_one(web={"d": {"port": True}}))

    def test_shared_must_be_a_boolean(self):
        with pytest.raises(StartupException, match="Invalid shared Flag"):
            parse_topology(_one(web={"d": {"port": 1, "shared": "yes"}}))

    def test_port_and_path_together_are_ambiguous(self):
        with pytest.raises(StartupException, match="Ambiguous Endpoint"):
            parse_topology(_one(web={"d": {"port": 1, "path": "/tmp/x.sock"}}))

    def test_a_process_id_with_odd_characters_is_rejected(self):
        with pytest.raises(StartupException, match="Invalid processes Identifier"):
            parse_topology({"main worker": {"primary": True, "web": {"d": {"port": 1}}}})

    def test_count_must_be_a_positive_integer(self):
        with pytest.raises(StartupException, match="Invalid count"):
            parse_topology({"a": {"primary": True, "count": 0, "web": {"d": {"port": 1}}}})
