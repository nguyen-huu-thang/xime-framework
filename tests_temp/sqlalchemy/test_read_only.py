"""
Test the read-only block (SQLAlchemy starter) — `async with self.read_only():`,
the sibling of `async with self.transaction():` for use cases that only read.

  Reading:
    - repository methods work inside a read-only block
    - a block that reads nothing is harmless
  The core guarantee — a read-only block never commits:
    - an entity changed inside the block does not reach the database
  Entities survive the block (this is what expunge_all() before rollback buys):
    - already-loaded attributes stay readable after the block exits
  Session boundary:
    - the ContextVar is restored on the way out, including when the block raises
    - calling a repo method outside any block still raises RuntimeError
  Nesting (a read-only service composing into a writing use case):
    - inside a transaction: borrows that session, and the transaction still
      commits normally afterwards
    - inside another read-only block: same borrowing behaviour
  Wiring:
    - SqlAlchemyReadOnlyContext satisfies the ReadOnlyContext Protocol
    - only the manager is exported for DI scanning, not the per-block context
    - FakeReadOnlyManager is a working no-op for tests without a database
"""
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.orm import Mapped, mapped_column

from xime.core.bootstrap import Application
from xime.core.config import BindingConfig
from xime.core.config.runtime import RuntimeConfig
from xime.core.transaction import ReadOnlyContext, ReadOnlyManager, TransactionManager
from xime.starters import sqlalchemy as sqlalchemy_starter
from xime.starters.sqlalchemy import (
    AsyncEngineProvider,
    AsyncSessionFactory,
    Base,
    CrudRepository,
    SqlAlchemyReadOnlyManager,
    SqlAlchemyTransactionManager,
)
from xime.testing import FakeReadOnlyManager


class Gadget(Base):
    __tablename__ = "read_only_test_gadgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class GadgetRepository(CrudRepository[Gadget]):
    model = Gadget


class ReadingService:
    """Consumer used by TestDiWiring - mirrors how an app injects both managers."""

    def __init__(
        self,
        read_only: ReadOnlyManager,
        transaction: TransactionManager,
    ) -> None:
        self.read_only = read_only
        self.transaction = transaction


class WriteOnlyService:
    """Consumer written before read-only blocks existed: transaction only."""

    def __init__(self, transaction: TransactionManager) -> None:
        self.transaction = transaction


@pytest_asyncio.fixture
async def stack(tmp_path):
    """Build a real SQLAlchemy stack on a temp-file SQLite DB and create the table.

    A file (not :memory:) is used so the engine's multiple pooled connections
    share the same database.
    """
    db_file = tmp_path / "read_only_test.db"
    config = RuntimeConfig.from_dict(
        {"database": {"url": f"sqlite+aiosqlite:///{db_file.as_posix()}"}}
    )
    provider = AsyncEngineProvider(config)
    async with provider.engine.begin() as conn:
        await conn.run_sync(Gadget.__table__.create)

    sessions = AsyncSessionFactory(provider)
    try:
        yield SimpleNamespace(
            provider=provider,
            sessions=sessions,
            repository=GadgetRepository(sessions),
            transaction=SqlAlchemyTransactionManager(sessions),
            read_only=SqlAlchemyReadOnlyManager(sessions),
        )
    finally:
        await provider.engine.dispose()


async def _insert(stack, name: str) -> int:
    """Write one row through the normal transaction path and return its id."""
    async with stack.transaction():
        gadget = await stack.repository.save(Gadget(name=name))
        return gadget.id


class TestReading:
    @pytest.mark.asyncio
    async def test_repository_methods_work_inside_block(self, stack):
        gadget_id = await _insert(stack, "reader")

        async with stack.read_only():
            assert (await stack.repository.find_or_fail(gadget_id)).name == "reader"
            assert await stack.repository.count() == 1
            assert len(await stack.repository.find_all()) == 1
            assert await stack.repository.exists(gadget_id) is True

    @pytest.mark.asyncio
    async def test_block_that_reads_nothing_is_harmless(self, stack):
        # No statement is ever issued, so SQLAlchemy never autobegins and no
        # connection is checked out. Exiting must still be clean.
        async with stack.read_only():
            pass


