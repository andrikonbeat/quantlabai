"""ResearchDirector — central orchestrator for multi-agent research campaigns.

Owns ``PipelineRunner``, constructs the full 17-stage pipeline from
``ResearchConfig``, manages campaign lifecycle (create → run → pause →
resume → rollback), handles human gate callbacks, and implements the
objective optimisation loop across iteration cycles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from quantlab.dsl.models import HypothesisConfig, IterationConfig, ResearchConfig
from quantlab.sqx.project_builder import BuildConfig

logger = logging.getLogger(__name__)


class CampaignState(str, Enum):
    """Lifecycle states for a research campaign."""

    CREATED = "created"
    RUNNING = "running"
    GATE_PENDING = "gate_pending"
    COMPLETED = "completed"
    CONVERGED = "converged"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    PAUSED = "paused"


@dataclass
class CampaignRecord:
    """Persistent record of a campaign's state and metadata."""

    campaign_id: str
    config: ResearchConfig
    state: CampaignState = CampaignState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    current_iteration: int = 0
    result: Any = None
    error: str | None = None
    previous_sharpes: list[float] = field(default_factory=list)
    best_result_score: float = 0.0
    best_result_iteration: int = 0
    best_result_config: Any = None
    consecutive_worse_count: int = 0


class ResearchDirector:
    """Central orchestrator for multi-agent research campaigns.

    Manages campaign lifecycle, owns ``PipelineRunner``, builds pipelines,
    handles human gate callbacks, and implements the objective optimization
    loop.

    Args:
        knowledge_root: Root path for Knowledge Lake artifacts. Defaults to
            ``knowledge/structured`` relative to CWD.
        engram_save_fn: Optional async function for recording gate decisions
            to Engram. Signature: ``async fn(title, type, scope, topic_key, content)``.
        gate_orchestrator: Optional ``HumanGateOrchestrator`` instance. When
            provided, gate callbacks registered via ``register_gate_callback``
            are forwarded to the orchestrator, and ``build_pipeline`` uses
            ``orchestrator.on_gate()`` as the per-gate callback.
    """

    def __init__(
        self,
        knowledge_root: str | Path | None = None,
        engram_save_fn: Any = None,
        gate_orchestrator: Any = None,
    ) -> None:
        self._knowledge_root = Path(knowledge_root or "knowledge/structured")
        self._engram_save_fn = engram_save_fn
        self._campaigns: dict[str, CampaignRecord] = {}
        self._runner: Any = None  # PipelineRunner, lazy-imported

        # Optional gate callbacks: gate_id -> async callable
        self._gate_callbacks: dict[str, Any] = {}
        self._gate_orchestrator = gate_orchestrator

    # ── Lazy imports ────────────────────────────────────────────────────────────

    def _get_runner(self) -> Any:
        """Lazy-import and return PipelineRunner."""
        if self._runner is None:
            from quantlab.pipeline.runner import PipelineRunner

            self._runner = PipelineRunner()
        return self._runner

    def _get_registry(self) -> Any:
        """Lazy-import and return StageRegistry."""
        from quantlab.pipeline.registry import StageRegistry

        return StageRegistry()

    # ── Gate callback registration ──────────────────────────────────────────────

    def register_gate_callback(self, gate_id: str, callback: Any) -> None:
        """Register an async callback for a human gate.

        Args:
            gate_id: Gate identifier (e.g. ``HUMAN_REVIEW_OBJECTIVES``).
            callback: Async function receiving ``GateContext`` and returning
                      ``GateDecision``.
        """
        self._gate_callbacks[gate_id] = callback
        if self._gate_orchestrator is not None:
            # Wrap the raw callback so the orchestrator can apply timeout,
            # fallback, notifications, and Engram audit around it.
            orchestrator = self._gate_orchestrator

            async def _orchestrator_callback(ctx: dict[str, Any], gid: str, cb: Any) -> Any:
                return await orchestrator.on_gate(gid, ctx)

            self._gate_orchestrator.register_callback(
                gate_id,
                lambda ctx, gid=gate_id, cb=callback: _orchestrator_callback(ctx, gid, cb),
            )

    # ── Task 2.1: Pipeline construction ────────────────────────────────────────

    def build_pipeline(
        self,
        config: ResearchConfig,
        agent_config: Any = None,
    ) -> Any:
        """Build the full 8-agent pipeline with 5 gate stages from a config.

        Constructs a Pipeline with concrete agent stages in the correct order
        and injects gate interceptor stages at configured positions.

        Stage order: research_llm|research → hypothesis_builder → refutation → [gate1] → builder → statistics →
        review → [gate2] → portfolio → [gate3] → deploy → [gate4] → monitor → [gate5]

        The research stage is selected based on ``agent_config``:
        - If ``agent_config.model`` is non-empty → ``research_llm`` (LLM-powered)
        - Otherwise → ``research`` (classic keyword-based)

        Args:
            config: Validated ``ResearchConfig`` with hypotheses, iteration_config,
                    and gate_policies.
            agent_config: Optional ``AgentConfig`` for LLM routing. When provided
                and ``model != ""``, uses the LLM-powered research stage.

        Returns:
            A ``Pipeline`` instance with all stages in correct order.

        Raises:
            ContractValidationError: If stage contracts are incompatible.
        """
        runner = self._get_runner()
        registry = self._get_registry()

        # Resolve research stage name based on AgentConfig.model
        research_stage = "research"
        if agent_config is not None:
            model = getattr(agent_config, "model", "")
            if model and isinstance(model, str) and model.strip():
                research_stage = "research_llm"

        # Build the stage config list (agent stages only — gates are injected)
        from quantlab.pipeline.config.models import (
            GateConfig,
            MultiAgentPipelineConfig,
            StageConfig,
        )

        stages: list[dict[str, Any]] = [
            {"name": research_stage, "type": "agent"},
            {"name": "hypothesis_builder", "type": "agent"},
            {"name": "refutation", "type": "agent"},
            {"name": "builder", "type": "agent"},
            {"name": "statistics", "type": "agent"},
            {"name": "analysis", "type": "agent"},
            {"name": "review", "type": "agent"},
            {"name": "portfolio", "type": "agent"},
            {"name": "deploy", "type": "agent"},
            {"name": "monitor", "type": "agent"},
        ]

        # Gate definitions with after_stage positions
        gates = [
            GateConfig(
                gate_id="HUMAN_REVIEW_OBJECTIVES",
                name="HUMAN_REVIEW_OBJECTIVES",
                after_stage=research_stage,
                timeout_hours=24,
                fallback="ESCALATE",
            ),
            GateConfig(
                gate_id="HUMAN_APPROVE_ITERATION",
                name="HUMAN_APPROVE_ITERATION",
                after_stage="review",
                timeout_hours=24,
                fallback="ABORT",
            ),
            GateConfig(
                gate_id="HUMAN_APPROVE_PORTFOLIO",
                name="HUMAN_APPROVE_PORTFOLIO",
                after_stage="portfolio",
                timeout_hours=24,
                fallback="ESCALATE",
            ),
            GateConfig(
                gate_id="HUMAN_APPROVE_DEPLOY",
                name="HUMAN_APPROVE_DEPLOY",
                after_stage="deploy",
                timeout_hours=12,
                fallback="HOLD",
            ),
            GateConfig(
                gate_id="HUMAN_REVIEW_PERFORMANCE",
                name="HUMAN_REVIEW_PERFORMANCE",
                after_stage="monitor",
                timeout_hours=48,
                fallback="CONTINUE",
            ),
        ]

        # Build pipeline config
        pipeline_config = MultiAgentPipelineConfig(
            name=f"campaign-{config.campaign}",
            stages=[StageConfig(**s) for s in stages],
            gates=gates,
        )

        # Build the pipeline from registry (gates are injected automatically)
        pipeline = runner.build_from_config(pipeline_config)

        # Register gate callbacks on GateInterceptorStage instances
        for stage_obj in pipeline.stages:
            stage_name = getattr(stage_obj, "name", "")
            gate_id = getattr(stage_obj, "gate_id", "")
            if not gate_id or not gate_id.startswith("HUMAN_"):
                continue

            orchestrator = self._gate_orchestrator

            if orchestrator is not None:
                # Use the orchestrator as the callback so timeout/fallback/
                # notifications/Engram audit are all applied consistently.
                async def _orchestrator_wrapper(
                    gate_ctx: Any,
                    gid: str = gate_id,
                    orch: Any = orchestrator,
                ) -> Any:
                    ctx_dict: dict[str, Any] = {}
                    if hasattr(gate_ctx, "__dict__"):
                        ctx_dict = gate_ctx.__dict__
                    elif isinstance(gate_ctx, dict):
                        ctx_dict = gate_ctx
                    return await orch.on_gate(gid, ctx_dict)

                stage_obj.set_callback(_orchestrator_wrapper)

            elif gate_id in self._gate_callbacks:
                stage_obj.set_callback(self._gate_callbacks[gate_id])

            else:
                # Set a default auto-approve callback for automated test mode
                from quantlab.pipeline.stages.gate_interceptor import (
                    GateAction,
                    GateContext,
                    GateDecision,
                )

                async def _auto_approve(ctx: GateContext) -> GateDecision:
                    return GateDecision(
                        gate_id=ctx.gate_id,
                        action=GateAction.APPROVED,
                        reason="Auto-approved (no callback registered)",
                        decided_by="system",
                    )

                stage_obj.set_callback(_auto_approve)

        return pipeline

    # ── Reconfiguration Loop ───────────────────────────────────────────────────

    @staticmethod
    def apply_iteration_proposal(
        parameter_changes: dict[str, Any],
        build_config: BuildConfig,
    ) -> BuildConfig:
        """Map ReviewerAgent semantic parameter_changes to BuildConfig fields.

        Returns a new BuildConfig instance with known fields applied.
        Unknown keys are skipped with a warning. Empty input returns
        the input config unchanged.

        Args:
            parameter_changes: Dict of semantic change keys from the reviewer.
            build_config: Current BuildConfig to mutate.

        Returns:
            New BuildConfig with applied overrides.
        """
        updated = BuildConfig(
            **{k: v for k, v in build_config.__dict__.items() if v is not None}
        )

        for key, value in parameter_changes.items():
            try:
                if key == "position_size":
                    factor = float(str(value).replace("x", ""))
                    updated.population = int(updated.population * factor) if updated.population else None

                elif key == "generations":
                    val = str(value)
                    if val.lower() in ("increase",):
                        updated.generations = (updated.generations or 0) + 20
                    elif val.lower() in ("decrease",):
                        updated.generations = (updated.generations or 0) - 20
                    else:
                        updated.generations = int(val)

                elif key == "ranking_type":
                    updated.ranking_type = str(value)

                elif key == "ranking_conditions_type":
                    updated.ranking_conditions_type = int(value)

                elif key == "min_conditions":
                    updated.min_conditions = int(value)

                elif key == "max_conditions":
                    updated.max_conditions = int(value)

                elif key == "sl_required":
                    if str(value).lower() == "tighter":
                        updated.sl_required = True
                        updated.sl_fixed_pips = True
                        updated.min_sl_pips = 10
                        updated.max_sl_pips = 30

                elif key == "pt_required":
                    updated.pt_required = True
                    updated.pt_fixed_pips = True
                    updated.min_pt_pips = 20

                elif key == "parameter_space":
                    if str(value).lower() == "reduce":
                        updated.islands = 1
                        updated.decimation_coef = 2

                elif key == "wf_optimization":
                    delta = 2 if str(value).lower() == "increase" else -2
                    updated.wf_optimization = max(1, (updated.wf_optimization or 1) + delta)

                else:
                    logger.warning("Unknown parameter_change key: %s", key)

            except (ValueError, TypeError) as exc:
                logger.warning("Invalid value for parameter_change '%s': %s (%s)", key, value, exc)

        return updated

    def _evaluate_iteration_score(self, ctx: Any) -> float:
        """Extract a scalar score for the current iteration result.

        Uses selected_strategies count as primary metric, falling back
        to aggregate_stats mean when the strategy list is empty.

        Args:
            ctx: PipelineContext from the most recent run.

        Returns:
            Numeric score (higher is better).
        """
        selected = ctx.artifacts.get("selected_strategies", [])
        if isinstance(selected, list) and len(selected) > 0:
            return float(len(selected))

        aggregate = ctx.artifacts.get("aggregate_stats", {})
        if isinstance(aggregate, dict) and aggregate:
            values = [v for v in aggregate.values() if isinstance(v, (int, float))]
            if values:
                return sum(values) / len(values)

        return 0.0

    # ── Task 2.2: Campaign execution ───────────────────────────────────────────

    async def execute_campaign(
        self,
        config: ResearchConfig,
        campaign_id: str | None = None,
    ) -> CampaignRecord:
        """Execute a full multi-agent research campaign.

        Builds the pipeline from config, runs it with iteration loops,
        handles gate callbacks, and checks convergence.

        Args:
            config: Validated ``ResearchConfig``.
            campaign_id: Optional campaign identifier. Auto-generated if omitted.

        Returns:
            ``CampaignRecord`` with final state and results.
        """
        import uuid

        cid = campaign_id or f"campaign_{uuid.uuid4().hex[:12]}"
        record = CampaignRecord(campaign_id=cid, config=config)
        self._campaigns[cid] = record

        # Iteration loop
        current_config = config.model_copy(deep=True) if hasattr(config, "model_copy") else config
        max_iterations = config.iteration_config.max_iterations
        auto_iterate = getattr(config.iteration_config, "auto_iterate", True)
        current_build_config = BuildConfig()

        for iteration in range(max_iterations):
            record.current_iteration = iteration + 1
            record.state = CampaignState.RUNNING
            logger.info(
                "Campaign '%s' — iteration %d/%d",
                cid, iteration + 1, max_iterations,
            )

            # Versioned campaign ID for iterations after the first
            iter_cid = cid if iteration == 0 else f"{cid}_iter{iteration:02d}"

            # Build pipeline with current config
            pipeline = self.build_pipeline(current_config)

            # Create PipelineContext
            from quantlab.pipeline.base import PipelineContext

            ctx = PipelineContext(
                config={
                    "campaign_id": iter_cid,
                    "campaign_name": config.campaign,
                    "iteration": iteration,
                    "max_iterations": max_iterations,
                    "build_config": current_build_config,
                },
                metadata={
                    "pipeline_name": f"campaign-{config.campaign}",
                    "engram_save": self._engram_save_fn,
                },
            )

            # Inject configuration into context artifacts
            ctx.artifacts["research_config"] = current_config.model_dump(mode="json") \
                if hasattr(current_config, "model_dump") else current_config
            ctx.artifacts["objectives"] = [config.campaign]
            ctx.artifacts["hypotheses"] = [
                h.model_dump(mode="json") if hasattr(h, "model_dump") else h
                for h in current_config.hypotheses
            ]
            ctx.artifacts["iteration_config"] = (
                current_config.iteration_config.model_dump(mode="json")
                if hasattr(current_config.iteration_config, "model_dump")
                else {}
            )
            ctx.artifacts["gate_policies"] = [
                g.model_dump(mode="json") if hasattr(g, "model_dump") else g
                for g in current_config.gate_policies
            ]

            # Pre-populate external inputs that stages require
            # (portfolio agent needs selected_strategies from outside)
            ctx.artifacts.setdefault("selected_strategies", [])
            # (monitoring agent needs live_equity from broker)
            ctx.artifacts.setdefault("live_equity", {})
            # (gate decisions — these will be provided by gate stages at runtime)
            for gate_id in ("HUMAN_APPROVE_PORTFOLIO", "HUMAN_APPROVE_DEPLOY", "HUMAN_REVIEW_PERFORMANCE"):
                key = f"gate_decision_{gate_id}"
                ctx.artifacts.setdefault(key, {"status": "pending"})

            # Run pipeline
            runner = self._get_runner()
            try:
                # External inputs passed as pre-satisfied for contract validation
                EXTERNAL_INPUTS = {
                    "live_equity",
                    "gate_decision_HUMAN_APPROVE_PORTFOLIO",
                    "gate_decision_HUMAN_APPROVE_DEPLOY",
                    "gate_decision_HUMAN_REVIEW_PERFORMANCE",
                }
                result = await runner.run(
                    pipeline, ctx,
                    external_provides=EXTERNAL_INPUTS,
                )
                record.result = result

                if result.is_successful:
                    logger.info(
                        "Campaign '%s' iteration %d completed successfully",
                        cid, iteration + 1,
                    )
                else:
                    record.state = CampaignState.FAILED
                    record.error = result.error
                    logger.error(
                        "Campaign '%s' iteration %d failed: %s",
                        cid, iteration + 1, result.error,
                    )
                    return record

            except Exception as e:
                record.state = CampaignState.FAILED
                record.error = f"{type(e).__name__}: {e}"
                logger.exception("Campaign '%s' iteration %d error", cid, iteration + 1)
                return record

            # Check convergence
            if self.check_convergence(ctx, current_config):
                record.state = CampaignState.CONVERGED
                logger.info("Campaign '%s' converged at iteration %d", cid, iteration + 1)
                record.completed_at = datetime.now(timezone.utc)
                return record

            # Evaluate iteration score and track best result
            current_score = self._evaluate_iteration_score(ctx)
            if current_score > record.best_result_score:
                record.best_result_score = current_score
                record.best_result_iteration = iteration + 1
                record.best_result_config = current_config
                record.consecutive_worse_count = 0
            else:
                record.consecutive_worse_count += 1
                if record.consecutive_worse_count >= 2:
                    record.state = CampaignState.CONVERGED
                    logger.info(
                        "Campaign '%s' aborted due to consecutive degradation at iteration %d",
                        cid, iteration + 1,
                    )
                    record.completed_at = datetime.now(timezone.utc)
                    if record.best_result_config is not None:
                        current_config = record.best_result_config
                    return record

            # Branch on review decision
            review_decision = ctx.artifacts.get("review_decision", "")
            if auto_iterate and review_decision == "ITERATE":
                iteration_proposal = ctx.artifacts.get("iteration_proposal", {})
                parameter_changes = (
                    iteration_proposal.get("parameter_changes", {})
                    if isinstance(iteration_proposal, dict)
                    else {}
                )
                current_build_config = self.apply_iteration_proposal(
                    parameter_changes,
                    current_build_config,
                )

                # Apply new hypotheses from proposal
                if isinstance(iteration_proposal, dict):
                    new_hypotheses = iteration_proposal.get("new_hypotheses", [])
                    if new_hypotheses:
                        updated = current_config.model_copy(deep=True) if hasattr(current_config, "model_copy") else current_config
                        if hasattr(updated, "hypotheses"):
                            updated.hypotheses = list(updated.hypotheses) + [
                                HypothesisConfig(
                                    name=f"reconfig_{iteration}_{i}",
                                    description=h,
                                    confidence=0.4,
                                )
                                for i, h in enumerate(new_hypotheses)
                            ]
                            current_config = updated

                # Continue to next iteration with updated config
                continue

            elif review_decision == "REJECT":
                record.state = CampaignState.FAILED
                record.error = f"Rejected by reviewer at iteration {iteration + 1}"
                record.completed_at = datetime.now(timezone.utc)
                return record

            elif review_decision == "APPROVE":
                record.state = CampaignState.COMPLETED
                record.completed_at = datetime.now(timezone.utc)
                return record

            # If auto-iteration is disabled, stop after the current iteration
            if not auto_iterate:
                break

            # Propose next cycle modifications (task 2.4) for non-ITERATE paths
            if iteration < max_iterations - 1:
                current_config = self.propose_next_cycle(ctx, current_config)

        # All iterations completed without convergence
        record.state = CampaignState.COMPLETED
        record.completed_at = datetime.now(timezone.utc)
        logger.info("Campaign '%s' completed all %d iterations", cid, max_iterations)
        return record

    async def run_campaign(
        self,
        campaign_id: str,
        config: ResearchConfig,
    ) -> CampaignRecord:
        """Alias for ``execute_campaign`` with explicit campaign_id.

        Args:
            campaign_id: Campaign identifier.
            config: Validated ``ResearchConfig``.

        Returns:
            ``CampaignRecord`` with final state and results.
        """
        return await self.execute_campaign(config=config, campaign_id=campaign_id)

    # ── Task 2.3: Rollback ──────────────────────────────────────────────────────

    def rollback_campaign(self, campaign_id: str) -> None:
        """Rollback a campaign by deleting Knowledge Lake artifacts.

        Removes:
        - ``knowledge/structured/{campaign_id}/`` directory and all artifacts.
        - Campaign record from the in-memory registry.

        Engram topics for the campaign are not deleted here (they serve as
        audit trail), but their lifecycle can be managed via ``Engram`` TTL
        policies.

        Args:
            campaign_id: Campaign identifier to roll back.

        Raises:
            ValueError: If the campaign_id is unknown.
        """
        if campaign_id not in self._campaigns:
            raise ValueError(f"Unknown campaign '{campaign_id}'")

        # Delete Knowledge Lake artifacts
        campaign_dir = self._knowledge_root / campaign_id
        if campaign_dir.exists():
            import shutil

            shutil.rmtree(campaign_dir)
            logger.info("Deleted Knowledge Lake artifacts for '%s'", campaign_id)

        # Mark campaign as rolled back
        self._campaigns[campaign_id].state = CampaignState.ROLLED_BACK
        logger.info("Campaign '%s' rolled back", campaign_id)

    # ── Task 2.4: Objective optimisation loop ───────────────────────────────────

    def check_convergence(
        self,
        ctx: Any,
        config: ResearchConfig,
    ) -> bool:
        """Check if the campaign has converged based on iteration config.

        Convergence criteria (configurable via ``IterationConfig``):
        1. Maximum iterations reached (checked externally by the loop).
        2. Sharpe improvement below ``convergence_threshold`` for
           ``early_stop_patience`` consecutive iterations.

        Args:
            ctx: PipelineContext from the most recent run.
            config: Current ``ResearchConfig`` with iteration settings.

        Returns:
            ``True`` if convergence criteria are met.
        """
        threshold = config.iteration_config.convergence_threshold
        patience = config.iteration_config.early_stop_patience

        # Extract Sharpe from context artifacts (written by Statistics stage)
        statistics = ctx.artifacts.get("statistics", {})
        current_sharpe = None
        if isinstance(statistics, dict):
            current_sharpe = statistics.get("sharpe_ratio") or statistics.get("sharpe")

        # Find the campaign record
        campaign_id = ctx.config.get("campaign_id", "")
        record = self._campaigns.get(campaign_id)

        if current_sharpe is not None and record is not None:
            # Track consecutive below-threshold improvements
            if record.previous_sharpes:
                prev_sharpe = record.previous_sharpes[-1]
                improvement = abs(current_sharpe - prev_sharpe)
                record.previous_sharpes.append(current_sharpe)

                if improvement < threshold:
                    # Increment consecutive count
                    record._consecutive_below = getattr(record, "_consecutive_below", 0) + 1
                    if record._consecutive_below >= patience:
                        logger.info(
                            "Convergence detected: Sharpe improvement < %.4f "
                            "for %d consecutive iterations",
                            threshold, patience,
                        )
                        return True
                else:
                    # Reset counter on improvement above threshold
                    record._consecutive_below = 0
            else:
                record.previous_sharpes.append(current_sharpe or 0.0)
                record._consecutive_below = 0

        return False

    def propose_next_cycle(
        self,
        ctx: Any,
        config: ResearchConfig,
    ) -> ResearchConfig:
        """Generate modified hypotheses for the next cycle based on monitoring feedback.

        Analyzes pipeline context artifacts (statistics, regime alerts) and
        adjusts hypotheses to target areas for improvement.

        Args:
            ctx: PipelineContext from the most recent run.
            config: Current ``ResearchConfig``.

        Returns:
            Modified ``ResearchConfig`` with updated hypotheses.
        """
        # Extract monitoring feedback from context
        statistics = ctx.artifacts.get("statistics", {})
        regime_alerts = ctx.artifacts.get("regime_alerts", [])
        portfolio_sharpe = None
        max_drawdown = None

        if isinstance(statistics, dict):
            portfolio_sharpe = statistics.get("sharpe_ratio") or statistics.get("sharpe")
            max_drawdown = statistics.get("max_drawdown")

        # Build new hypotheses targeting improvements
        new_hypotheses: list[HypothesisConfig] = list(config.hypotheses)

        if portfolio_sharpe is not None and portfolio_sharpe < 1.5:
            new_hypotheses.append(
                HypothesisConfig(
                    name=f"improve_sharpe_{config.iteration_config.max_iterations}",
                    description=(
                        f"Improve Sharpe from {portfolio_sharpe:.2f} to > 1.5 "
                        "by tightening entry filters and adding trend confirmation"
                    ),
                    parameters={"min_sharpe": 1.5, "current": portfolio_sharpe},
                    expected_outcome="Sharpe > 1.5 after optimisation",
                    confidence=0.5,
                )
            )

        if max_drawdown is not None and max_drawdown > 0.15:
            new_hypotheses.append(
                HypothesisConfig(
                    name=f"reduce_dd_{config.iteration_config.max_iterations}",
                    description=(
                        f"Reduce max drawdown from {max_drawdown:.1%} to < 15% "
                        "via position sizing and volatility filter"
                    ),
                    parameters={"max_dd": 0.15, "current": max_drawdown},
                    expected_outcome="Max drawdown < 15%",
                    confidence=0.6,
                )
            )

        if regime_alerts:
            new_hypotheses.append(
                HypothesisConfig(
                    name="regime_adapt",
                    description=f"Adapt strategy to regime change: {regime_alerts}",
                    parameters={"regime_alerts": regime_alerts},
                    expected_outcome="Regime-adaptive parameters",
                    confidence=0.4,
                )
            )

        # Build updated config
        updated = config.model_copy(deep=True) if hasattr(config, "model_copy") else config
        if hasattr(updated, "hypotheses"):
            updated.hypotheses = new_hypotheses

        return updated

    # ── Utility methods ─────────────────────────────────────────────────────────

    def get_campaign(self, campaign_id: str) -> CampaignRecord | None:
        """Retrieve a campaign record by ID.

        Args:
            campaign_id: Campaign identifier.

        Returns:
            ``CampaignRecord`` or ``None`` if not found.
        """
        return self._campaigns.get(campaign_id)

    def list_campaigns(self) -> list[CampaignRecord]:
        """Return all known campaign records."""
        return list(self._campaigns.values())
