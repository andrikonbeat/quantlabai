"""Tests for BuilderAgent parameter matrix generation and orchestrated handoff."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.agents.builder_agent import BuilderAgent
from quantlab.dsl.models import Market, Timeframe
from quantlab.sqx.project_builder import BuildConfig, get_tab_for_field


def _minimal_research_config() -> dict:
    return {
        "campaign": "test_campaign",
        "market": Market.EURUSD.value,
        "timeframe": Timeframe.H1.value,
    }


class TestGetTabForField:
    """Map BuildConfig fields to SQX tab names."""

    @pytest.mark.parametrize(
        "field,expected",
        [
            ("sl_required", "MoneyManagement"),
            ("pt_required", "MoneyManagement"),
            ("sl_fixed_pips", "MoneyManagement"),
            ("min_sl_pips", "MoneyManagement"),
            ("max_sl_pips", "MoneyManagement"),
            ("sl_atr", "MoneyManagement"),
            ("min_sl_atr_multiple", "MoneyManagement"),
            ("max_sl_atr_multiple", "MoneyManagement"),
            ("min_sl_atr_period", "MoneyManagement"),
            ("max_sl_atr_period", "MoneyManagement"),
            ("pt_fixed_pips", "MoneyManagement"),
            ("min_pt_pips", "MoneyManagement"),
            ("max_pt_pips", "MoneyManagement"),
            ("pt_atr", "MoneyManagement"),
            ("min_pt_atr_multiple", "MoneyManagement"),
            ("max_pt_atr_multiple", "MoneyManagement"),
            ("min_pt_atr_period", "MoneyManagement"),
            ("max_pt_atr_period", "MoneyManagement"),
            ("limit_slpt_rrr", "MoneyManagement"),
            ("limit_slpt_rrr_from", "MoneyManagement"),
            ("limit_slpt_rrr_to", "MoneyManagement"),
            ("sl_value_type", "MoneyManagement"),
            ("pt_value_type", "MoneyManagement"),
            ("sl_indicator_based", "MoneyManagement"),
            ("pt_indicator_based", "MoneyManagement"),
            ("sl_percent", "MoneyManagement"),
            ("min_sl_percent", "MoneyManagement"),
            ("max_sl_percent", "MoneyManagement"),
            ("pt_percent", "MoneyManagement"),
            ("min_pt_percent", "MoneyManagement"),
            ("max_pt_percent", "MoneyManagement"),
            ("ranking_type", "Ranking"),
            ("ranking_avg_trades_min", "Ranking"),
            ("ranking_pf_min", "Ranking"),
            ("ranking_return_dd_min", "Ranking"),
            ("ranking_conditions_type", "Ranking"),
            ("rankings_enabled", "Ranking"),
            ("min_conditions", "What to build"),
            ("max_conditions", "What to build"),
            ("min_exit_conditions", "What to build"),
            ("max_exit_conditions", "What to build"),
            ("min_period", "What to build"),
            ("max_period", "What to build"),
            ("min_shift", "What to build"),
            ("max_shift", "What to build"),
            ("max_strategies", "What to build"),
            ("market_sides", "What to build"),
            ("entry_symmetry", "What to build"),
            ("exit_symmetry", "What to build"),
            ("generations", "Build options"),
            ("population", "Build options"),
            ("islands", "Build options"),
            ("migration_modulo", "Build options"),
            ("migration_rate", "Build options"),
            ("init_generation_type", "Build options"),
            ("decimation_coef", "Build options"),
            ("evo_restart_on_finish", "Build options"),
            ("evo_restart_on_stagnation", "Build options"),
            ("evo_restart_stagnation_fitness_type", "Build options"),
            ("evo_restart_stagnation_generations", "Build options"),
            ("evo_in_sample_period_ratio", "Build options"),
            ("fresh_blood_replace_similar", "Build options"),
            ("fresh_blood_replace_weakest", "Build options"),
            ("fresh_blood_weakest_pct", "Build options"),
            ("fresh_blood_weakest_generations", "Build options"),
            ("filter_initial_population", "Build options"),
            ("evo_fitness_restart_type", "Build options"),
            ("evo_stagnation_restart_generations", "Build options"),
            ("session", "Trading hours"),
            ("exit_at_end_of_day", "Trading hours"),
            ("eod_exit_time", "Trading hours"),
            ("exit_on_friday", "Trading hours"),
            ("friday_exit_time", "Trading hours"),
            ("limit_time_range", "Trading hours"),
            ("signal_time_range_from", "Trading hours"),
            ("signal_time_range_to", "Trading hours"),
            ("exit_at_end_of_range", "Trading hours"),
            ("max_trades_per_day", "Trading hours"),
            ("reserved_bars", "Trading hours"),
            ("store_chart_data", "Trading hours"),
            ("atms_enable", "ATMs"),
            ("atms_scale_out_type", "ATMs"),
            ("atms_size_decimals", "ATMs"),
            ("atms_min_size", "ATMs"),
            ("entry_rules_symmetry", "Parts to improve"),
            ("entry_long_improvement", "Parts to improve"),
            ("entry_short_improvement", "Parts to improve"),
            ("exit_rules_symmetry", "Parts to improve"),
            ("exit_long_improvement", "Parts to improve"),
            ("exit_short_improvement", "Parts to improve"),
            ("wf_period", "CrossChecks"),
            ("wf_optimization", "CrossChecks"),
            ("wf_param1", "CrossChecks"),
            ("wf_param2", "CrossChecks"),
            ("wf_optimize_periods", "CrossChecks"),
            ("wf_optimize_exit_types", "CrossChecks"),
            ("wf_max_tests", "CrossChecks"),
            ("wf_acceptance_threshold_pct", "CrossChecks"),
            ("wf_acceptance_min_conditions", "CrossChecks"),
            ("wf_acceptance_min_markets", "CrossChecks"),
            ("wf_acceptance_pf_min", "CrossChecks"),
            ("rc_spread", "CrossChecks"),
            ("rc_pf_min", "CrossChecks"),
            ("rc_min_conditions", "CrossChecks"),
            ("rc_min_markets", "CrossChecks"),
            ("main_test_values", "CrossChecks"),
            ("enabled_blocks", "Building blocks"),
            ("block_weights", "Building blocks"),
            ("unknown_field", "Other"),
        ],
    )
    def test_tab_mapping(self, field, expected):
        assert get_tab_for_field(field) == expected


class TestGenerateParameterMatrix:
    """BuilderAgent.generate_parameter_matrix() behavior."""

    def test_none_config_returns_empty(self):
        agent = BuilderAgent()
        assert agent.generate_parameter_matrix(None) == []

    def test_populated_config_returns_entries(self):
        agent = BuilderAgent()
        cfg = BuildConfig(
            sl_required=True,
            min_sl_pips=10,
            ranking_type="Fitness",
            generations=50,
        )
        matrix = agent.generate_parameter_matrix(cfg)
        assert len(matrix) == 4
        params = {entry["parameter"]: entry for entry in matrix}
        assert params["sl_required"]["tab"] == "MoneyManagement"
        assert params["sl_required"]["value"] is True
        assert params["sl_required"]["source"] == "orchestrator"
        assert params["sl_required"]["confidence"] == 0.7
        assert "orchestrator" in params["sl_required"]["rationale"]
        assert params["min_sl_pips"]["tab"] == "MoneyManagement"
        assert params["ranking_type"]["tab"] == "Ranking"
        assert params["generations"]["tab"] == "Build options"

    def test_hypothesis_ref_propagated(self):
        agent = BuilderAgent()
        cfg = BuildConfig(generations=50)
        cfg.hypothesis = "trend_following"
        matrix = agent.generate_parameter_matrix(cfg)
        assert len(matrix) == 1
        assert matrix[0]["hypothesis_ref"] == "trend_following"

    def test_none_fields_excluded(self):
        agent = BuilderAgent()
        cfg = BuildConfig(generations=50)
        matrix = agent.generate_parameter_matrix(cfg)
        assert len(matrix) == 1
        assert matrix[0]["parameter"] == "generations"


class TestBuilderAgentRunMatrixArtifact:
    """BuilderAgent.run() writes parameter_matrix to context artifacts."""

    @pytest.mark.asyncio
    async def test_orchestrated_mode_adds_phase_and_checkpoint(self):
        agent = BuilderAgent()
        ctx = MagicMock()
        ctx.artifacts = {"research_config": _minimal_research_config()}
        ctx.config = {
            "orchestrated": True,
            "campaign_id": "test_campaign_123",
            "build_config": BuildConfig(generations=10),
        }

        agent._translate = AsyncMock(return_value=(b"cfx", {}))
        agent._validate = AsyncMock(return_value={"valid": True})
        agent._check_license = AsyncMock(return_value={"valid": True})

        result = await agent.run(ctx)

        assert result["phase_type"] == "builder"
        assert result["checkpoint_metadata"] == {"campaign_id": "test_campaign_123"}
        assert "parameter_matrix" in ctx.artifacts
        assert len(ctx.artifacts["parameter_matrix"]) == 1
        assert ctx.artifacts["parameter_matrix"][0]["parameter"] == "generations"

    @pytest.mark.asyncio
    async def test_parameter_matrix_written_non_orchestrated(self):
        agent = BuilderAgent()
        ctx = MagicMock()
        ctx.artifacts = {"research_config": _minimal_research_config()}
        ctx.config = {
            "orchestrated": False,
            "campaign_id": "test_campaign_456",
            "build_config": BuildConfig(population=100),
        }

        agent._translate = AsyncMock(return_value=(b"cfx", {}))
        agent._validate = AsyncMock(return_value={"valid": True})
        agent._check_license = AsyncMock(return_value={"valid": True})

        dispatch_result = MagicMock()
        dispatch_result.cfx_bytes = b"cfx"
        dispatch_result.campaign_id = "test_campaign_456"
        dispatch_result.sqcli_status = "completed"
        dispatch_result.export_paths = ["exports/test.csv"]
        dispatch_result.dispatch_log = []
        agent._dispatch_with_retry = AsyncMock(return_value=dispatch_result)

        result = await agent.run(ctx)

        assert "phase_type" not in result
        assert "checkpoint_metadata" not in result
        assert "parameter_matrix" in ctx.artifacts
        assert len(ctx.artifacts["parameter_matrix"]) == 1
        assert ctx.artifacts["parameter_matrix"][0]["parameter"] == "population"
