"""Tests for PipelineRunner retry logic and StageStatus.RETRYING."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from quantlab.pipeline.base import Pipeline, PipelineContext, Stage
from quantlab.pipeline.runner import PipelineRunner
from quantlab.pipeline.models import StageStatus, StageResult, PipelineResult


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


class TestPipelineRunnerRetry:
    """Tests for retry logic in PipelineRunner."""

    @pytest.mark.asyncio
    async def test_runner_no_retry_by_default(self):
        """Default runner should not retry - fail on first attempt."""
        # We need to add retry logic to runner first
        runner = PipelineRunner()
        pipeline = Pipeline("test").then(RetryableStage(fail_count=1))
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        # Should fail on first attempt (no retry logic yet)
        assert result.is_successful is False
        assert result.stages[0].status == StageStatus.FAILED

    @pytest.mark.xfail(reason="PipelineRunner does not yet support retry params")
    @pytest.mark.asyncio
    async def test_runner_with_retry_config(self):
        """Runner with retry config should retry failed stages."""
        runner = PipelineRunner(max_retries=3, retry_delay=0.01)
        pipeline = Pipeline("test").then(RetryableStage(fail_count=2))
        ctx = PipelineContext(config={})

        result = await runner.run(pipeline, ctx)

        assert result.is_successful is True
        assert result.stages[0].status == StageStatus.COMPLETED
        # Verify it was retried
        assert ctx.artifacts["retry_result"] == "success_on_attempt_3"


class TestStageStatusRetrying:
    """Tests for StageStatus.RETRYING enum value."""

    def test_retrying_status_exists(self):
        """StageStatus should have RETRYING value."""
        assert hasattr(StageStatus, "RETRYING")
        assert StageStatus.RETRYING.value == "retrying"


class TestRetryWithExponentialBackoff:
    """Tests for exponential backoff retry behavior."""

    @pytest.mark.xfail(reason="Exponential backoff not yet implemented in PipelineRunner")
    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Retries should use exponential backoff: 1s, 2s, 4s, ..."""
        pytest.fail("Not yet implemented")

    @pytest.mark.xfail(reason="Max retries exceeded logic not yet implemented in PipelineRunner")
    @pytest.mark.asyncio
    async def test_max_retries_exceeded_fails(self):
        """After max_retries, stage should be marked FAILED."""
        pytest.fail("Not yet implemented")


class TestRetryIntegration:
    """Integration tests for retry with pipeline execution."""

    @pytest.mark.xfail(reason="Retry integration not yet implemented in PipelineRunner")
    @pytest.mark.asyncio
    async def test_retry_stage_then_continue_pipeline(self):
        """Retried stage succeeds, pipeline continues to next stages."""
        pytest.fail("Not yet implemented")

    @pytest.mark.xfail(reason="Retry integration not yet implemented in PipelineRunner")
    @pytest.mark.asyncio
    async def test_retry_exhausted_stops_pipeline(self):
        """Stage fails after max retries, pipeline stops (remaining SKIPPED)."""
        pytest.fail("Not yet implemented")