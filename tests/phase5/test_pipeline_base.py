"""Tests for pipeline core: Stage ABC, Pipeline, PipelineContext."""

import pytest
from quantlab.pipeline.base import PipelineContext, Pipeline, Stage
from quantlab.pipeline.models import StageStatus, StageResult, PipelineResult
from quantlab.pipeline.runner import PipelineRunner


class DummyStage(Stage):
    """Simple test stage."""
    name = "dummy"
    requires = []
    provides = ["dummy_output"]
    
    def __init__(self, should_fail: bool = False, output: str = "ok"):
        self._should_fail = should_fail
        self._output = output
    
    async def execute(self, ctx: PipelineContext) -> str:
        if self._should_fail:
            raise ValueError("Intentional failure")
        ctx.artifacts["dummy_output"] = self._output
        return self._output


class RequiresStage(Stage):
    """Stage that requires an artifact from previous stage."""
    name = "requires"
    requires = ["dummy_output"]
    provides = ["requires_output"]
    
    async def execute(self, ctx: PipelineContext) -> str:
        value = ctx.artifacts["dummy_output"]
        ctx.artifacts["requires_output"] = f"got:{value}"
        return f"got:{value}"


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""
    
    def test_defaults(self):
        ctx = PipelineContext(config={"key": "value"})
        assert ctx.config == {"key": "value"}
        assert ctx.artifacts == {}
        assert ctx.metadata == {}
        assert ctx.error is None
    
    def test_mutable_artifacts(self):
        ctx = PipelineContext(config={})
        ctx.artifacts["test"] = "value"
        assert ctx.artifacts["test"] == "value"
    
    def test_error_propagation(self):
        ctx = PipelineContext(config={})
        assert ctx.error is None
        ctx.error = ValueError("test")
        assert isinstance(ctx.error, ValueError)


class TestPipeline:
    """Tests for Pipeline fluent builder."""
    
    def test_empty_pipeline(self):
        p = Pipeline("empty")
        assert p.name == "empty"
        assert p.stages == []
    
    def test_fluent_chaining(self):
        p = Pipeline("chain").then(DummyStage()).then(RequiresStage())
        assert len(p.stages) == 2
        assert p.stages[0].name == "dummy"
        assert p.stages[1].name == "requires"
    
    def test_returns_self_for_chaining(self):
        p = Pipeline("test")
        result = p.then(DummyStage())
        assert result is p


class TestPipelineRunner:
    """Tests for PipelineRunner sequential execution."""
    
    @pytest.mark.asyncio
    async def test_successful_pipeline(self):
        """Three valid stages run to completion."""
        p = Pipeline("success").then(DummyStage(output="a")).then(RequiresStage())
        ctx = PipelineContext(config={})
        runner = PipelineRunner()
        
        result = await runner.run(p, ctx)
        
        assert result.pipeline_name == "success"
        assert len(result.stages) == 2
        assert all(s.status == StageStatus.COMPLETED for s in result.stages)
        assert result.is_successful is True
        assert result.error is None
        assert result.total_duration > 0
        assert ctx.artifacts["requires_output"] == "got:a"
    
    @pytest.mark.asyncio
    async def test_error_isolation_stops_remaining(self):
        """Stage 2 fails → stage 1 completed, stage 2 failed, stage 3 skipped."""
        p = Pipeline("error").then(
            DummyStage(output="first")
        ).then(
            DummyStage(should_fail=True)
        ).then(
            DummyStage(output="third")
        )
        ctx = PipelineContext(config={})
        runner = PipelineRunner()
        
        result = await runner.run(p, ctx)
        
        assert len(result.stages) == 3
        assert result.stages[0].status == StageStatus.COMPLETED
        assert result.stages[1].status == StageStatus.FAILED
        assert result.stages[2].status == StageStatus.SKIPPED
        assert result.is_successful is False
        assert result.error is not None
        assert "ValueError" in result.error
    
    @pytest.mark.asyncio
    async def test_timing_recorded(self):
        """Each stage has duration > 0 and timestamps."""
        p = Pipeline("timing").then(DummyStage())
        ctx = PipelineContext(config={})
        runner = PipelineRunner()
        
        result = await runner.run(p, ctx)
        
        stage = result.stages[0]
        assert stage.duration > 0
        assert stage.started_at is not None
        assert stage.completed_at is not None
        assert stage.completed_at >= stage.started_at
        assert result.total_duration >= stage.duration
    
    @pytest.mark.asyncio
    async def test_stage_result_output_captured(self):
        """Stage output appears in StageResult.output and ctx.artifacts."""
        p = Pipeline("output").then(DummyStage(output="hello"))
        ctx = PipelineContext(config={})
        runner = PipelineRunner()
        
        result = await runner.run(p, ctx)
        
        assert result.stages[0].output == "hello"
        assert ctx.artifacts["dummy_output"] == "hello"
    
    @pytest.mark.asyncio
    async def test_artifact_flow_between_stages(self):
        """RequiresStage reads what DummyStage wrote."""
        p = Pipeline("flow").then(DummyStage(output="test")).then(RequiresStage())
        ctx = PipelineContext(config={})
        runner = PipelineRunner()
        
        result = await runner.run(p, ctx)
        
        assert result.is_successful
        assert ctx.artifacts["requires_output"] == "got:test"


class TestPipelineResult:
    """Tests for PipelineResult computed properties."""
    
    def test_is_successful_true(self):
        result = PipelineResult(
            pipeline_name="test",
            stages=[
                StageResult(stage_name="a", status=StageStatus.COMPLETED),
                StageResult(stage_name="b", status=StageStatus.COMPLETED),
            ]
        )
        assert result.is_successful is True
    
    def test_is_successful_false_on_failed(self):
        result = PipelineResult(
            pipeline_name="test",
            stages=[
                StageResult(stage_name="a", status=StageStatus.COMPLETED),
                StageResult(stage_name="b", status=StageStatus.FAILED),
            ]
        )
        assert result.is_successful is False
    
    def test_is_successful_false_on_skipped(self):
        result = PipelineResult(
            pipeline_name="test",
            stages=[
                StageResult(stage_name="a", status=StageStatus.COMPLETED),
                StageResult(stage_name="b", status=StageStatus.SKIPPED),
            ]
        )
        assert result.is_successful is False
    
    def test_is_successful_false_on_error(self):
        result = PipelineResult(
            pipeline_name="test",
            stages=[StageResult(stage_name="a", status=StageStatus.COMPLETED)],
            error="Something failed"
        )
        assert result.is_successful is False