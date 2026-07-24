"""PipelineRunner — sequential stage execution with timing, error isolation, contract validation, and gate injection."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from quantlab.pipeline.base import Pipeline, PipelineContext, Stage as PipelineStage
from quantlab.pipeline.errors import ContractValidationError, GateTimeoutError
from quantlab.pipeline.models import PipelineResult, StageResult, StageStatus
from quantlab.pipeline.registry import StageRegistry
from quantlab.pipeline.stages.gate_interceptor import (
    FallbackPolicy,
    GateInterceptorStage,
    HUMAN_GATE_IDS,
)


class PipelineRunner:
    """Executes a Pipeline sequentially with per-stage timing and error isolation.
    
    Features:
        - Sequential stage execution with per-stage timing
        - Error isolation: on failure, stops execution, marks remaining SKIPPED
        - Contract validation: validates all stage ``requires`` before execution
        - Gate injection: registers ``GateInterceptorStage`` instances at configured positions
        - Fluent gate registration API
    """
    
    def __init__(self) -> None:
        self._gates: dict[str, GateInterceptorStage] = {}
        self._registry: StageRegistry | None = None
    
    # ─── Gate Registration ─────────────────────────────────────────────────────
    
    def register_gate(self, after_stage: str, gate: GateInterceptorStage) -> None:
        """Register a gate interceptor to execute after a given stage.
        
        Args:
            after_stage: Name of the stage after which this gate executes.
            gate: GateInterceptorStage instance.
        """
        self._gates[after_stage] = gate
    
    def configure_gates(self, gates_config: list[dict[str, Any]]) -> None:
        """Configure gates from a list of gate config dicts.
        
        Each config dict may contain:
            - after_stage (str): Stage name to gate after.
            - gate_id (str): Gate identifier.
            - timeout_hours (float): Timeout in hours.
            - fallback (str): Fallback policy.
        
        Args:
            gates_config: List of gate configuration dictionaries.
        """
        for g in gates_config:
            gate = GateInterceptorStage()
            gate.name = g.get("gate_id", "gate")
            gate.gate_id = g.get("gate_id", "gate")
            gate.timeout_hours = g.get("timeout_hours", 24.0)
            fallback_str = g.get("fallback", "CONTINUE")
            try:
                gate.fallback = FallbackPolicy(fallback_str)
            except ValueError:
                gate.fallback = FallbackPolicy.CONTINUE
            gate.requires = g.get("requires", [])
            gate.provides = [f"gate_decision_{gate.gate_id}"]
            
            after = g.get("after_stage", "")
            if after:
                self.register_gate(after, gate)
    
    # ─── Contract Validation ────────────────────────────────────────────────────
    
    def validate_contracts(
        self,
        pipeline: Pipeline,
        external_provides: set[str] | None = None,
    ) -> None:
        """Verify that every stage's ``requires`` are satisfied by prior stages' ``provides``.
        
        Iterates through pipeline stages in order, accumulates the set of
        provided keys, and checks each stage's requires against it.
        
        Args:
            pipeline: The pipeline to validate.
            external_provides: Optional set of keys that are provided externally
                (e.g. "selected_strategies", "live_equity"), so contract validation
                treats them as pre-satisfied.
        
        Raises:
            ContractValidationError: If any stage requires a key not provided by
                any earlier stage. Includes details of missing keys per stage.
        """
        provided: set[str] = set(external_provides or ())
        missing_keys: dict[str, list[str]] = {}
        stage_names: list[str] = []
        
        for stage in pipeline.stages:
            stage_requires = getattr(stage, "requires", [])
            stage_name = getattr(stage, "name", "unnamed")
            
            stage_missing = [k for k in stage_requires if k not in provided]
            if stage_missing:
                missing_keys[stage_name] = stage_missing
                stage_names.append(stage_name)
            
            stage_provides = getattr(stage, "provides", [])
            provided.update(stage_provides)
        
        if missing_keys:
            raise ContractValidationError(
                message=f"Pipeline '{pipeline.name}' has contract violations",
                missing_keys=missing_keys,
                stage_names=stage_names,
            )
    
    # ─── Pipeline Building from Config ─────────────────────────────────────────
    
    def set_registry(self, registry: StageRegistry) -> None:
        """Set a stage registry for building pipelines from config.
        
        Args:
            registry: StageRegistry instance.
        """
        self._registry = registry
    
    def _get_gate_lookup(self, config_gates: list[Any]) -> dict[str, Any]:
        """Build a lookup dict: after_stage -> gate config dict.
        
        Supports both Pydantic models and plain dicts.
        """
        gate_lookup: dict[str, Any] = {}
        for g in (config_gates or []):
            if hasattr(g, "after_stage"):
                # Pydantic model
                after = g.after_stage or g.name or ""
                if after:
                    gate_lookup[after] = g
            elif isinstance(g, dict):
                after = g.get("after_stage", "") or g.get("name", "")
                if after:
                    gate_lookup[after] = g
        return gate_lookup
    
    def _make_gate_stage(self, gate_config: Any) -> GateInterceptorStage:
        """Create a GateInterceptorStage from a gate config (dict or Pydantic)."""
        if hasattr(gate_config, "gate_id"):
            # Pydantic model
            gate_id = gate_config.gate_id or gate_config.name
            timeout = gate_config.timeout_hours
            fallback_str = gate_config.fallback
            requires = gate_config.requires or []
        else:
            # dict
            gate_id = gate_config.get("gate_id", "") or gate_config.get("name", "")
            timeout = gate_config.get("timeout_hours", 24.0)
            fallback_str = gate_config.get("fallback", "CONTINUE")
            requires = gate_config.get("requires", [])
        
        gate_stage = GateInterceptorStage()
        gate_stage.name = f"gate_{gate_id}" if gate_id else "gate"
        gate_stage.gate_id = gate_id or "UNKNOWN_GATE"
        gate_stage.timeout_hours = timeout
        try:
            gate_stage.fallback = FallbackPolicy(fallback_str)
        except ValueError:
            gate_stage.fallback = FallbackPolicy.CONTINUE
        gate_stage.requires = requires
        gate_stage.provides = [f"gate_decision_{gate_stage.gate_id}"]
        return gate_stage
    
    def build_from_config(
        self,
        config: Any,
        pipeline_name: str | None = None,
    ) -> Pipeline:
        """Build a Pipeline from a config by instantiating stages.
        
        Uses the configured StageRegistry to look up stage classes.
        Automatically injects gate stages at their configured positions.
        
        Args:
            config: A MultiAgentPipelineConfig (or compatible object with
                   ``stages``, ``gates``, ``name`` fields).
            pipeline_name: Override for the pipeline name.
        
        Returns:
            Configured Pipeline instance with all stages in order.
        
        Raises:
            ValueError: If a stage name is not found in the registry.
        """
        if self._registry is None:
            self._registry = StageRegistry()
        
        name = pipeline_name or (getattr(config, "name", None) or "multi-agent-pipeline")
        pipeline = Pipeline(name=name)
        
        config_stages = getattr(config, "stages", []) or []
        config_gates = getattr(config, "gates", []) or []
        
        gate_lookup = self._get_gate_lookup(config_gates)
        
        for stage_config in config_stages:
            # Support both Pydantic models and dicts
            if hasattr(stage_config, "name"):
                stage_name = stage_config.name
            elif isinstance(stage_config, dict):
                stage_name = stage_config.get("name", "unknown")
            else:
                stage_name = str(stage_config)
            
            stage_class = self._registry.get_stage_class(stage_name)
            
            if stage_class is None:
                raise ValueError(
                    f"Unknown stage '{stage_name}'. "
                    f"Available: {', '.join(sorted(self._registry.list_stage_names()))}"
                )
            
            stage = stage_class()
            pipeline.stages.append(stage)
            
            # Inject gate after this stage if configured
            gate_config_obj = gate_lookup.get(stage_name)
            if gate_config_obj is not None:
                gate_stage = self._make_gate_stage(gate_config_obj)
                pipeline.stages.append(gate_stage)
        
        return pipeline
    
    # ─── Pipeline Execution ────────────────────────────────────────────────────
    
    async def run(
        self,
        pipeline: Pipeline,
        ctx: PipelineContext,
        external_provides: set[str] | None = None,
    ) -> PipelineResult:
        """Run all stages in the pipeline sequentially.
        
        Validates contracts before execution.
        
        Args:
            pipeline: The pipeline to execute.
            ctx: Shared pipeline context.
            external_provides: Optional set of keys provided externally (e.g.
                "selected_strategies", "live_equity"). These are treated as
                pre-satisfied during contract validation.
        
        Returns:
            PipelineResult with per-stage results.
        """
        result = PipelineResult(pipeline_name=pipeline.name)
        pipeline_start = time.monotonic()
        
        # Validate contracts before any execution
        self.validate_contracts(pipeline, external_provides=external_provides)
        
        for i, stage in enumerate(pipeline.stages):
            # Check if previous stage failed
            if ctx.error is not None:
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
                
            except GateTimeoutError:
                stage_duration = time.monotonic() - stage_start
                stage_result.status = StageStatus.FAILED
                stage_result.duration = stage_duration
                stage_result.error = "Gate timed out and aborted pipeline"
                stage_result.completed_at = datetime.now()
                ctx.error = GateTimeoutError(
                    f"Gate aborted pipeline"
                )
                
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
    
    async def run_with_gates(
        self,
        pipeline: Pipeline,
        ctx: PipelineContext,
        external_provides: set[str] | None = None,
    ) -> PipelineResult:
        """Run pipeline with gate interceptors injected at registered positions.
        
        After each pipeline stage completes successfully, checks if a gate
        interceptor is registered for that stage and executes it.
        
        Args:
            pipeline: The pipeline to execute.
            ctx: Pipeline context.
            external_provides: Optional set of keys provided externally.
        
        Returns:
            PipelineResult with per-stage and per-gate results.
        """
        result = PipelineResult(pipeline_name=pipeline.name)
        pipeline_start = time.monotonic()
        
        # Validate contracts before any execution
        self.validate_contracts(pipeline, external_provides=external_provides)
        
        for i, stage in enumerate(pipeline.stages):
            # Check if previous stage failed
            if ctx.error is not None:
                skipped = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.SKIPPED,
                    duration=0.0,
                    error=f"Skipped due to previous failure: {ctx.error}",
                )
                result.stages.append(skipped)
                continue
            
            # Execute pipeline stage
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
                ctx.error = e
            
            # Append stage result BEFORE gate result
            result.stages.append(stage_result)
            
            # If stage succeeded, check for gate after this stage
            if stage_result.status == StageStatus.COMPLETED:
                gate = self._gates.get(stage.name)
                if gate is not None:
                    gate_result = StageResult(
                        stage_name=gate.name,
                        status=StageStatus.RUNNING,
                        started_at=datetime.now(),
                    )
                    try:
                        gate_output = await gate.execute(ctx)
                        gate_duration = time.monotonic() - stage_start
                        gate_result.status = StageStatus.COMPLETED
                        gate_result.duration = gate_duration
                        gate_result.output = gate_output
                        gate_result.completed_at = datetime.now()
                    except GateTimeoutError as e:
                        gate_duration = time.monotonic() - stage_start
                        gate_result.status = StageStatus.FAILED
                        gate_result.duration = gate_duration
                        gate_result.error = str(e)
                        gate_result.completed_at = datetime.now()
                        ctx.error = e
                        result.stages.append(gate_result)
                        break  # Stop on gate abort
                    except Exception as e:
                        gate_duration = time.monotonic() - stage_start
                        gate_result.status = StageStatus.FAILED
                        gate_result.duration = gate_duration
                        gate_result.error = f"{type(e).__name__}: {e}"
                        gate_result.completed_at = datetime.now()
                        ctx.error = e
                        result.stages.append(gate_result)
                        break
                    
                    result.stages.append(gate_result)
                    if gate_result.status == StageStatus.FAILED:
                        break
        
        result.total_duration = time.monotonic() - pipeline_start
        if ctx.error:
            result.error = f"{type(ctx.error).__name__}: {ctx.error}"
        
        return result
