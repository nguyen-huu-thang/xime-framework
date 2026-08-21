"""
Test CrudRepository (SQLAlchemy starter) - the generic base repository giving
apps find/find_all/find_or_fail/exists/count/save/save_all/delete for free.

  CRUD round-trip (against a temp-file SQLite DB, inside a transaction):
    - save assigns the generated primary key and find reads it back
    - find_all / count reflect the rows present
    - exists is True/False for present/absent ids
    - find_or_fail returns the row, or raises EntityNotFoundError when absent
    - save_all inserts several rows in one flush
    - delete removes the row
  DI eligibility:
    - CrudRepository itself is abstract → PackageScanner skips it
    - a concrete subclass that sets `model` IS eligible
  Session boundary:
    - calling a repo method outside any block (transaction or read-only) raises
      RuntimeError
"""
import pytest
import pytest_asyncio
from sqlalchemy.orm import Mapped, mapped_column

from xime.core.config.runtime import RuntimeConfig
from xime.core.container.scanner import PackageScanner
from xime.core.metadata.type_utils import is_abstract
from xime.starters.sqlalchemy import (
    AsyncEngineProvider,
    AsyncSessionFactory,
    Base,
    CrudRepository,
    EntityNotFoundError,
    SqlAlchemyTransactionManager,
)


class Widget(Base):
    __tablename__ = "crud_test_widgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class WidgetRepository(CrudRepository[Widget]):
    model = Widget


@pytest_asyncio.fixture
async def repo_and_tx(tmp_path):
    """Build a real SQLAlchemy stack on a temp-file SQLite DB and create the table.

    A file (not :memory:) is used so the engine's multiple pooled connections
    share the same database.
    """
    db_file = tmp_path / "crud_test.db"
    config = RuntimeConfig.from_dict(
        {"database": {"url": f"sqlite+aiosqlite:///{db_file.as_posix()}"}}
    )
    provider = AsyncEngineProvider(config)
    async with provider.engine.begin() as conn:
        await conn.run_sync(Widget.__table__.create)

    sessions = AsyncSessionFactory(provider)
    transaction = SqlAlchemyTransactionManager(sessions)
    repository = WidgetRepository(sessions)
    try:
        yield repository, transaction
    finally:
        await provider.engine.dispose()


@pytest.mark.asyncio
async def test_save_assigns_id_and_find_reads_back(repo_and_tx):
    repo, tx = repo_and_tx
    async with tx():
        saved = await repo.save(Widget(name="alpha"))
        assert saved.id is not None

    async with tx():
        found = await repo.find(saved.id)
        assert found is not None
        assert found.name == "alpha"


@pytest.mark.asyncio
async def test_find_all_and_count(repo_and_tx):
    repo, tx = repo_and_tx
    async with tx():
        await repo.save(Widget(name="a"))
        await repo.save(Widget(name="b"))

    async with tx():
        rows = await repo.find_all()
        assert {w.name for w in rows} == {"a", "b"}
        assert await repo.count() == 2


@pytest.mark.asyncio
async def test_exists(repo_and_tx):
    repo, tx = repo_and_tx
    async with tx():
        saved = await repo.save(Widget(name="here"))

    async with tx():
        assert await repo.exists(saved.id) is True
        assert await repo.exists(999_999) is False


@pytest.mark.asyncio
async def test_find_or_fail(repo_and_tx):
    repo, tx = repo_and_tx
    async with tx():
        saved = await repo.save(Widget(name="present"))

    async with tx():
        got = await repo.find_or_fail(saved.id)
        assert got.id == saved.id

    async with tx():
        with pytest.raises(EntityNotFoundError) as exc:
            await repo.find_or_fail(123_456)
    assert exc.value.model_name == "Widget"
    assert exc.value.id == 123_456


@pytest.mark.asyncio
async def test_save_all(repo_and_tx):
    repo, tx = repo_and_tx
    async with tx():
        saved = await repo.save_all([Widget(name="x"), Widget(name="y"), Widget(name="z")])
        assert len(saved) == 3
        assert all(w.id is not None for w in saved)

    async with tx():
        assert await repo.count() == 3


@pytest.mark.asyncio
async def test_delete(repo_and_tx):
    repo, tx = repo_and_tx
    async with tx():
        saved = await repo.save(Widget(name="doomed"))

    async with tx():
        entity = await repo.find(saved.id)
        await repo.delete(entity)

    async with tx():
        assert await repo.find(saved.id) is None
        assert await repo.count() == 0


def test_base_is_abstract_and_scanner_skips_it():
    # CrudRepository declares `model` as an abstract property → abstract base.
    assert is_abstract(CrudRepository) is True

    scanner = PackageScanner()
    # The abstract base must be skipped …
    assert scanner._is_eligible(CrudRepository) is False
    # … but a concrete subclass that sets `model` is registered normally.
    assert is_abstract(WidgetRepository) is False
    assert scanner._is_eligible(WidgetRepository) is True


@pytest.mark.asyncio
async def test_method_outside_transaction_raises(repo_and_tx):
    repo, _tx = repo_and_tx
    with pytest.raises(RuntimeError):
        await repo.find(1)
