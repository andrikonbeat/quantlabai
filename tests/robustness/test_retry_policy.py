"""Tests for RetryPolicy — backoff timing, jitter, max_delay cap, async retry()."""

import asyncio
import time

import pytest

from quantlab.robustness.retry_policy import RetryPolicy


class TestRetryPolicyConfiguration:
    """RetryPolicy default and custom configuration."""

    def test_default_policy(self):
        rp = RetryPolicy()
        assert rp.max_retries == 3
        assert rp.base_delay == 1.0
        assert rp.max_delay == 60.0
        assert rp.jitter is True

    def test_custom_policy(self):
        rp = RetryPolicy(max_retries=5, base_delay=2.0, max_delay=30.0, jitter=False)
        assert rp.max_retries == 5
        assert rp.base_delay == 2.0
        assert rp.max_delay == 30.0
        assert rp.jitter is False


class TestRetryPolicyBackoffProgression:
    """Exponential backoff: delay = min(base_delay * 2^attempt, max_delay)."""

    @pytest.mark.asyncio
    async def test_backoff_progression(self):
        rp = RetryPolicy(base_delay=1.0, max_delay=60.0, jitter=False)
        delays = []

        async def fail_once_then_succeed():
            if len(delays) < 2:
                delays.append(rp._compute_delay(len(delays)))
                raise RuntimeError("transient")
            return "success"

        result = await rp.retry(fail_once_then_succeed)
        assert result == "success"
        assert len(delays) == 2
        assert delays[0] == 1.0
        assert delays[1] == 2.0

    @pytest.mark.asyncio
    async def test_backoff_uses_exponential_growth(self):
        rp = RetryPolicy(base_delay=1.0, max_delay=60.0, jitter=False)
        delays = []

        async def fail_three_times():
            idx = len(delays)
            delays.append(rp._compute_delay(idx))
            raise RuntimeError("transient")

        with pytest.raises(RuntimeError):
            await rp.retry(fail_three_times, max_retries=2)
        assert delays == [1.0, 2.0, 4.0]


class TestRetryPolicyMaxDelayCap:
    """Delay is capped at max_delay regardless of exponential growth."""

    def test_delay_capped_at_max_delay(self):
        rp = RetryPolicy(base_delay=1.0, max_delay=10.0, jitter=False)
        # Attempt 10 would be base_delay * 2^10 = 1024, but capped at 10
        delay = rp._compute_delay(10)
        assert delay == 10.0

    @pytest.mark.asyncio
    async def test_max_delay_cap_in_retry(self):
        rp = RetryPolicy(base_delay=1.0, max_delay=5.0, jitter=False)
        delays = []

        async def fail_many_times():
            idx = len(delays)
            delays.append(rp._compute_delay(idx))
            raise RuntimeError("transient")

        with pytest.raises(RuntimeError):
            await rp.retry(fail_many_times, max_retries=10)
        for d in delays:
            assert d <= 5.0


class TestRetryPolicyJitter:
    """Jitter is added to each backoff delay in range [0, delay * 0.3]."""

    @pytest.mark.asyncio
    async def test_jitter_in_range(self):
        rp = RetryPolicy(base_delay=2.0, max_delay=60.0, jitter=True)
        delays = []

        for attempt in range(5):
            delay = rp._compute_delay(attempt)
            delays.append(delay)
            # Jitter range is [base_delay * 2^attempt, base_delay * 2^attempt * 1.3]
            expected_base = 2.0 * (2**attempt)
            assert delay >= expected_base
            assert delay <= expected_base * 1.3

    @pytest.mark.asyncio
    async def test_no_jitter_when_disabled(self):
        rp = RetryPolicy(base_delay=2.0, max_delay=60.0, jitter=False)
        delay = rp._compute_delay(1)
        assert delay == 4.0

    @pytest.mark.asyncio
    async def test_jitter_range_for_base_delay_2(self):
        rp = RetryPolicy(base_delay=2.0, max_delay=60.0, jitter=True)
        # With base_delay=2, attempt=0: delay in [2.0, 2.6]
        delays = [rp._compute_delay(0) for _ in range(20)]
        for d in delays:
            assert 2.0 <= d <= 2.6