class TestConnectionPool:
    """Measures the claim that an empty block costs nothing.

    Documented in readonly.py: no explicit begin() means SQLAlchemy autobegins
    on the first statement, so a block that reads nothing never checks out a
    connection. Asserted here rather than taken on faith.
    """

    @pytest.mark.asyncio
    async def test_empty_block_checks_out_no_connection(self, stack):
        pool = stack.provider.engine.pool
        before = pool.checkedout()

        async with stack.read_only():
            assert pool.checkedout() == before

        assert pool.checkedout() == before

    @pytest.mark.asyncio
    async def test_block_that_reads_checks_out_one_and_returns_it(self, stack):
        pool = stack.provider.engine.pool
        before = pool.checkedout()

        async with stack.read_only():
            await stack.repository.count()
            assert pool.checkedout() == before + 1

        # The connection must go back to the pool when the block ends.
        assert pool.checkedout() == before


class TestNeverCommits:
    @pytest.mark.asyncio
    async def test_entity_changed_inside_block_is_not_persisted(self, stack):
        gadget_id = await _insert(stack, "original")

        async with stack.read_only():
            gadget = await stack.repository.find_or_fail(gadget_id)
            gadget.name = "changed by accident"

        async with stack.read_only():
            reloaded = await stack.repository.find_or_fail(gadget_id)
            assert reloaded.name == "original"

    @pytest.mark.asyncio
    async def test_entity_added_inside_block_is_not_persisted(self, stack):
        async with stack.read_only():
            await stack.repository.save(Gadget(name="should not survive"))

        async with stack.read_only():
            assert await stack.repository.count() == 0


class TestEntitiesSurviveTheBlock:
    @pytest.mark.asyncio
    async def test_loaded_attributes_readable_after_exit(self, stack):
        """Guards the expunge_all()-before-rollback step.

        rollback() expires every object the session still owns, so reading an
        attribute afterwards raises DetachedInstanceError. Detaching first keeps
        the loaded values. Verified by removing that one line: this test and
        test_list_results_readable_after_exit are the two that go red.
        """
        gadget_id = await _insert(stack, "durable")

        async with stack.read_only():
            gadget = await stack.repository.find_or_fail(gadget_id)

        assert gadget.id == gadget_id
        assert gadget.name == "durable"

    @pytest.mark.asyncio
    async def test_list_results_readable_after_exit(self, stack):
        await _insert(stack, "first")
        await _insert(stack, "second")

        async with stack.read_only():
            gadgets = await stack.repository.find_all()

        assert sorted(g.name for g in gadgets) == ["first", "second"]


class TestSessionBoundary:
    @pytest.mark.asyncio
    async def test_context_var_set_inside_and_restored_after(self, stack):
        with pytest.raises(RuntimeError):
            stack.sessions.current()

        async with stack.read_only():
            assert stack.sessions.current() is not None

        with pytest.raises(RuntimeError):
            stack.sessions.current()

    @pytest.mark.asyncio
    async def test_context_var_restored_when_block_raises(self, stack):
        with pytest.raises(ValueError, match="boom"):
            async with stack.read_only():
                await stack.repository.count()
                raise ValueError("boom")

        with pytest.raises(RuntimeError):
            stack.sessions.current()

    @pytest.mark.asyncio
    async def test_repository_outside_any_block_still_raises(self, stack):
        # Backward compatibility: nothing about the old error path changed.
        with pytest.raises(RuntimeError, match="No active database session"):
            await stack.repository.count()


