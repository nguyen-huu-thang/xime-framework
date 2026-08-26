"""Phép kiểm cần biết `main.py` khai gì, và việc gán ô cho adapter.

Bốn phép kiểm lúc khởi động chia làm hai nửa: nửa tự kiểm được từ YAML nằm ở
`test_topology.py`, nửa cần danh sách adapter nằm ở đây.
"""

from __future__ import annotations

import logging

import pytest

from xime.core.bootstrap._processes import parse_topology
from xime.core.bootstrap._slot import AdapterSlot
from xime.core.bootstrap.adapter import SCALING_REPLICATED, Adapter
from xime.core.bootstrap._supervisor import (
    bind_shared_sockets,
    prepare_worker,
    validate_against_adapters,
)
from xime.core.exception.framework import StartupException


class FakeAdapter(Adapter, scaling=SCALING_REPLICATED):
    """Adapter tối thiểu, đủ để framework nhận diện và đẩy ô vào."""

    adapter_kind = "web"
    share_port_by = "inherit"

    def __init__(self, server_id: str = "default") -> None:
        self.adapter_id = server_id
        self.slot: AdapterSlot | None = None

    def assign_slot(self, slot: AdapterSlot) -> None:
        self.slot = slot

    async def start(self, app: object) -> None:  # pragma: no cover - không chạy
        ...

    async def serve(self) -> None:  # pragma: no cover - không chạy
        ...

    async def stop(self) -> None:  # pragma: no cover - không chạy
        ...


class FakeGrpc(FakeAdapter):
    adapter_kind = "grpc"
    share_port_by = "reuseport"


class FakeOutbound(FakeAdapter):
    """Hạng kết nối RA: không mở cổng, và không dùng chung được cổng nào."""

    adapter_kind = "mqtt"
    share_port_by = "none"


def _topo(raw: dict):
    return parse_topology(raw)


class TestUnknownEndpoint:
    """Phép kiểm 2: tên trong cấu hình mà `main.py` không khai."""

    def test_a_typo_in_the_adapter_id_is_caught(self):
        topo = _topo({"main": {"primary": True, "web": {"publik": {"port": 1}}}})

        with pytest.raises(StartupException, match="Unknown Endpoint") as exc:
            validate_against_adapters(topo, [FakeAdapter("public")])

        assert "web.publik" in str(exc.value)
        assert "web.public" in str(exc.value)

    def test_a_typo_in_the_adapter_kind_is_caught(self):
        topo = _topo({"main": {"primary": True, "wbe": {"default": {"port": 1}}}})

        with pytest.raises(StartupException, match="Unknown Endpoint"):
            validate_against_adapters(topo, [FakeAdapter()])

    def test_matching_names_pass(self):
        topo = _topo({"main": {"primary": True, "web": {"default": {"port": 1}}}})
        validate_against_adapters(topo, [FakeAdapter()])


class TestAdapterNobodyRuns:
    def test_an_adapter_missing_from_every_block_is_an_error(self):
        """Khác phép kiểm 3: *khối này không có* là cách lọc hợp lệ, *không khối
        nào có* thì không ai cố ý làm vậy."""
        topo = _topo({"main": {"primary": True, "web": {"default": {"port": 1}}}})

        with pytest.raises(StartupException, match="Runs In No Process") as exc:
            validate_against_adapters(topo, [FakeAdapter(), FakeGrpc("internal")])

        assert "grpc.internal" in str(exc.value)

    def test_an_adapter_present_in_only_one_block_is_fine(self):
        """Vế đối chứng - đây chính là ma trận thưa mà fieldbus cần."""
        topo = _topo(
            {
                "a": {"primary": True, "web": {"d": {"port": 1}}, "grpc": {"i": {"port": 3}}},
                "b": {"web": {"d": {"port": 2}}},
            }
        )
        validate_against_adapters(topo, [FakeAdapter("d"), FakeGrpc("i")])


