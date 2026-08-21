"""Khai kênh, khai handler, và bốn phép kiểm lúc khởi động."""

from __future__ import annotations

import pytest

from xime.core.exception.framework import StartupException
from xime.core.link import (
    INTERNAL_CHANNEL,
    ChannelSpec,
    collect,
    configure_link,
    link_registry,
    on_announce,
    on_request,
)


class TestChannelSpec:
    def test_defaults_are_modest(self):
        """⚠ Trên Windows bộ nhớ chung bị cấp phát THẬT ngay lúc tạo.

        Nên mặc định phải khiêm tốn: 4 kênh × 4096 dòng × 64 KB là 1 GB mất
        trắng lúc khởi động, và không ai định làm điều đó.
        """
        spec = ChannelSpec()
        assert spec.rows == 256
        assert spec.payload_bytes == 512

    @pytest.mark.parametrize("rows", [0, -1])
    def test_rejects_a_channel_with_no_rows(self, rows):
        with pytest.raises(ValueError, match="rows must be >= 1"):
            ChannelSpec(rows=rows)

    @pytest.mark.parametrize("size", [0, -8])
    def test_rejects_a_channel_with_no_payload(self, size):
        with pytest.raises(ValueError, match="payload_bytes must be >= 1"):
            ChannelSpec(payload_bytes=size)


class TestConfigureLink:
    def test_the_internal_channel_exists_even_when_the_app_declares_nothing(self):
        """⚠ Framework LUÔN tạo kênh nội bộ, không phụ thuộc ứng dụng khai gì.

        Cha dùng nó làm kênh điều khiển (thăng cấp primary, tín hiệu sẵn sàng).
        Để nó phụ thuộc ứng dụng là đặt một chốt chặn của framework lên một
        thành phần TUỲ CHỌN - đúng thứ đã bị bác khi loại phương án khoá trong
        LMDB: nó sẽ vắng mặt đúng lúc cần nhất.
        """
        configure_link()
        assert INTERNAL_CHANNEL in link_registry.channels()

    def test_it_still_exists_when_the_app_declares_its_own(self):
        configure_link(channels={"fieldbus": ChannelSpec(rows=4, payload_bytes=32)})
        channels = link_registry.channels()
        assert INTERNAL_CHANNEL in channels
        assert "fieldbus" in channels

    def test_app_channels_excludes_the_internal_one(self):
        """Phép kiểm khởi động nói về kênh của ỨNG DỤNG, không về kênh framework."""
        configure_link(channels={"fieldbus": ChannelSpec()})
        assert set(link_registry.app_channels()) == {"fieldbus"}

    def test_a_name_reserved_for_the_framework_is_refused(self):
        with pytest.raises(StartupException, match="Reserved Link Channel Name"):
            configure_link(channels={"__mine__": ChannelSpec()})

    @pytest.mark.parametrize("bad", ["", "x" * 65])
    def test_an_unusable_name_is_refused(self, bad):
        with pytest.raises(StartupException, match="Invalid Link Channel Name"):
            configure_link(channels={bad: ChannelSpec()})

    def test_handlers_are_stored_as_classes_not_instances(self):
        """`handlers=` nhận CLASS để framework lấy instance từ DI.

        Cùng khuôn `configure_jwt(key_provider=...)` và
        `configure_grpc_tls(provider=...)`: truyền class, framework inject.
        """

        class Handler:
            @on_announce("fieldbus")
            async def listen(self, key: str, payload: bytes) -> None: ...

        configure_link(channels={"fieldbus": ChannelSpec()}, handlers=[Handler])
        assert link_registry.handlers() == (Handler,)

    def test_a_channel_with_no_handler_is_perfectly_valid(self):
        """Tiến trình chỉ GỬI là ca bình thường, không phải lỗi."""
        configure_link(channels={"chi-gui": ChannelSpec()})
        assert link_registry.handlers() == ()


class TestCollect:
    def test_it_binds_a_method_to_its_channel(self):
        class Handler:
            @on_request("fieldbus")
            async def control(self, key: str, payload: bytes) -> bytes | None:
                return None

        bound = collect([Handler()])
        assert set(bound) == {"fieldbus"}
        assert bound["fieldbus"].kind == "request"
        assert bound["fieldbus"].owner == "Handler.control"

    def test_one_class_may_serve_several_channels(self):
        class Handler:
            @on_request("a")
            async def one(self, key: str, payload: bytes) -> bytes | None:
                return None

            @on_announce("b")
            async def two(self, key: str, payload: bytes) -> None: ...

        assert set(collect([Handler()])) == {"a", "b"}

    def test_two_handlers_on_one_channel_is_refused(self):
        """Một kênh một handler.

        Nhiều handler thì framework phải trả lời *"ai được nhận"*, mà câu đó lại
        phụ thuộc thứ chỉ biết lúc chạy - đúng cái vòng vừa thoát ra khi bỏ định
        tuyến theo tên tiến trình. Muốn nhiều nhánh thì handler tự phân nhánh.
        """

        class First:
            @on_request("fieldbus")
            async def control(self, key: str, payload: bytes) -> bytes | None:
                return None

        class Second:
            @on_announce("fieldbus")
            async def listen(self, key: str, payload: bytes) -> None: ...

        with pytest.raises(StartupException, match="Two Handlers On One Link Channel"):
            collect([First(), Second()])

    def test_the_error_names_both_offenders(self):
        class First:
            @on_request("fieldbus")
            async def control(self, key: str, payload: bytes) -> bytes | None:
                return None

        class Second:
            @on_request("fieldbus")
            async def other(self, key: str, payload: bytes) -> bytes | None:
                return None

        with pytest.raises(StartupException) as exc:
            collect([First(), Second()])
        assert "First.control" in str(exc.value)
        assert "Second.other" in str(exc.value)

    def test_an_object_with_no_handler_contributes_nothing(self):
        class Plain:
            async def helper(self) -> None: ...

        assert collect([Plain()]) == {}


class TestHandlerShape:
    def test_a_blocking_handler_is_refused_at_import_time(self):
        """Vòng xử lý kênh `await` handler, nên nó phải là `async def`.

        Một handler đồng bộ sẽ chặn cả kênh - và nó là thứ bắt được ngay lúc
        định nghĩa class, không cần đợi tới lúc chạy.
        """
        with pytest.raises(StartupException, match="Link Handler Must Be Async"):

            class Blocking:
                @on_request("fieldbus")
                def control(self, key: str, payload: bytes) -> bytes | None:
                    return None

    def test_an_async_handler_is_accepted(self):
        """Vế đối chứng: phép kiểm phải CHO QUA hình dạng đúng."""

        class Fine:
            @on_request("fieldbus")
            async def control(self, key: str, payload: bytes) -> bytes | None:
                return None

        assert set(collect([Fine()])) == {"fieldbus"}

    def test_an_empty_channel_name_is_refused(self):
        with pytest.raises(ValueError, match="non-empty name"):
            on_request("")