class TestNesting:
    @pytest.mark.asyncio
    async def test_inside_transaction_borrows_the_same_session(self, stack):
        gadget_id = await _insert(stack, "outer")

        async with stack.transaction():
            outer_session = stack.sessions.current()
            async with stack.read_only():
                assert stack.sessions.current() is outer_session
                found = await stack.repository.find_or_fail(gadget_id)
            assert stack.sessions.current() is outer_session
            assert found.name == "outer"

    @pytest.mark.asyncio
    async def test_transaction_still_commits_after_nested_block(self, stack):
        async with stack.transaction():
            first = await stack.repository.save(Gadget(name="before"))
            async with stack.read_only():
                assert await stack.repository.find_or_fail(first.id) is first
            # The nested block must not have closed the transaction's session.
            await stack.repository.save(Gadget(name="after"))

        async with stack.read_only():
            assert await stack.repository.count() == 2

    @pytest.mark.asyncio
    async def test_read_only_inside_read_only(self, stack):
        gadget_id = await _insert(stack, "nested")

        async with stack.read_only():
            outer_session = stack.sessions.current()
            async with stack.read_only():
                assert stack.sessions.current() is outer_session
                await stack.repository.find_or_fail(gadget_id)
            # Inner exit must leave the outer block usable.
            assert stack.sessions.current() is outer_session
            assert await stack.repository.count() == 1

        with pytest.raises(RuntimeError):
            stack.sessions.current()


class TestWiring:
    @pytest.mark.asyncio
    async def test_context_satisfies_protocol(self, stack):
        context = stack.read_only()
        assert isinstance(context, ReadOnlyContext)

    def test_manager_matches_protocol_shape(self, stack):
        manager: ReadOnlyManager = stack.read_only
        assert callable(manager)

    def test_only_the_manager_is_exported_for_scanning(self):
        assert "SqlAlchemyReadOnlyManager" in sqlalchemy_starter.__all__
        # The per-block context is not a singleton — it must stay out of __all__.
        assert "SqlAlchemyReadOnlyContext" not in sqlalchemy_starter.__all__

    @pytest.mark.asyncio
    async def test_fake_manager_is_a_working_no_op(self):
        fake = FakeReadOnlyManager()
        async with fake():
            pass  # no database involved

        context = fake()
        assert isinstance(context, ReadOnlyContext)


class TestDiWiring:
    """Boots a real Application with the binding the docs tell apps to write.

    Everything above builds the managers by hand; this is the only test that
    proves the Protocol binding actually resolves through the container and
    survives startup validation.
    """

    @staticmethod
    def _resources(tmp_path) -> str:
        resources = tmp_path / "resources"
        resources.mkdir()
        db_file = tmp_path / "di_wiring.db"
        (resources / "application.yml").write_text(
            f"database:\n  url: sqlite+aiosqlite:///{db_file.as_posix()}\n",
            encoding="utf-8",
        )
        return str(resources)

    @pytest.mark.asyncio
    async def test_both_managers_inject_into_a_service(self, tmp_path):
        binding = BindingConfig()
        binding.scan("xime.starters.sqlalchemy")
        binding.register(ReadingService)
        binding.bind(
            {
                TransactionManager: SqlAlchemyTransactionManager,
                ReadOnlyManager: SqlAlchemyReadOnlyManager,
            }
        )

        async with Application(
            binding=binding, resources_dir=self._resources(tmp_path)
        ) as app:
            service = app.get(ReadingService)

            assert isinstance(service.read_only, SqlAlchemyReadOnlyManager)
            assert isinstance(service.transaction, SqlAlchemyTransactionManager)
            # Both must share one session factory, otherwise a read-only block
            # nested in a transaction would not see the enclosing session.
            assert service.read_only._factory is service.transaction._factory

    @pytest.mark.asyncio
    async def test_app_without_the_read_only_binding_still_starts(self, tmp_path):
        # Backward compatibility: ReadOnlyManager is opt-in. An app written
        # before this feature binds only TransactionManager and must be fine.
        binding = BindingConfig()
        binding.scan("xime.starters.sqlalchemy")
        binding.register(WriteOnlyService)
        binding.bind({TransactionManager: SqlAlchemyTransactionManager})

        async with Application(
            binding=binding, resources_dir=self._resources(tmp_path)
        ) as app:
            service = app.get(WriteOnlyService)
            assert isinstance(service.transaction, SqlAlchemyTransactionManager)