class TestSharing:
    def test_an_adapter_that_cannot_share_rejects_the_flag(self):
        topo = _topo({"main": {"primary": True, "mqtt": {"m": {"port": 1, "shared": True}}}})

        with pytest.raises(StartupException, match="Cannot Share An Address"):
            validate_against_adapters(topo, [FakeOutbound("m")])

    def test_reuseport_is_refused_on_windows(self, monkeypatch):
        """`SO_REUSEPORT` không có trên Windows.

        Không nổ ở đây thì tiến trình thứ hai chết bằng `WinError 10048` giữa
        lúc chạy, và người đọc lỗi đó không có đường nào lần ra nguyên nhân.
        """
        monkeypatch.setattr("sys.platform", "win32")
        topo = _topo(
            {
                "a": {"primary": True, "grpc": {"i": {"port": 9095, "shared": True}}},
                "b": {"grpc": {"i": {"port": 9095, "shared": True}}},
            }
        )

        with pytest.raises(StartupException, match="Not Available On Windows"):
            validate_against_adapters(topo, [FakeGrpc("i")])

    def test_reuseport_is_accepted_on_linux(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        topo = _topo(
            {
                "a": {"primary": True, "grpc": {"i": {"port": 9095, "shared": True}}},
                "b": {"grpc": {"i": {"port": 9095, "shared": True}}},
            }
        )
        validate_against_adapters(topo, [FakeGrpc("i")])

    def test_a_private_port_is_never_checked_for_sharing(self, monkeypatch):
        """Vế đối chứng của hai test trên: không khai `shared` thì không ai hỏi."""
        monkeypatch.setattr("sys.platform", "win32")
        topo = _topo(
            {
                "a": {"primary": True, "grpc": {"i": {"port": 9095}}},
                "b": {"grpc": {"i": {"port": 9096}}},
            }
        )
        validate_against_adapters(topo, [FakeGrpc("i")])


class TestBindSharedSockets:
    def test_the_parent_binds_one_socket_per_shared_address(self):
        topo = _topo(
            {
                "a": {"primary": True, "web": {"d": {"host": "127.0.0.1", "port": 0, "shared": True}}},
                "b": {"web": {"d": {"host": "127.0.0.1", "port": 0, "shared": True}}},
            }
        )
        bound = bind_shared_sockets(topo, [FakeAdapter("d")])
        try:
            assert len(bound) == 1
            assert ("tcp", 0) in bound
        finally:
            for sock in bound.values():
                sock.close()

    def test_a_shared_address_is_bound_exactly_ONCE(self, monkeypatch):
        """⚠ Đếm số lần `bind`, không đếm số socket trả về.

        Dict kết quả dùng danh tính địa chỉ làm khoá nên nó **luôn** ra một mục,
        kể cả khi cha bind ba lần rồi ghi đè lên nhau. Trên Windows ba lần bind
        đó đều thành công (`SO_REUSEADDR` cho phép chiếm lại), nên hai socket bị
        rò và **không gì báo**; trên Linux lần thứ hai nổ `EADDRINUSE` và cụm
        không khởi động nổi. Cùng một lỗi, hai triệu chứng khác hẳn nhau - nên
        phép đo phải nhắm vào **nguyên nhân**, không nhắm vào triệu chứng.
        """
        from xime.core.bootstrap import _supervisor

        calls: list[int] = []
        original = _supervisor._bind_tcp

        def spy(spec):
            calls.append(spec.port)
            return original(spec)

        monkeypatch.setattr(_supervisor, "_bind_tcp", spy)
        topo = _topo(
            {
                "a": {"primary": True, "web": {"d": {"host": "127.0.0.1", "port": 0, "shared": True}}},
                "b": {"web": {"d": {"host": "127.0.0.1", "port": 0, "shared": True}}},
                "c": {"web": {"d": {"host": "127.0.0.1", "port": 0, "shared": True}}},
            }
        )
        bound = bind_shared_sockets(topo, [FakeAdapter("d")])
        try:
            assert len(calls) == 1, f"parent bound the same address {len(calls)} times"
        finally:
            for sock in bound.values():
                sock.close()

    def test_a_private_address_is_left_to_the_child(self):
        topo = _topo({"main": {"primary": True, "web": {"d": {"host": "127.0.0.1", "port": 0}}}})
        assert bind_shared_sockets(topo, [FakeAdapter("d")]) == {}

    def test_reuseport_addresses_are_not_bound_by_the_parent(self, monkeypatch):
        """gRPC tự bind ở từng con - cha bind hộ là chiếm mất cổng của chúng."""
        monkeypatch.setattr("sys.platform", "linux")
        topo = _topo(
            {
                "a": {"primary": True, "grpc": {"i": {"host": "127.0.0.1", "port": 0, "shared": True}}},
                "b": {"grpc": {"i": {"host": "127.0.0.1", "port": 0, "shared": True}}},
            }
        )
        assert bind_shared_sockets(topo, [FakeGrpc("i")]) == {}

    def test_a_port_already_taken_fails_in_the_parent(self):
        """⭐ Cổng bị chiếm thì CHA nổ ngay, thay vì bốn con lần lượt nổ và người
        vận hành đọc bốn stack trace giống nhau."""
        import socket as pysocket

        blocker = pysocket.socket()
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]
        try:
            topo = _topo(
                {
                    "a": {"primary": True, "web": {"d": {"host": "127.0.0.1", "port": port, "shared": True}}},
                    "b": {"web": {"d": {"host": "127.0.0.1", "port": port, "shared": True}}},
                }
            )
            with pytest.raises(StartupException, match="Cannot Bind A Shared Port"):
                bind_shared_sockets(topo, [FakeAdapter("d")])
        finally:
            blocker.close()


