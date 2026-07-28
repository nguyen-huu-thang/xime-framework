"""
Test FakeTransactionManager and FakeReadOnlyManager:

  __call__():
    - Callable: FakeTransactionManager() can be called
    - Returns an async context manager (has __aenter__ and __aexit__)
    - Multiple calls return independent context objects (not the same instance)

  async with FakeTransactionManager()():
    - __aenter__ returns self (the context object)
    - __aexit__ does not raise on success (exc_type=None)
    - __aexit__ does not suppress exceptions (re-raises)
    - Can be nested without error

  Protocol compatibility:
    - __call__ returns object with __aenter__ and __aexit__ (TransactionContext shape)

  FakeReadOnlyManager (same no-op contract, read-only side):
    - callable, each call returns an independent context
    - async with works, exceptions propagate, nesting is allowed
    - nests inside FakeTransactionManager (a read-only service composing into
      a writing use case must work without a database)
"""
import pytest

from xime.testing import FakeReadOnlyManager, FakeTransactionManager
from xime.testing._fakes import _FakeReadOnlyContext, _FakeTransactionContext


class TestFakeTransactionManagerCall:
    def test_is_callable(self):
        manager = FakeTransactionManager()
        assert callable(manager)

    def test_call_returns_fake_transaction_context(self):
        manager = FakeTransactionManager()
        ctx = manager()
        assert isinstance(ctx, _FakeTransactionContext)

    def test_each_call_returns_new_context_instance(self):
        manager = FakeTransactionManager()
        ctx1 = manager()
        ctx2 = manager()
        assert ctx1 is not ctx2

    def test_returned_context_has_aenter(self):
        ctx = FakeTransactionManager()()
        assert hasattr(ctx, "__aenter__")

    def test_returned_context_has_aexit(self):
        ctx = FakeTransactionManager()()
        assert hasattr(ctx, "__aexit__")


class TestFakeTransactionContext:
    @pytest.mark.asyncio
    async def test_aenter_returns_self(self):
        ctx = FakeTransactionManager()()
        result = await ctx.__aenter__()
        assert result is ctx

    @pytest.mark.asyncio
    async def test_aexit_on_success_does_not_raise(self):
        ctx = FakeTransactionManager()()
        await ctx.__aenter__()
        await ctx.__aexit__(None, None, None)  # no exception

    @pytest.mark.asyncio
    async def test_aexit_on_exception_does_not_raise_but_does_not_suppress(self):
        ctx = FakeTransactionManager()()
        await ctx.__aenter__()
        # __aexit__ returns None (falsy) → exception propagates as normal
        result = await ctx.__aexit__(ValueError, ValueError("boom"), None)
        assert not result  # falsy → exception not suppressed

    @pytest.mark.asyncio
    async def test_async_with_happy_path(self):
        async with FakeTransactionManager()():
            pass  # no error

    @pytest.mark.asyncio
    async def test_exception_inside_async_with_propagates(self):
        with pytest.raises(ValueError, match="test error"):
            async with FakeTransactionManager()():
                raise ValueError("test error")

    @pytest.mark.asyncio
    async def test_nested_async_with_does_not_raise(self):
        manager = FakeTransactionManager()
        async with manager():
            async with manager():
                pass  # nested transactions allowed (no error)

    @pytest.mark.asyncio
    async def test_aenter_returns_self_in_async_with(self):
        manager = FakeTransactionManager()
        async with manager() as ctx:
            assert ctx is not None


class TestFakeReadOnlyManager:
    def test_is_callable(self):
        assert callable(FakeReadOnlyManager())

    def test_call_returns_fake_read_only_context(self):
        assert isinstance(FakeReadOnlyManager()(), _FakeReadOnlyContext)

    def test_each_call_returns_new_context_instance(self):
        manager = FakeReadOnlyManager()
        assert manager() is not manager()

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self):
        ctx = FakeReadOnlyManager()()
        assert await ctx.__aenter__() is ctx

    @pytest.mark.asyncio
    async def test_async_with_happy_path(self):
        async with FakeReadOnlyManager()():
            pass  # no error

    @pytest.mark.asyncio
    async def test_exception_inside_async_with_propagates(self):
        with pytest.raises(ValueError, match="test error"):
            async with FakeReadOnlyManager()():
                raise ValueError("test error")

    @pytest.mark.asyncio
    async def test_nested_async_with_does_not_raise(self):
        manager = FakeReadOnlyManager()
        async with manager():
            async with manager():
                pass  # nested read-only blocks allowed (no error)

    @pytest.mark.asyncio
    async def test_nests_inside_a_fake_transaction(self):
        # Mirrors the real behaviour: a read-only service used from inside a
        # writing use case must work with no database attached.
        async with FakeTransactionManager()():
            async with FakeReadOnlyManager()():
                pass
