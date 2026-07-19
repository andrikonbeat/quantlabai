"""Tests for PipelineRunner."""

import pytest
from quantlab.pipeline.base import Pipeline, PipelineContext, Stage
from quantlab.pipeline.runner import PipelineRunner
from quantlab.pipeline.models import StageStatus


class SuccessStage(Stage):
    name = "success"
    requires = []
    provides = ["value"]
    
    async def execute(self, ctx):
        ctx.artifacts["value"] = "done"
        return "done"


class FailStage(Stage):
    name = "fail"
    requires = []
    provides = []
    
    async def execute(self, ctx):
        raise ValueError("boom")


class ReadValueStage(Stage):
    name = "read_value"
    requires = ["value"]
    provides = ["read_value"]
    
    async def execute(self, ctx):
        return ctx.artifacts["value"]


@pytest.mark.asyncio
async def test_runner_successful_pipeline():
    pipeline = Pipeline("test").then(SuccessStage()).then(ReadValueStage())
    ctx = PipelineContext(config={})
    runner = PipelineRunner()
    result = await runner.run(pipeline, ctx)
    
    assert result.is_successful is True
    assert len(result.stages) == 2
    assert result.stages[0].status == StageStatus.COMPLETED
    assert result.stages[1].status == StageStatus.COMPLETED
    assert result.total_duration > 0


@pytest.mark.asyncio
async def test_runner_error_isolation():
    pipeline = Pipeline("test").then(SuccessStage()).then(FailStage()).then(ReadValueStage())
    ctx = PipelineContext(config={})
    runner = PipelineRunner()
    result = await runner.run(pipeline, ctx)
    
    assert result.is_successful is False
    assert result.stages[0].status == StageStatus.COMPLETED
    assert result.stages[1].status == StageStatus.FAILED
    assert result.stages[2].status == StageStatus.SKIPPED
    assert "ValueError" in result.stages[1].error
    assert "Skipped due to previous failure" in result.stages[2].error


@pytest.mark.asyncio
async def test_runner_timing():
    pipeline = Pipeline("test").then(SuccessStage())
    ctx = PipelineContext(config={})
    runner = PipelineRunner()
    result = await runner.run(pipeline, ctx)
    
    assert result.stages[0].duration > 0
    assert result.total_duration >= result.stages[0].duration
    assert result.stages[0].started_at is not None
    assert result.stages[0].completed_at is not None