class TestPrepareWorker:
    def test_each_adapter_gets_its_own_cell(self):
        topo = _topo(
            {
                "main": {
                    "primary": True,
                    "web": {"d": {"port": 8086}},
                    "grpc": {"i": {"port": 9095}},
                }
            }
        )
        web, grpc = FakeAdapter("d"), FakeGrpc("i")

        active = prepare_worker(topo, [web, grpc], "main", {})

        assert active == [web, grpc]
        assert web.slot.spec.port == 8086
        assert grpc.slot.spec.port == 9095
        assert web.slot.primary is True
        assert web.slot.process_id == "main"

    def test_an_adapter_the_block_omits_is_filtered_out_and_said_out_loud(self, caplog):
        """Phép kiểm 3: lọc, không phải lỗi - nhưng **phải nói ra**.

        Với web thì im lặng còn chấp nhận được; với một dây chuyền thiết bị thì
        im lặng nghĩa là không ai đọc nó mà không ai biết.
        """
        topo = _topo(
            {
                "a": {"primary": True, "web": {"d": {"port": 1}}, "grpc": {"i": {"port": 3}}},
                "b": {"web": {"d": {"port": 2}}},
            }
        )
        web, grpc = FakeAdapter("d"), FakeGrpc("i")

        with caplog.at_level(logging.WARNING):
            active = prepare_worker(topo, [web, grpc], "b", {})

        assert active == [web]
        assert grpc.slot is None
        assert any("grpc" in record.getMessage() for record in caplog.records)

    def test_an_inherited_socket_reaches_the_right_adapter(self):
        import socket as pysocket

        topo = _topo(
            {
                "a": {"primary": True, "web": {"d": {"port": 8086, "shared": True}}},
                "b": {"web": {"d": {"port": 8086, "shared": True}}},
            }
        )
        sock = pysocket.socket()
        web = FakeAdapter("d")
        try:
            prepare_worker(topo, [web], "b", {("web", "d"): sock})
            assert web.slot.sock is sock
        finally:
            sock.close()

    def test_an_unknown_process_id_is_an_error(self):
        topo = _topo({"main": {"primary": True, "web": {"d": {"port": 1}}}})

        with pytest.raises(StartupException, match="Unknown Process Id"):
            prepare_worker(topo, [FakeAdapter("d")], "typo", {})

    def test_an_adapter_without_assign_slot_is_an_error(self):
        """Không nổ ở đây thì adapter tự đọc YAML và bind CỔNG KHÁC với cái cha
        vừa kiểm - hai nguồn cho một giá trị, và không gì báo."""

        class Legacy(Adapter, scaling=SCALING_REPLICATED):
            adapter_kind = "web"
            share_port_by = "inherit"

            def __init__(self) -> None:
                self.adapter_id = "d"

            async def start(self, app): ...
            async def serve(self): ...
            async def stop(self): ...

        topo = _topo({"main": {"primary": True, "web": {"d": {"port": 1}}}})

        with pytest.raises(StartupException, match="Does Not Accept A processes Block"):
            prepare_worker(topo, [Legacy()], "main", {})


