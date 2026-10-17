"""Fault injection checks ownership, error precedence, and session restoration."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from xime.starters.sqlalchemy.readonly import SqlAlchemyReadOnlyContext
from xime.starters.sqlalchemy.session import _current_session
from xime.starters.sqlalchemy.transaction import SqlAlchemyTransactionContext


def _context(kind):
    session = Mock(spec=AsyncSession)
    for method in ("begin", "commit", "rollback", "close"):
        setattr(session, method, AsyncMock())
    factory = Mock()
    factory.create.return_value = session
    context = (
        SqlAlchemyTransactionContext(session) if kind == "transaction"
        else SqlAlchemyReadOnlyContext(factory)
    )
    return context, session, factory


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["transaction", "read_only"])
@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_close_failure_restores_context_and_next_unit_of_work(kind, failure):
    context, session, _ = _context(kind)
    session.close.side_effect = failure("close failed")
    with pytest.raises(failure):
        async with context:
            assert _current_session.get() is session
    assert _current_session.get() is None
    assert context._token is None
    if kind == "read_only":
        assert context._session is None
    next_context, next_session, _ = _context(kind)
    async with next_context:
        assert _current_session.get() is next_session
    assert _current_session.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["transaction", "read_only"])
@pytest.mark.parametrize("operation", ["rollback", "close"])
async def test_cleanup_failure_preserves_body_error(kind, operation, caplog):
    context, session, _ = _context(kind)
    getattr(session, operation).side_effect = RuntimeError("cleanup failed")
    original = ValueError("business failed")
    with pytest.raises(ValueError) as caught:
        async with context:
            raise original
    assert caught.value is original
    assert _current_session.get() is None
    assert operation in caplog.text
    assert any(operation in note for note in original.__notes__)
    session.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["begin", "commit", "rollback"])
async def test_transaction_operation_error_survives_close_error(operation):
    context, session, _ = _context("transaction")
    original = RuntimeError(operation)
    getattr(session, operation).side_effect = original
    session.close.side_effect = ValueError("close")
    body = RuntimeError("body") if operation == "rollback" else None
    with pytest.raises(RuntimeError) as caught:
        async with context:
            if body is not None:
                raise body
    assert caught.value is (body or original)
    session.close.assert_awaited_once()
    assert _current_session.get() is None
    assert context._token is None


@pytest.mark.asyncio
async def test_transaction_close_failure_restores_outer_session():
    outer = Mock(spec=AsyncSession)
    token = _current_session.set(outer)
    try:
        context, session, _ = _context("transaction")
        session.close.side_effect = RuntimeError("close")
        with pytest.raises(RuntimeError):
            async with context:
                assert _current_session.get() is session
        assert _current_session.get() is outer
    finally:
        _current_session.reset(token)


@pytest.mark.asyncio
async def test_borrowed_read_only_does_not_close_outer_session():
    outer = Mock(spec=AsyncSession)
    token = _current_session.set(outer)
    try:
        context, session, factory = _context("read_only")
        with pytest.raises(ValueError):
            async with context:
                assert _current_session.get() is outer
                raise ValueError("body")
        factory.create.assert_not_called()
        session.close.assert_not_awaited()
        outer.close.assert_not_called()
        assert _current_session.get() is outer
    finally:
        _current_session.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["transaction", "read_only"])
async def test_cancellation_at_close_is_not_swallowed_by_an_existing_error(kind):
    context, session, _ = _context(kind)
    session.close.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        async with context:
            raise ValueError("body")
    assert _current_session.get() is None
