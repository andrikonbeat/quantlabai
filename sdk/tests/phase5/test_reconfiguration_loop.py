"""Tests for Reconfiguration Loop — Phase 5.

Covers:
- apply_iteration_proposal() unit mapping
- execute_campaign() ITERATE / REJECT / APPROVE branching
- Degradation abort (2 consecutive worse)
- auto_iterate=False bypass
- E2E full loop with mock SQX + versioned dirs
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quantlab.agents.research_director import CampaignState, ResearchDirector
from quantlab.dsl.models import (
    HypothesisConfig,
    IterationConfig,
    ResearchConfig,
)
from quantlab.sqx.project_builder import BuildConfig


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_config(**overrides) -> ResearchConfig:
    """Minimal ResearchConfig for loop tests."""
    iteration_config = IterationConfig(
        max_iterations=overrides.pop("max_iterations", 3),
        auto_iterate=overrides.pop("auto_iterate", True),
    )
    base = dict(
        campaign="LoopTest",
        market="EURUSD",
        timeframe="H1",
        iteration_config=iteration_config,
    )
    base.update(overrides)
    return ResearchConfig(**base)


def _mock_pipeline_result(is_successful: bool = True, error: str | None = None):
    result = MagicMock()
    result.is_successful = is_successful
    result.error = error
    result.stages = []
    result.total_duration = 0.0
    return result


def _patch_director_deps(director: ResearchDirector, review_decision: str = "APPROVE"):
    """Patch build_pipeline and runner to avoid real SQX dispatch."""
    mock_pipeline = MagicMock()
    mock_runner = MagicMock()

    async def _fake_run(pipeline, ctx, **kwargs):
        # Populate artifacts the loop logic expects
        ctx.artifacts["review_decision"] = review_decision
        ctx.artifacts["iteration_proposal"] = {
            "action": "MODIFY_AND_RETEST",
            "parameter_changes": {"position_size": "0.5x"} if review_decision == "ITERATE" else {},
            "new_hypotheses": [],
            "rationale": "test",
            "failed_checks": ["sharpe"] if review_decision == "ITERATE" else [],
        }
        ctx.artifacts["selected_strategies"] = ["strat_a"]
        ctx.artifacts["statistics"] = {"sharpe_ratio": 1.2, "max_drawdown": 10.0}
        return _mock_pipeline_result(is_successful=True)

    mock_runner.run = _fake_run
    director._get_runner = MagicMock(return_value=mock_runner)
    director.build_pipeline = MagicMock(return_value=mock_pipeline)


# ── Unit: apply_iteration_proposal ────────────────────────────────────────────

class TestApplyIterationProposal:
    """Task 2.1: apply_iteration_proposal() mapping."""

    def test_known_keys_applied(self) -> None:
        """GIVEN parameter_changes with known BuildConfig fields
        WHEN apply_iteration_proposal() processes them
        THEN each known field updates the BuildConfig.
        """
        director = ResearchDirector()
        base = BuildConfig(population=200, generations=80)
        changes = {
            "position_size": "0.5x",
            "generations": "increase",
            "ranking_type": "ReturnDDRatio",
            "ranking_conditions_type": "2",
            "min_conditions": "3",
            "max_conditions": "5",
            "sl_required": "tighter",
            "pt_required": "2.0x",
            "parameter_space": "reduce",
            "wf_optimization": "increase",
        }
        result = director.apply_iteration_proposal(changes, base)
        assert result.population == 100  # 200 * 0.5
        assert result.generations == 100  # 80 + 20
        assert result.ranking_type == "ReturnDDRatio"
        assert result.ranking_conditions_type == 2
        assert result.min_conditions == 3
        assert result.max_conditions == 5
        assert result.sl_required is True
        assert result.sl_fixed_pips is True
        assert result.min_sl_pips == 10
        assert result.max_sl_pips == 30
        assert result.pt_required is True
        assert result.pt_fixed_pips is True
        assert result.min_pt_pips == 20
        assert result.islands == 1
        assert result.decimation_coef == 2
        assert result.wf_optimization == 3  # None treated as 1 + 2 increase

    def test_unknown_keys_skipped_with_warning(self, caplog) -> None:
        """GIVEN parameter_changes containing an unrecognized field
        WHEN apply_iteration_proposal() processes them
        THEN a warning is logged and the unknown field is skipped.
        """
        director = ResearchDirector()
        base = BuildConfig(population=200)
        changes = {"unknown_key": "value", "position_size": "2.0x"}
        with caplog.at_level(logging.WARNING):
            result = director.apply_iteration_proposal(changes, base)
        assert "Unknown parameter_change key: unknown_key" in caplog.text
        assert result.population == 400  # 200 * 2.0

    def test_empty_input_returns_unchanged(self) -> None:
        """GIVEN empty parameter_changes
        WHEN apply_iteration_proposal() processes them
        THEN no BuildConfig fields are modified.
        """
        director = ResearchDirector()
        base = BuildConfig(population=200, generations=80)
        result = director.apply_iteration_proposal({}, base)
        assert result.population == 200
        assert result.generations == 80
        assert result is not base  # returns a new instance

    def test_all_keys_skipped_returns_unchanged(self) -> None:
        """GIVEN parameter_changes where all keys are unknown
        WHEN apply_iteration_proposal() processes them
        THEN the input BuildConfig is returned unchanged.
        """
        director = ResearchDirector()
        base = BuildConfig(population=200)
        changes = {"foo": "bar", "baz": "qux"}
        result = director.apply_iteration_proposal(changes, base)
        assert result.population == 200

    def test_position_size_direct_float(self) -> None:
        """GIVEN position_size as a direct float-like string
        WHEN apply_iteration_proposal() processes it
        THEN population is multiplied correctly.
        """
        director = ResearchDirector()
        base = BuildConfig(population=100)
        changes = {"position_size": "1.5x"}
        result = director.apply_iteration_proposal(changes, base)
        assert result.population == 150

    def test_generations_direct_int(self) -> None:
        """GIVEN generations as a direct int string
        WHEN apply_iteration_proposal() processes it
        THEN generations is set to that int.
        """
        director = ResearchDirector()
        base = BuildConfig(generations=50)
        changes = {"generations": "120"}
        result = director.apply_iteration_proposal(changes, base)
        assert result.generations == 120

    def test_wf_optimization_decrease(self) -> None:
        """GIVEN wf_optimization decrease
        WHEN apply_iteration_proposal() processes it
        THEN wf_optimization is decreased by 2, clamped to >= 1.
        """
        director = ResearchDirector()
        base = BuildConfig(wf_optimization=3)
        changes = {"wf_optimization": "decrease"}
        result = director.apply_iteration_proposal(changes, base)
        assert result.wf_optimization == 1  # 3 - 2, clamped to 1

    def test_invalid_value_type_skipped(self, caplog) -> None:
        """GIVEN a known key with an invalid value type
        WHEN apply_iteration_proposal() processes it
        THEN the key is skipped with a warning.
        """
        director = ResearchDirector()
        base = BuildConfig(population=200)
        changes = {"ranking_conditions_type": "not_an_int"}
        with caplog.at_level(logging.WARNING):
            result = director.apply_iteration_proposal(changes, base)
        assert result.population == 200  # unchanged


# ── Integration: execute_campaign branching ────────────────────────────────────

class TestExecuteCampaignBranching:
    """Task 2.2+: execute_campaign() review_decision branching."""

    @pytest.mark.asyncio
    async def test_iterate_branch_applies_proposal_and_continues(self) -> None:
        """GIVEN review_decision=ITERATE and auto_iterate=True
        WHEN execute_campaign() runs
        THEN the loop continues with mutated BuildConfig and versioned ID.
        """
        director = ResearchDirector()
        config = _make_config(max_iterations=2)
        _patch_director_deps(director, review_decision="ITERATE")

        record = await director.execute_campaign(config, campaign_id="base-camp")
        # Should complete both iterations
        assert record.current_iteration == 2
        assert record.state == CampaignState.COMPLETED

    @pytest.mark.asyncio
    async def test_reject_branch_aborts_with_failed(self) -> None:
        """GIVEN review_decision=REJECT
        WHEN execute_campaign() runs
        THEN the campaign aborts with state=FAILED.
        """
        director = ResearchDirector()
        config = _make_config(max_iterations=3)
        _patch_director_deps(director, review_decision="REJECT")

        record = await director.execute_campaign(config, campaign_id="reject-camp")
        assert record.state == CampaignState.FAILED
        assert record.current_iteration == 1

    @pytest.mark.asyncio
    async def test_approve_branch_exits_loop(self) -> None:
        """GIVEN review_decision=APPROVE
        WHEN execute_campaign() runs
        THEN the loop exits and state=COMPLETED.
        """
        director = ResearchDirector()
        config = _make_config(max_iterations=3)
        _patch_director_deps(director, review_decision="APPROVE")

        record = await director.execute_campaign(config, campaign_id="approve-camp")
        assert record.state == CampaignState.COMPLETED
        assert record.current_iteration == 1

    @pytest.mark.asyncio
    async def test_auto_iterate_false_ignores_review_decision(self) -> None:
        """GIVEN auto_iterate=False and review_decision=ITERATE
        WHEN execute_campaign() runs
        THEN a single iteration executes and loop proceeds to portfolio.
        """
        director = ResearchDirector()
        config = _make_config(max_iterations=3, auto_iterate=False)
        _patch_director_deps(director, review_decision="ITERATE")

        record = await director.execute_campaign(config, campaign_id="no-reconfig")
        # With auto_iterate=False, loop should not re-run for ITERATE
        assert record.state == CampaignState.COMPLETED
        assert record.current_iteration == 1

    @pytest.mark.asyncio
    async def test_versioned_campaign_id_injected(self) -> None:
        """GIVEN execute_campaign() with multiple iterations
        WHEN the loop runs
        THEN versioned campaign IDs are injected into context.config.
        """
        director = ResearchDirector()
        config = _make_config(max_iterations=2)
        _patch_director_deps(director, review_decision="ITERATE")

        captured_ids: list[str] = []

        original_build_pipeline = director.build_pipeline
        def capture_build(cfg):
            # We can't easily capture context IDs here because build_pipeline
            # doesn't receive context. Instead we verify via the mock runner.
            return original_build_pipeline(cfg)

        # Patch _get_runner to capture context IDs
        async def capturing_run(pipeline, ctx, **kwargs):
            captured_ids.append(ctx.config.get("campaign_id", ""))
            ctx.artifacts["review_decision"] = "ITERATE"
            ctx.artifacts["iteration_proposal"] = {
                "action": "MODIFY_AND_RETEST",
                "parameter_changes": {"position_size": "0.5x"},
                "new_hypotheses": [],
                "rationale": "test",
                "failed_checks": ["sharpe"],
            }
            ctx.artifacts["selected_strategies"] = ["strat_a"]
            ctx.artifacts["statistics"] = {"sharpe_ratio": 1.2, "max_drawdown": 10.0}
            return _mock_pipeline_result(is_successful=True)

        mock_runner = MagicMock()
        mock_runner.run = capturing_run
        director._get_runner = MagicMock(return_value=mock_runner)
        director.build_pipeline = MagicMock(return_value=MagicMock())

        await director.execute_campaign(config, campaign_id="versioned-base")
        assert "versioned-base" in captured_ids
        assert any("_iter" in cid for cid in captured_ids)

    @pytest.mark.asyncio
    async def test_degradation_aborts_after_two_consecutive_worse(self) -> None:
        """GIVEN 2 consecutive iterations with worse results than best
        WHEN execute_campaign() runs
        THEN the campaign aborts with state=CONVERGED and returns best result.
        """
        director = ResearchDirector()
        config = _make_config(max_iterations=5)
        _patch_director_deps(director, review_decision="ITERATE")

        # Override the fake run to simulate degrading selected_strategies
        call_count = 0

        async def degrading_run(pipeline, ctx, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                ctx.artifacts["selected_strategies"] = ["s1", "s2", "s3"]  # best = 3
            else:
                ctx.artifacts["selected_strategies"] = ["s1"]  # worse = 1
            ctx.artifacts["review_decision"] = "ITERATE"
            ctx.artifacts["iteration_proposal"] = {
                "action": "MODIFY_AND_RETEST",
                "parameter_changes": {"position_size": "0.5x"},
                "new_hypotheses": [],
                "rationale": "test",
                "failed_checks": ["sharpe"],
            }
            ctx.artifacts["statistics"] = {"sharpe_ratio": 1.2, "max_drawdown": 10.0}
            return _mock_pipeline_result(is_successful=True)

        mock_runner = MagicMock()
        mock_runner.run = degrading_run
        director._get_runner = MagicMock(return_value=mock_runner)
        director.build_pipeline = MagicMock(return_value=MagicMock())

        record = await director.execute_campaign(config, campaign_id="degrade-camp")
        assert record.state == CampaignState.CONVERGED
        # Should have run at most 3 iterations (best, worse1, worse2 -> abort)
        assert call_count <= 3

    @pytest.mark.asyncio
    async def test_best_result_restored_on_degradation_abort(self) -> None:
        """GIVEN degradation abort
        WHEN execute_campaign() returns
        THEN the best selected_strategies count is preserved.
        """
        director = ResearchDirector()
        config = _make_config(max_iterations=5)
        _patch_director_deps(director, review_decision="ITERATE")

        call_count = 0

        async def degrading_run(pipeline, ctx, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                ctx.artifacts["selected_strategies"] = ["s1", "s2", "s3", "s4"]
            else:
                ctx.artifacts["selected_strategies"] = ["s1"]
            ctx.artifacts["review_decision"] = "ITERATE"
            ctx.artifacts["iteration_proposal"] = {
                "action": "MODIFY_AND_RETEST",
                "parameter_changes": {"position_size": "0.5x"},
                "new_hypotheses": [],
                "rationale": "test",
                "failed_checks": ["sharpe"],
            }
            ctx.artifacts["statistics"] = {"sharpe_ratio": 1.2, "max_drawdown": 10.0}
            return _mock_pipeline_result(is_successful=True)

        mock_runner = MagicMock()
        mock_runner.run = degrading_run
        director._get_runner = MagicMock(return_value=mock_runner)
        director.build_pipeline = MagicMock(return_value=MagicMock())

        record = await director.execute_campaign(config, campaign_id="best-camp")
        # The record should reflect the best score (4 strategies)
        assert getattr(record, "best_result_score", 0) == 4


# ── E2E: full loop with mock SQX ──────────────────────────────────────────────

class TestReconfigurationLoopE2E:
    """Task 2.7: E2E full loop with mock SQX."""

    @pytest.mark.asyncio
    async def test_full_loop_uses_versioned_campaign_ids(self) -> None:
        """GIVEN a ResearchConfig with auto_iterate=True
        WHEN execute_campaign() runs 2 iterations with mocked pipeline
        THEN versioned campaign IDs are injected into context.config
        (iter00 for iteration 2; base ID for iteration 1).
        """
        director = ResearchDirector()
        config = _make_config(max_iterations=2, auto_iterate=True)

        captured_ids: list[str] = []

        async def id_capturing_run(pipeline, ctx, **kwargs):
            captured_ids.append(ctx.config.get("campaign_id", ""))
            ctx.artifacts["review_decision"] = "ITERATE"
            ctx.artifacts["iteration_proposal"] = {
                "action": "MODIFY_AND_RETEST",
                "parameter_changes": {"position_size": "0.5x"},
                "new_hypotheses": [],
                "rationale": "e2e",
                "failed_checks": ["sharpe"],
            }
            ctx.artifacts["selected_strategies"] = ["s1", "s2"]
            ctx.artifacts["statistics"] = {"sharpe_ratio": 1.5, "max_drawdown": 10.0}
            return _mock_pipeline_result(is_successful=True)

        mock_runner = MagicMock()
        mock_runner.run = id_capturing_run
        director._get_runner = MagicMock(return_value=mock_runner)
        director.build_pipeline = MagicMock(return_value=MagicMock())

        record = await director.execute_campaign(
            config, campaign_id="e2e-base"
        )

        # First iteration: base ID; second iteration: versioned
        assert captured_ids[0] == "e2e-base"
        assert captured_ids[1] == "e2e-base_iter01"
        assert record.state == CampaignState.COMPLETED
        assert len(captured_ids) == 2