class TestAdapterIdentity:
    def test_an_adapter_without_adapter_kind_is_an_error(self):
        class Nameless(Adapter, scaling=SCALING_REPLICATED):
            def __init__(self) -> None:
                self.adapter_id = "d"

            async def start(self, app): ...
            async def serve(self): ...
            async def stop(self): ...

        topo = _topo({"main": {"primary": True, "web": {"d": {"port": 1}}}})

        with pytest.raises(StartupException, match="Without adapter_kind"):
            validate_against_adapters(topo, [Nameless()])

    def test_the_real_adapters_declare_their_kind(self):
        """Test đi đúng đường tài liệu: sáu adapter thật, không phải fake."""
        from xime.adapters.grpc import GrpcAdapter
        from xime.adapters.modbus import ModbusAdapter
        from xime.adapters.mqtt import MqttAdapter
        from xime.adapters.opcua import OpcuaAdapter
        from xime.adapters.socket import SocketAdapter
        from xime.adapters.web import WebAdapter

        kinds = {
            WebAdapter: "web",
            GrpcAdapter: "grpc",
            SocketAdapter: "socket",
            MqttAdapter: "mqtt",
            ModbusAdapter: "modbus",
            OpcuaAdapter: "opcua",
        }
        for cls, kind in kinds.items():
            assert cls.adapter_kind == kind, cls.__name__


class TestShardingRulesAreData:
    """⚠ Cả lớp này gọi với `share_load=False`, và lý do đáng ghi.

    Hai phép kiểm phân mảnh **chưa thể nổ ở 0.8**: adapter hạng phân mảnh bị
    `_reject_sharded_under_share_load` chặn trước, vì việc chia tập thiết bị /
    tập topic lùi sang **một bản 0.8.x** chưa chốt. Chúng được xây và canh từ bây giờ vì hình
    dạng `unique_per_process` / `disjoint_per_process` là **API công khai** và
    0.8 là bản Alpha cuối - đổi tên sau khi ba adapter đã dùng là phải sửa cả ba.

    Gọi thẳng với `share_load=False` là cách kiểm chúng mà không phải gỡ cái
    chốt ấy ra; ⭐ và `TestTheShardedGateIsStillClosed` ngay dưới canh
    chính cái chốt đó, để không ai gỡ nó mà bộ test vẫn xanh.

    Trước 0.8 lý do chống trùng nằm trong **docstring** của `MqttAdapter` -
    cả một đoạn giải thích vì sao hai adapter cùng `client_id` sẽ đánh nhau trong
    vòng lặp reconnect. Framework **đọc được nhưng không dùng được**."""

    class FakeMqtt(FakeAdapter, scaling="sharded",
                   unique_per_process=("client_id",),
                   disjoint_per_process=("topics",)):
        adapter_kind = "mqtt"
        share_port_by = "none"

    def test_two_processes_sharing_one_client_id_is_an_error(self):
        topo = _topo(
            {
                "a": {"primary": True, "mqtt": {"m": {"client_id": "xime-1"}}},
                "b": {"mqtt": {"m": {"client_id": "xime-1"}}},
            }
        )
        with pytest.raises(StartupException, match="Repeats A Value") as exc:
            validate_against_adapters(topo, [self.FakeMqtt("m")], share_load=False)
        assert "client_id" in str(exc.value)

    def test_different_client_ids_pass(self):
        """Vế đối chứng - không có nó thì cách sửa sai *"luôn nổ"* cũng qua."""
        topo = _topo(
            {
                "a": {"primary": True, "mqtt": {"m": {"client_id": "xime-1"}}},
                "b": {"mqtt": {"m": {"client_id": "xime-2"}}},
            }
        )
        validate_against_adapters(topo, [self.FakeMqtt("m")], share_load=False)

    def test_overlapping_topics_are_an_error(self):
        """⭐ Phép kiểm **khác** phép kiểm trên: *"khác nhau"* áp cho một giá trị
        đơn, *"không giao nhau"* áp cho một **tập**. MQTT cần cả hai cùng lúc, và
        đó là bằng chứng tách đúng."""
        topo = _topo(
            {
                "a": {
                    "primary": True,
                    "mqtt": {"m": {"client_id": "x1", "topics": ["nha-kinh/A/#", "chung/#"]}},
                },
                "b": {"mqtt": {"m": {"client_id": "x2", "topics": ["chung/#"]}}},
            }
        )
        with pytest.raises(StartupException, match="Overlaps Across Processes") as exc:
            validate_against_adapters(topo, [self.FakeMqtt("m")], share_load=False)
        assert "chung/#" in str(exc.value)

    def test_disjoint_topics_pass(self):
        topo = _topo(
            {
                "a": {"primary": True, "mqtt": {"m": {"client_id": "x1", "topics": ["A/#"]}}},
                "b": {"mqtt": {"m": {"client_id": "x2", "topics": ["B/#"]}}},
            }
        )
        validate_against_adapters(topo, [self.FakeMqtt("m")], share_load=False)


