from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from xime.core.config.runtime import RuntimeConfig
from xime.starters.lmdb import LmdbEnvironment, store_registry


@pytest.fixture
def store_root(tmp_path) -> str:
    """A private store directory per test, so tables never leak between tests."""
    return str(tmp_path / "store")


@pytest.fixture
def runtime(store_root: str) -> RuntimeConfig:
    # Small sizes on purpose: a few tests need to reach the ceiling, and on
    # Windows an LMDB file is allocated for real the moment it opens.
    return RuntimeConfig.from_dict(
        {"lmdb": {"path": store_root, "map_size": "1MB", "total_max": "32MB"}}
    )


@pytest_asyncio.fixture
async def env(runtime: RuntimeConfig) -> AsyncIterator[LmdbEnvironment]:
    environment = LmdbEnvironment(runtime)
    yield environment
    await environment.pre_destroy()
    store_registry.reset()
