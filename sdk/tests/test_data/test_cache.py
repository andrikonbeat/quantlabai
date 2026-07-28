"""Tests for SqliteCache."""

import pytest
import time
from pathlib import Path

from quantlab.data.fundamental.cache import SqliteCache


@pytest.mark.asyncio
async def test_set_and_get(tmp_path: Path):
    cache = SqliteCache(db_path=str(tmp_path / "cache.db"))
    await cache.set("key1", {"value": 42}, ttl=300)
    result = await cache.get("key1")
    assert result == {"value": 42}


@pytest.mark.asyncio
async def test_get_miss(tmp_path: Path):
    cache = SqliteCache(db_path=str(tmp_path / "cache.db"))
    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_ttl_expiry(tmp_path: Path):
    """Very short TTL means expired after sleeping past it."""
    cache = SqliteCache(db_path=str(tmp_path / "cache.db"))
    await cache.set("key1", {"data": "x"}, ttl=0.1)  # 100ms TTL
    import asyncio
    await asyncio.sleep(0.15)  # Sleep past expiry
    result = await cache.get("key1")
    assert result is None


@pytest.mark.asyncio
async def test_clear(tmp_path: Path):
    cache = SqliteCache(db_path=str(tmp_path / "cache.db"))
    await cache.set("a", {"val": 1}, ttl=300)
    await cache.set("b", {"val": 2}, ttl=300)
    await cache.clear()
    assert await cache.get("a") is None
    assert await cache.get("b") is None


@pytest.mark.asyncio
async def test_overwrite(tmp_path: Path):
    cache = SqliteCache(db_path=str(tmp_path / "cache.db"))
    await cache.set("k", {"val": "old"}, ttl=300)
    await cache.set("k", {"val": "new"}, ttl=300)
    assert await cache.get("k") == {"val": "new"}


@pytest.mark.asyncio
async def test_default_ttl(tmp_path: Path):
    cache = SqliteCache(db_path=str(tmp_path / "cache.db"), default_ttl=3600)
    await cache.set("k", {"val": 1})  # no ttl → uses default_ttl
    result = await cache.get("k")
    assert result == {"val": 1}


@pytest.mark.asyncio
async def test_persistence(tmp_path: Path):
    db = tmp_path / "persist.db"
    cache = SqliteCache(db_path=str(db))
    await cache.set("persist", {"val": 99}, ttl=300)
    # Re-open same DB
    cache2 = SqliteCache(db_path=str(db))
    assert await cache2.get("persist") == {"val": 99}