class TestSingletonBelongsToPrimary:
    """Khai một adapter đơn nhất ở khối khác là **một lời hứa framework không
    giữ**: nó chỉ start ở primary. Không nổ thì cấu hình nói một đằng, hành vi
    một nẻo, và không gì báo."""

    class FakeCron(FakeAdapter, scaling="singleton"):
        adapter_kind = "scheduler"
        share_port_by = "none"

    def test_declaring_it_outside_primary_is_an_error(self):
        topo = _topo(
            {
                "a": {"primary": True, "scheduler": {"default": {}}},
                "b": {"scheduler": {"default": {}}},
            }
        )
        with pytest.raises(StartupException, match="Outside primary") as exc:
            validate_against_adapters(topo, [self.FakeCron("default")], share_load=False)
        assert "b" in str(exc.value)

    def test_declaring_it_only_on_primary_passes(self):
        topo = _topo(
            {
                "a": {"primary": True, "scheduler": {"default": {}}},
                "b": {"web": {"d": {"port": 1}}},
            }
        )
        validate_against_adapters(
            topo, [self.FakeCron("default"), FakeAdapter("d")], share_load=False
        )


class TestTheShardedGateIsStillClosed:
    """Chốt: adapter hạng phân mảnh chưa chia tải được.

    ⚠ Chốt này ở **framework**, không ở adapter. Trước đó mỗi adapter tự ném
    trong `assign_slot()`, nhưng từ khi mọi adapter luôn nhận một ô thì cách đó
    chặn luôn cả nhánh **một tiến trình** - nơi chúng chạy hoàn toàn bình
    thường. Thứ phải chặn là *chia tải*, không phải *nhận cấu hình*.
    """

    class FakeMqtt(FakeAdapter, scaling="sharded", unique_per_process=("client_id",)):
        adapter_kind = "mqtt"
        share_port_by = "none"

    def test_share_load_refuses_a_sharded_adapter(self):
        topo = _topo({"main": {"primary": True, "mqtt": {"m": {"client_id": "x"}}}})

        with pytest.raises(StartupException, match="Not Supported Yet") as exc:
            validate_against_adapters(topo, [self.FakeMqtt("m")], share_load=True)
        # ⚠ KHÔNG neo vào một số hiệu bản. Câu cũ là `"0.8.1" in ...`, và nó
        # đỏ ngay ngày việc đó bị lùi - tức test canh **lịch phát hành** thay vì
        # canh **hành vi**. Neo vào đường lui mà thông báo phải chỉ ra.
        assert "single process" in str(exc.value)

    def test_a_single_process_runs_it_fine(self):
        """Vế đối chứng, và là vế quan trọng hơn: chặn nhầm ở đây là **mọi app
        MQTT / Modbus / OPC UA hết chạy được**, kể cả một tiến trình."""
        topo = _topo({"main": {"primary": True, "mqtt": {"m": {"client_id": "x"}}}})
        validate_against_adapters(topo, [self.FakeMqtt("m")], share_load=False)