class TestRetryPolicyAsyncRetry:
    """async retry() method for async coroutines."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failures(self):
        rp = RetryPolicy(max_retries=3, base_delay=0.01, max_delay=1.0, jitter=False)
        attempts = 0

        async def flaky():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("transient")
            return "success"

        result = await rp.retry(flaky)
        assert result == "success"
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_retry_exhausts_max_retries(self):
        rp = RetryPolicy(max_retries=2, base_delay=0.01, max_delay=1.0, jitter=False)
        attempts = 0

        async def always_fails():
            nonlocal attempts
            attempts += 1
            raise RuntimeError("permanent")

        with pytest.raises(RuntimeError, match="permanent"):
            await rp.retry(always_fails)
        assert attempts == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_immediate_success(self):
        rp = RetryPolicy(max_retries=3, base_delay=0.01, max_delay=1.0, jitter=False)

        async def succeeds():
            return "ok"

        result = await rp.retry(succeeds)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_preserves_exception(self):
        rp = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=1.0, jitter=False)

        async def fails():
            raise ValueError("specific error")

        with pytest.raises(ValueError, match="specific error"):
            await rp.retry(fails)


class TestRetryPolicyJitterEdgeCases:
    """Additional jitter edge cases and statistical distribution checks."""

    @pytest.mark.asyncio
    async def test_jitter_produces_different_delays(self):
        """GIVEN jitter enabled, WHEN computing delays for the same attempt
        multiple times, THEN the delays vary (not all identical)."""
        rp = RetryPolicy(base_delay=2.0, max_delay=60.0, jitter=True)
        delays = [rp._compute_delay(0) for _ in range(50)]
        # With jitter, not all delays should be identical
        assert len(set(delays)) > 1
        # All delays should be in the valid range [2.0, 2.6]
        for d in delays:
            assert 2.0 <= d <= 2.6

    @pytest.mark.asyncio
    async def test_jitter_disabled_produces_identical_delays(self):
        """GIVEN jitter disabled, WHEN computing delays for the same attempt
        multiple times, THEN all delays are identical."""
        rp = RetryPolicy(base_delay=2.0, max_delay=60.0, jitter=False)
        delays = [rp._compute_delay(1) for _ in range(20)]
        assert len(set(delays)) == 1
        assert delays[0] == 4.0

    @pytest.mark.asyncio
    async def test_jitter_range_starts_at_base_delay(self):
        """GIVEN jitter enabled, WHEN computing delay for attempt 0,
        THEN the delay is in [base_delay, base_delay * 1.3]."""
        rp = RetryPolicy(base_delay=3.0, max_delay=60.0, jitter=True)
        delays = [rp._compute_delay(0) for _ in range(30)]
        for d in delays:
            assert 3.0 <= d <= 3.9  # [3.0, 3.0 * 1.3]


class TestRetryPolicyMaxDelayEdgeCases:
    """Max delay cap edge cases."""

    @pytest.mark.asyncio
    async def test_max_delay_cap_with_large_attempt(self):
        """GIVEN base_delay=1 and max_delay=5, WHEN attempt 100 fails,
        THEN delay is capped at 5.0 (not 2^100)."""
        rp = RetryPolicy(base_delay=1.0, max_delay=5.0, jitter=False)
        delay = rp._compute_delay(100)
        assert delay == 5.0

    @pytest.mark.asyncio
    async def test_max_delay_cap_with_zero_base(self):
        """GIVEN base_delay=0 and max_delay=10, WHEN attempt 5 fails,
        THEN delay is 0 (capped by base, not max)."""
        rp = RetryPolicy(base_delay=0.0, max_delay=10.0, jitter=False)
        delay = rp._compute_delay(5)
        assert delay == 0.0


class TestRetryPolicyAsyncRetryEdgeCases:
    """async retry() edge cases."""

    @pytest.mark.asyncio
    async def test_retry_with_custom_max_retries_overrides_policy(self):
        """GIVEN a policy with max_retries=1, WHEN retry() is called with
        max_retries=5, THEN up to 5 attempts are made."""
        rp = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=1.0, jitter=False)
        attempts = 0

        async def flaky():
            nonlocal attempts
            attempts += 1
            if attempts < 4:
                raise RuntimeError("transient")
            return "success"

        result = await rp.retry(flaky, max_retries=5)
        assert result == "success"
        assert attempts == 4

    @pytest.mark.asyncio
    async def test_retry_preserves_original_exception_type(self):
        """GIVEN a ValueError, WHEN all retries are exhausted,
        THEN the original ValueError is raised (not a generic Exception)."""
        rp = RetryPolicy(max_retries=2, base_delay=0.01, max_delay=1.0, jitter=False)

        async def fails_with_value_error():
            raise ValueError("original error")

        with pytest.raises(ValueError, match="original error"):
            await rp.retry(fails_with_value_error)

    @pytest.mark.asyncio
    async def test_retry_zero_max_retries(self):
        """GIVEN max_retries=0, WHEN a call fails, THEN no retries are attempted
        and the exception is raised immediately."""
        rp = RetryPolicy(max_retries=0, base_delay=0.01, max_delay=1.0, jitter=False)

        async def always_fails():
            raise RuntimeError("immediate failure")

        with pytest.raises(RuntimeError, match="immediate failure"):
            await rp.retry(always_fails)
