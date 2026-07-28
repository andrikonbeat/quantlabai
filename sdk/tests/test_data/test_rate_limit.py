"""Tests for TokenBucket rate limiter."""

import asyncio
import pytest
from quantlab.data.fundamental.rate_limit import TokenBucket


@pytest.mark.asyncio
async def test_acquire_immediately():
    bucket = TokenBucket(rate=10, capacity=10)
    await bucket.acquire()  # returns None when succeeds


@pytest.mark.asyncio
async def test_acquire_blocks_when_empty():
    bucket = TokenBucket(rate=5, capacity=1)
    await bucket.acquire()  # consumes the only token
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(bucket.acquire(), timeout=0.05)


@pytest.mark.asyncio
async def test_concurrent_acquire():
    bucket = TokenBucket(rate=1000, capacity=10)
    results = await asyncio.gather(
        bucket.acquire(),
        bucket.acquire(),
        bucket.acquire(),
        return_exceptions=True,
    )
    assert all(r is None for r in results)  # None = success


def test_available_tokens():
    bucket = TokenBucket(rate=10, capacity=5)
    assert bucket.available_tokens == 5.0


def test_positive_rate_required():
    with pytest.raises(ValueError):
        TokenBucket(rate=0, capacity=1)


def test_positive_capacity_required():
    with pytest.raises(ValueError):
        TokenBucket(rate=1, capacity=0)
