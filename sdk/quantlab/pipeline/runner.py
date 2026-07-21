"""PipelineRunner — sequential stage execution with timing and error isolation."""

import time
from datetime import datetime
from typing import Any

from quantlab.pipeline.base import Pipeline, PipelineContext
from quantlab.pipeline.models import PipelineResult, StageResult, StageStatus


class PipelineRunner:
    """Executes a Pipeline sequentially with per-stage timing and error isolation.
    
    On stage failure: records error, stops execution, marks remaining stages SKIPPED.
    """
    
    async def run(self, pipeline: Pipeline, ctx: PipelineContext) -> PipelineResult:
        """Run all stages in the pipeline sequentially."""
        result = PipelineResult(pipeline_name=pipeline.name)
        pipeline_start = time.monotonic()
        
        for i, stage in enumerate(pipeline.stages):
            # Check if previous stage failed
            if ctx.error is not None:
                # Skip remaining stages
                skipped = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.SKIPPED,
                    duration=0.0,
                    error=f"Skipped due to previous failure: {ctx.error}",
                )
                result.stages.append(skipped)
                continue
            
            # Execute stage
            stage_start = time.monotonic()
            stage_result = StageResult(
                stage_name=stage.name,
                status=StageStatus.RUNNING,
                started_at=datetime.now(),
            )
            
            try:
                output = await stage.execute(ctx)
                stage_duration = time.monotonic() - stage_start
                
                stage_result.status = StageStatus.COMPLETED
                stage_result.duration = stage_duration
                stage_result.output = output
                stage_result.completed_at = datetime.now()
                
            except Exception as e:
                stage_duration = time.monotonic() - stage_start
                
                stage_result.status = StageStatus.FAILED
                stage_result.duration = stage_duration
                stage_result.error = f"{type(e).__name__}: {e}"
                stage_result.completed_at = datetime.now()
                
                # Set context error to skip remaining stages
                ctx.error = e
            
            result.stages.append(stage_result)
        
        result.total_duration = time.monotonic() - pipeline_start
        if ctx.error:
            result.error = f"{type(ctx.error).__name__}: {ctx.error}"
        
        return result