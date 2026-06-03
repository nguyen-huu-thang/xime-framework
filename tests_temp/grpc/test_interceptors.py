"""
Test interceptors:

  _GrpcInterceptorRegistry:
    - get_interceptors() rỗng ban đầu
    - get_error_mappings() rỗng ban đầu
    - add_interceptors() lưu đúng
    - add_interceptors() gọi nhiều lần tích luỹ
    - set_error_mappings() lưu đúng, gọi nhiều lần merge
    - get_interceptors() / get_error_mappings() trả về bản sao

  configure_grpc_interceptors() + configure_grpc_error_mappings():
    - delegate đúng vào registry

  RequestContextInterceptor:
    - set request_id trong request_context trước khi gọi continuation
    - xóa request_context sau khi continuation hoàn thành
    - xóa security context sau khi continuation hoàn thành
    - vẫn clear context kể cả khi continuation raise exception

  ErrorMappingInterceptor._resolve_status_code():
    - trả về status code mapped khi exception đúng loại
    - trả về INTERNAL khi không có mapping
    - hỗ trợ isinstance check (subclass)

  ErrorMappingInterceptor.intercept_service():
    - trả về None ngay khi handler là None
    - wrap unary_unary handler
    - wrap unary_stream handler
    - wrap stream_unary handler
    - wrap stream_stream handler
    - handler không có exception: hành vi bình thường (không thay đổi output)
    - handler raise mapped exception: gọi context.abort với status code đúng
    - handler raise unmapped exception: gọi context.abort với INTERNAL
    - handler raise grpc.RpcError: re-raise không abort
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import grpc.aio
import pytest
import pytest_asyncio

from xime.adapters.grpc.interceptors._config import (
    _GrpcInterceptorRegistry,
    configure_grpc_error_mappings,
    configure_grpc_interceptors,
    grpc_interceptor_registry,
)
from xime.adapters.grpc.interceptors._context import RequestContextInterceptor
from xime.adapters.grpc.interceptors._error import ErrorMappingInterceptor
from xime.core.context import request_context
from xime.core.security import clear_security


# ---------------------------------------------------------------------------
# Helper exception classes
# ---------------------------------------------------------------------------

class _NotFoundException(Exception):
    pass

class _ValidationException(Exception):
    pass

class _UnmappedException(Exception):
    pass

class _SubNotFoundException(_NotFoundException):
    pass


# ---------------------------------------------------------------------------
# _GrpcInterceptorRegistry — trạng thái ban đầu
# ---------------------------------------------------------------------------

class TestGrpcInterceptorRegistryInitial:
    def test_interceptors_empty_on_init(self):
        reg = _GrpcInterceptorRegistry()
        assert reg.get_interceptors() == []

    def test_error_mappings_empty_on_init(self):
        reg = _GrpcInterceptorRegistry()
        assert reg.get_error_mappings() == {}


# ---------------------------------------------------------------------------
# _GrpcInterceptorRegistry — add_interceptors
# ---------------------------------------------------------------------------

class TestGrpcInterceptorRegistryAddInterceptors:
    def test_stores_interceptors(self):
        reg = _GrpcInterceptorRegistry()
        mock_interceptor = MagicMock(spec=grpc.aio.ServerInterceptor)
        reg.add_interceptors([mock_interceptor])
        assert mock_interceptor in reg.get_interceptors()

    def test_multiple_calls_accumulate(self):
        reg = _GrpcInterceptorRegistry()
        a = MagicMock(spec=grpc.aio.ServerInterceptor)
        b = MagicMock(spec=grpc.aio.ServerInterceptor)
        reg.add_interceptors([a])
        reg.add_interceptors([b])
        interceptors = reg.get_interceptors()
        assert a in interceptors
        assert b in interceptors

    def test_get_interceptors_returns_copy(self):
        reg = _GrpcInterceptorRegistry()
        a = MagicMock(spec=grpc.aio.ServerInterceptor)
        reg.add_interceptors([a])
        result = reg.get_interceptors()
        result.append(MagicMock())
        assert len(reg.get_interceptors()) == 1


# ---------------------------------------------------------------------------
# _GrpcInterceptorRegistry — set_error_mappings
# ---------------------------------------------------------------------------

class TestGrpcInterceptorRegistryErrorMappings:
    def test_stores_mappings(self):
        reg = _GrpcInterceptorRegistry()
        reg.set_error_mappings({_NotFoundException: grpc.StatusCode.NOT_FOUND})
        assert reg.get_error_mappings()[_NotFoundException] == grpc.StatusCode.NOT_FOUND

    def test_multiple_calls_merge(self):
        reg = _GrpcInterceptorRegistry()
        reg.set_error_mappings({_NotFoundException: grpc.StatusCode.NOT_FOUND})
        reg.set_error_mappings({_ValidationException: grpc.StatusCode.INVALID_ARGUMENT})
        mappings = reg.get_error_mappings()
        assert _NotFoundException in mappings
        assert _ValidationException in mappings

    def test_later_call_overwrites_same_key(self):
        reg = _GrpcInterceptorRegistry()
        reg.set_error_mappings({_NotFoundException: grpc.StatusCode.NOT_FOUND})
        reg.set_error_mappings({_NotFoundException: grpc.StatusCode.INTERNAL})
        assert reg.get_error_mappings()[_NotFoundException] == grpc.StatusCode.INTERNAL

    def test_get_error_mappings_returns_copy(self):
        reg = _GrpcInterceptorRegistry()
        reg.set_error_mappings({_NotFoundException: grpc.StatusCode.NOT_FOUND})
        result = reg.get_error_mappings()
        result[_ValidationException] = grpc.StatusCode.INVALID_ARGUMENT
        assert _ValidationException not in reg.get_error_mappings()


# ---------------------------------------------------------------------------
# configure_grpc_interceptors / configure_grpc_error_mappings
# ---------------------------------------------------------------------------

class TestConfigureFunctions:
    def setup_method(self):
        grpc_interceptor_registry._interceptors.clear()
        grpc_interceptor_registry._error_mappings.clear()

    def teardown_method(self):
        grpc_interceptor_registry._interceptors.clear()
        grpc_interceptor_registry._error_mappings.clear()

    def test_configure_grpc_interceptors_stores_in_registry(self):
        interceptor = MagicMock(spec=grpc.aio.ServerInterceptor)
        configure_grpc_interceptors([interceptor])
        assert interceptor in grpc_interceptor_registry.get_interceptors()

    def test_configure_grpc_error_mappings_stores_in_registry(self):
        configure_grpc_error_mappings({_NotFoundException: grpc.StatusCode.NOT_FOUND})
        assert grpc_interceptor_registry.get_error_mappings()[_NotFoundException] == grpc.StatusCode.NOT_FOUND


# ---------------------------------------------------------------------------
# RequestContextInterceptor
# ---------------------------------------------------------------------------

class TestRequestContextInterceptor:
    @pytest.mark.asyncio
    async def test_sets_request_id_before_continuation(self):
        captured_id = None

        async def continuation(details):
            nonlocal captured_id
            captured_id = request_context.get("request_id")
            return MagicMock(spec=grpc.RpcMethodHandler)

        interceptor = RequestContextInterceptor()
        await interceptor.intercept_service(continuation, MagicMock())
        assert captured_id is not None
        assert len(captured_id) == 36   # UUID4 format

    @pytest.mark.asyncio
    async def test_clears_request_context_after_continuation(self):
        async def continuation(details):
            return MagicMock(spec=grpc.RpcMethodHandler)

        request_context.set("request_id", "pre-existing")
        interceptor = RequestContextInterceptor()
        await interceptor.intercept_service(continuation, MagicMock())
        assert request_context.get("request_id") is None

    @pytest.mark.asyncio
    async def test_clears_context_even_when_continuation_raises(self):
        async def continuation(details):
            raise RuntimeError("continuation failed")

        request_context.set("request_id", "some-id")
        interceptor = RequestContextInterceptor()

        with pytest.raises(RuntimeError):
            await interceptor.intercept_service(continuation, MagicMock())

        assert request_context.get("request_id") is None

    @pytest.mark.asyncio
    async def test_returns_result_of_continuation(self):
        expected_handler = MagicMock(spec=grpc.RpcMethodHandler)

        async def continuation(details):
            return expected_handler

        interceptor = RequestContextInterceptor()
        result = await interceptor.intercept_service(continuation, MagicMock())
        assert result is expected_handler


# ---------------------------------------------------------------------------
# ErrorMappingInterceptor._resolve_status_code
# ---------------------------------------------------------------------------

class TestErrorMappingInterceptorResolve:
    def test_returns_mapped_status_code(self):
        interceptor = ErrorMappingInterceptor({
            _NotFoundException: grpc.StatusCode.NOT_FOUND,
        })
        assert interceptor._resolve_status_code(_NotFoundException()) == grpc.StatusCode.NOT_FOUND

    def test_returns_internal_for_unmapped_exception(self):
        interceptor = ErrorMappingInterceptor({})
        assert interceptor._resolve_status_code(_UnmappedException()) == grpc.StatusCode.INTERNAL

    def test_supports_subclass_isinstance_check(self):
        """_SubNotFoundException extends _NotFoundException → mapped đúng."""
        interceptor = ErrorMappingInterceptor({
            _NotFoundException: grpc.StatusCode.NOT_FOUND,
        })
        assert interceptor._resolve_status_code(_SubNotFoundException()) == grpc.StatusCode.NOT_FOUND

    def test_multiple_mappings_returns_first_match(self):
        interceptor = ErrorMappingInterceptor({
            _NotFoundException: grpc.StatusCode.NOT_FOUND,
            _ValidationException: grpc.StatusCode.INVALID_ARGUMENT,
        })
        assert interceptor._resolve_status_code(_ValidationException()) == grpc.StatusCode.INVALID_ARGUMENT


# ---------------------------------------------------------------------------
# ErrorMappingInterceptor.intercept_service — handler wrapping
# ---------------------------------------------------------------------------

class TestErrorMappingInterceptorIntercept:
    """
    Dùng grpc public factory functions thay vì grpc.RpcMethodHandler() trực tiếp
    vì trong grpcio >= 1.70 grpc.RpcMethodHandler là ABC.
    Factory: grpc.unary_unary_rpc_method_handler, grpc.unary_stream_rpc_method_handler,
             grpc.stream_unary_rpc_method_handler, grpc.stream_stream_rpc_method_handler.
    """

    @pytest.mark.asyncio
    async def test_returns_none_when_handler_is_none(self):
        async def continuation(details):
            return None

        interceptor = ErrorMappingInterceptor({})
        result = await interceptor.intercept_service(continuation, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_wraps_unary_unary_handler(self):
        async def original(request, context):
            return "response"

        handler = grpc.unary_unary_rpc_method_handler(original)

        async def continuation(details):
            return handler

        interceptor = ErrorMappingInterceptor({})
        result = await interceptor.intercept_service(continuation, MagicMock())
        assert result.unary_unary is not original
        assert result.unary_unary is not None

    @pytest.mark.asyncio
    async def test_wraps_unary_stream_handler(self):
        async def original(request, context):
            yield "item"

        handler = grpc.unary_stream_rpc_method_handler(original)

        async def continuation(details):
            return handler

        interceptor = ErrorMappingInterceptor({})
        result = await interceptor.intercept_service(continuation, MagicMock())
        assert result.unary_stream is not original

    @pytest.mark.asyncio
    async def test_wraps_stream_unary_handler(self):
        async def original(request_iter, context):
            return "response"

        handler = grpc.stream_unary_rpc_method_handler(original)

        async def continuation(details):
            return handler

        interceptor = ErrorMappingInterceptor({})
        result = await interceptor.intercept_service(continuation, MagicMock())
        assert result.stream_unary is not original

    @pytest.mark.asyncio
    async def test_wraps_stream_stream_handler(self):
        async def original(request_iter, context):
            yield "item"

        handler = grpc.stream_stream_rpc_method_handler(original)

        async def continuation(details):
            return handler

        interceptor = ErrorMappingInterceptor({})
        result = await interceptor.intercept_service(continuation, MagicMock())
        assert result.stream_stream is not original

    @pytest.mark.asyncio
    async def test_unary_handler_maps_exception_to_status_code(self):
        async def original(request, context):
            raise _NotFoundException("not found")

        handler = grpc.unary_unary_rpc_method_handler(original)

        async def continuation(details):
            return handler

        mock_context = AsyncMock(spec=grpc.aio.ServicerContext)
        interceptor = ErrorMappingInterceptor({_NotFoundException: grpc.StatusCode.NOT_FOUND})
        result = await interceptor.intercept_service(continuation, MagicMock())
        await result.unary_unary("req", mock_context)

        mock_context.abort.assert_called_once_with(grpc.StatusCode.NOT_FOUND, "not found")

    @pytest.mark.asyncio
    async def test_unary_handler_uses_internal_for_unmapped_exception(self):
        async def original(request, context):
            raise _UnmappedException("boom")

        handler = grpc.unary_unary_rpc_method_handler(original)

        async def continuation(details):
            return handler

        mock_context = AsyncMock(spec=grpc.aio.ServicerContext)
        interceptor = ErrorMappingInterceptor({})
        result = await interceptor.intercept_service(continuation, MagicMock())
        await result.unary_unary("req", mock_context)

        mock_context.abort.assert_called_once_with(grpc.StatusCode.INTERNAL, "boom")

    @pytest.mark.asyncio
    async def test_unary_handler_reraises_rpc_error(self):
        class _FakeRpcError(grpc.RpcError):
            pass

        async def original(request, context):
            raise _FakeRpcError()

        handler = grpc.unary_unary_rpc_method_handler(original)

        async def continuation(details):
            return handler

        mock_context = AsyncMock(spec=grpc.aio.ServicerContext)
        interceptor = ErrorMappingInterceptor({})
        result = await interceptor.intercept_service(continuation, MagicMock())

        with pytest.raises(_FakeRpcError):
            await result.unary_unary("req", mock_context)

        mock_context.abort.assert_not_called()

    @pytest.mark.asyncio
    async def test_unary_handler_returns_response_when_no_exception(self):
        async def original(request, context):
            return "ok"

        handler = grpc.unary_unary_rpc_method_handler(original)

        async def continuation(details):
            return handler

        interceptor = ErrorMappingInterceptor({})
        result = await interceptor.intercept_service(continuation, MagicMock())
        response = await result.unary_unary("req", AsyncMock())
        assert response == "ok"

    @pytest.mark.asyncio
    async def test_streaming_handler_yields_items_when_no_exception(self):
        async def original(request, context):
            yield "a"
            yield "b"

        handler = grpc.unary_stream_rpc_method_handler(original)

        async def continuation(details):
            return handler

        interceptor = ErrorMappingInterceptor({})
        result = await interceptor.intercept_service(continuation, MagicMock())

        items = []
        async for item in result.unary_stream("req", AsyncMock()):
            items.append(item)

        assert items == ["a", "b"]

    @pytest.mark.asyncio
    async def test_streaming_handler_maps_exception_to_status_code(self):
        async def original(request, context):
            yield "first"
            raise _NotFoundException("stream error")

        handler = grpc.unary_stream_rpc_method_handler(original)

        async def continuation(details):
            return handler

        mock_context = AsyncMock(spec=grpc.aio.ServicerContext)
        interceptor = ErrorMappingInterceptor({_NotFoundException: grpc.StatusCode.NOT_FOUND})
        result = await interceptor.intercept_service(continuation, MagicMock())

        items = []
        async for item in result.unary_stream("req", mock_context):
            items.append(item)

        assert items == ["first"]
        mock_context.abort.assert_called_once_with(grpc.StatusCode.NOT_FOUND, "stream error")
