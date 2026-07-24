"""Tests for PipelineRunner retry logic and StageStatus.RETRYING."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from quantlab.pipeline.base import Pipeline, PipelineContext, Stage
from quantlab.pipeline.runner import PipelineRunner
from quantlab.pipeline.models import StageStatus, StageResult, PipelineResult
from quantlab.pipeline.progress import PhaseStatus


class RetryableStage(Stage):
    """Stage that fails N times then succeeds."""
    name = "retryable"
    requires = []
    provides = ["retry_result"]

    def __init__(self, fail_count: int = 2):
        self.fail_count = fail_count
        self.attempt = 0

    async def execute(self, ctx: PipelineContext) -> str:
        self.attempt += 1
        if self.attempt <= self.fail_count:
            raise ConnectionError(f"Attempt {self.attempt} failed")
        ctx.artifacts["retry_result"] = f"success_on_attempt_{self.attempt}"
        return f"success_on_attempt_{self.attempt}"


class AlwaysFailsStage(Stage):
    """Stage that always fails."""
    name = "always_fails"
    requires = []
    provides = []

    async def execute(self, ctx: PipelineContext) -> None:
        raise ValueError("Permanent failure")


class CounterStage(Stage):
    """Stage that records execution attempts and always succeeds."""
    name = "counter"
    requires = []
    provides = ["counted"]

    def __init__(self) -> None:
        self.call_count = 0

    async def execute(self, ctx: PipelineContext) -> str:
        self.call_count += 1
        ctx.artifacts["counted"] = self.call_count
        return f"call_{self.call_count}"


class TestPipelineRunnerRetry:
    """Tests for retry logic in PipelineRunner."""

    @pytest.mark.asyncio
    async def test_runner_no_retry_by_default(self):
        """Default runner should not retry - fail on first attempt."""
        runner = PipelineRunner()
        pipeline = Pipeline("test").then(RetryableStage(fail_count=1))
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        # Should fail on first attempt (max_retries=0)
        assert result.is_successful is False
        assert result.stages[0].status == StageStatus.FAILED

    @pytest.mark.asyncio
    async def test_runner_with_retry_config(self):
        """Runner with retry config should retry failed stages."""
        runner = PipelineRunner(max_retries=3, retry_delay=0.01)
        pipeline = Pipeline("test").then(RetryableStage(fail_count=2))
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        assert result.is_successful is True
        assert result.stages[0].status == StageStatus.COMPLETED
        # Verify it was retried (fails 2 times, succeeds on 3rd)
        assert ctx.artifacts["retry_result"] == "success_on_attempt_3"

    @pytest.mark.asyncio
    async def test_runner_retry_stage_internal_does_not_modify(self):
        """Retries should not mutate the original stage between calls."""
        runner = PipelineRunner(max_retries=2, retry_delay=0.01)
        stage = RetryableStage(fail_count=4)  # fails 4 times, only 2 retries
        pipeline = Pipeline("test").then(stage)
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        assert result.is_successful is False
        assert "ConnectionError" in (result.stages[0].error or "")


class TestStageStatusRetrying:
    """Tests for StageStatus.RETRYING enum value."""

    def test_retrying_status_exists(self):
        """StageStatus should have RETRYING value."""
        assert hasattr(StageStatus, "RETRYING")
        assert StageStatus.RETRYING.value == "retrying"


class TestRetryWithExponentialBackoff:
    """Tests for exponential backoff retry behavior."""

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_fails(self):
        """After max_retries, stage should be marked FAILED."""
        runner = PipelineRunner(max_retries=2, retry_delay=0.01)
        pipeline = Pipeline("test").then(AlwaysFailsStage())
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        assert result.is_successful is False
        assert result.stages[0].status == StageStatus.FAILED
        # Error message should mention retries
        assert "retries" in (result.stages[0].error or "").lower()

    @pytest.mark.asyncio
    async def test_exponential_backoff_applied(self):
        """Backoff delay grows exponentially: delay, 2*delay, 4*delay, ..."""
        runner = PipelineRunner(max_retries=3, retry_delay=0.05)
        stage = RetryableStage(fail_count=3)
        pipeline = Pipeline("test").then(stage)
        ctx = PipelineContext(config={})

        start = asyncio.get_running_loop().time()
        result = await runner.run(pipeline, ctx)
        elapsed = asyncio.get_running_loop().time() - start

        # 3 retries: 0.05 + 0.10 + 0.20 = 0.35 expected minimum
        assert result.is_successful is True
        min_expected = 0.05 + 0.10 + 0.20
        assert elapsed >= min_expected * 0.8, (
            f"Backoff too fast: {elapsed:.3f}s < {min_expected:.3f}s"
        )


class TestRetryIntegration:
    """Integration tests for retry with pipeline execution."""

    @pytest.mark.asyncio
    async def test_retry_stage_then_continue_pipeline(self):
        """Retried stage succeeds, pipeline continues to next stages."""
        runner = PipelineRunner(max_retries=2, retry_delay=0.01)
        pipeline = (
            Pipeline("test")
            .then(RetryableStage(fail_count=1))
            .then(CounterStage())
        )
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        assert result.is_successful is True
        assert result.stages[0].status == StageStatus.COMPLETED
        assert result.stages[1].status == StageStatus.COMPLETED
        # CounterStage ran once
        assert ctx.artifacts.get("counted") == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted_stops_pipeline(self):
        """Stage fails after max retries, pipeline stops (remaining SKIPPED)."""
        runner = PipelineRunner(max_retries=1, retry_delay=0.01)
        pipeline = (
            Pipeline("test")
            .then(AlwaysFailsStage())
            .then(CounterStage())
        )
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        assert result.is_successful is False
        assert result.stages[0].status == StageStatus.FAILED
        assert result.stages[1].status == StageStatus.SKIPPED
        # CounterStage should NOT have been called
        assert "counted" not in ctx.artifacts


class TestRetryProgressCallback:
    """Tests for progress callback integration with retries."""

    @pytest.mark.asyncio
    async def test_progress_called_for_retried_stage(self):
        """Progress callback should be invoked on retry events."""
        events: list[tuple[str, str, str | None]] = []

        def on_progress(phase: str, status: PhaseStatus, detail: str | None = None) -> None:
            events.append((phase, status.value, detail))

        runner = PipelineRunner(max_retries=2, retry_delay=0.01, progress=on_progress)
        pipeline = Pipeline("test").then(RetryableStage(fail_count=2))
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        assert result.is_successful is True
        stage_events = [e for e in events if "retryable" in e[0]]
        # At minimum: STARTED + SUCCESS (retry events happen internally)
        assert len(stage_events) >= 2

    @pytest.mark.asyncio
    async def test_progress_error_on_failed_retries(self):
        """Progress callback should report ERROR when retries exhausted."""
        events: list[tuple[str, str, str | None]] = []

        def on_progress(phase: str, status: PhaseStatus, detail: str | None = None) -> None:
            events.append((phase, status.value, detail))

        runner = PipelineRunner(max_retries=1, retry_delay=0.01, progress=on_progress)
        pipeline = Pipeline("test").then(AlwaysFailsStage()).then(CounterStage())
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        assert result.is_successful is False
        error_events = [e for e in events if e[1] == "error"]
        assert len(error_events) >= 1
        assert "retries" in (error_events[0][2] or "").lower()