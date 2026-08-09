"""Tests for BuilderAgent parameter matrix generation and orchestrated handoff.

Covers the spec scenarios:
- Build with defaults produces matrix (source="default", rationale "using SQX default")
- Manual override requires justification (source="manual", non-empty rationale)
- Missing rationale blocks advancement (ParameterMatrixError raised, run blocked)
- Handoff failure preserves build artifact (CFX + matrix persisted to Knowledge
  Lake before the dispatch boundary so a handoff failure leaves them recoverable).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.agents.builder_agent import BuilderAgent, ParameterMatrixError
from quantlab.dsl.models import Market, Timeframe
from quantlab.sqx.project_builder import (
    BuildConfig,
    get_tab_for_field,
    get_template_default,
)


def _minimal_research_config() -> dict:
    return {
        "campaign": "test_campaign",
        "market": Market.EURUSD.value,
        "timeframe": Timeframe.H1.value,
    }


class TestGetTabForField:
    """Map BuildConfig fields to their SQX tab (dataclass section) names."""

    @pytest.mark.parametrize(
        "field,expected",
        [
            # ── Trading hours (BuildTradingOptions) ──
            ("exit_at_end_of_day", "Trading hours"),
            ("eod_exit_time", "Trading hours"),
            ("exit_on_friday", "Trading hours"),
            ("friday_exit_time", "Trading hours"),
            ("limit_time_range", "Trading hours"),
            ("signal_time_range_from", "Trading hours"),
            ("signal_time_range_to", "Trading hours"),
            ("exit_at_end_of_range", "Trading hours"),
            ("max_trades_per_day", "Trading hours"),
            ("session", "Trading hours"),
            ("reserved_bars", "Trading hours"),
            ("store_chart_data", "Trading hours"),
            # ── What to build (Rules Complexity / Market Sides) ──
            ("min_conditions", "What to build"),
            ("max_conditions", "What to build"),
            ("min_exit_conditions", "What to build"),
            ("max_exit_conditions", "What to build"),
            ("min_period", "What to build"),
            ("max_period", "What to build"),
            ("min_shift", "What to build"),
            ("max_shift", "What to build"),
            ("market_sides", "What to build"),
            ("entry_symmetry", "What to build"),
            ("exit_symmetry", "What to build"),
            # ── MoneyManagement (SL/PT Options) ──
            ("sl_required", "MoneyManagement"),
            ("sl_fixed_pips", "MoneyManagement"),
            ("min_sl_pips", "MoneyManagement"),
            ("max_sl_pips", "MoneyManagement"),
            ("min_sl_money", "MoneyManagement"),
            ("max_sl_money", "MoneyManagement"),
            ("sl_atr", "MoneyManagement"),
            ("min_sl_atr_multiple", "MoneyManagement"),
            ("max_sl_atr_multiple", "MoneyManagement"),
            ("min_sl_atr_period", "MoneyManagement"),
            ("max_sl_atr_period", "MoneyManagement"),
            ("pt_required", "MoneyManagement"),
            ("pt_fixed_pips", "MoneyManagement"),
            ("min_pt_pips", "MoneyManagement"),
            ("max_pt_pips", "MoneyManagement"),
            ("min_pt_money", "MoneyManagement"),
            ("max_pt_money", "MoneyManagement"),
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
            # ── Build options (Genetic) ──
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
            # ── Ranking ──
            ("max_strategies", "Ranking"),
            ("ranking_type", "Ranking"),
            ("ranking_avg_trades_min", "Ranking"),
            ("ranking_pf_min", "Ranking"),
            ("ranking_return_dd_min", "Ranking"),
            ("ranking_conditions_type", "Ranking"),
            # ── MoneyManagement ──
            ("mm_method", "Other"),
            ("mm_lot_size", "Other"),
            ("initial_capital", "Other"),
            ("mm_risk_pct", "Other"),
            ("mm_max_drawdown", "Other"),
            # ── ATMs ──
            ("atms_enable", "ATMs"),
            ("atms_scale_out_type", "ATMs"),
            ("atms_size_decimals", "ATMs"),
            ("atms_min_size", "ATMs"),
            # ── Parts to improve ──
            ("entry_rules_symmetry", "Parts to improve"),
            ("entry_long_improvement", "Parts to improve"),
            ("entry_short_improvement", "Parts to improve"),
            ("exit_rules_symmetry", "Parts to improve"),
            ("exit_long_improvement", "Parts to improve"),
            ("exit_short_improvement", "Parts to improve"),
            # ── CrossChecks ──
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
            # ── Blocks bridge ──
            ("enabled_blocks", "Blocks bridge"),
            ("block_weights", "Blocks bridge"),
            ("unknown_field", "Other"),
        ],
    )
    def test_tab_mapping(self, field, expected):
        assert get_tab_for_field(field) == expected


class TestGenerateParameterMatrix:
    """BuilderAgent.generate_parameter_matrix() — spec source semantics."""

    def test_none_config_returns_empty(self):
        agent = BuilderAgent()
        assert agent.generate_parameter_matrix(None) == []

    def test_default_values_marked_default_with_sqx_rationale(self):
        """GIVEN a BuildConfig value that matches the SQX template default
        THEN the entry has source "default" and rationale "using SQX default"
        (spec scenario "Build with defaults produces matrix").
        """
        # Ground truth from the bundled default-project template:
        assert get_template_default("sl_atr") is False
        assert get_template_default("exit_at_end_of_day") is False
        matrix = BuilderAgent().generate_parameter_matrix(BuildConfig(sl_atr=False))
        assert len(matrix) == 1
        entry = matrix[0]
        assert entry["parameter"] == "sl_atr"
        assert entry["value"] is False
        assert entry["source"] == "default"
        assert entry["rationale"] == "using SQX default"
        assert entry["confidence"] == 0.9

    def test_manual_override_requires_justification(self):
        """GIVEN a manual override with a non-empty rationale
        THEN the entry has a non-empty rationale and source "manual"
        (spec scenario "Manual override requires justification").
        """
        matrix = BuilderAgent().generate_parameter_matrix(
            BuildConfig(sl_atr=True),
            rationale_overrides={"sl_atr": "ATR stop-loss for regime A"},
        )
        assert len(matrix) == 1
        entry = matrix[0]
        assert entry["parameter"] == "sl_atr"
        assert entry["source"] == "manual"
        assert entry["rationale"] == "ATR stop-loss for regime A"
        assert entry["confidence"] == 0.7

    def test_missing_rationale_raises_parameter_matrix_error(self):
        """GIVEN a manual override with no rationale
        WHEN the matrix is generated
        THEN ParameterMatrixError is raised (spec: "Missing rationale blocks
        advancement").
        """
        # sl_atr template default is false — setting it True is a manual
        # override that MUST be justified.
        with pytest.raises(ParameterMatrixError, match="sl_atr"):
            BuilderAgent().generate_parameter_matrix(BuildConfig(sl_atr=True))

    def test_blank_rationale_raises_parameter_matrix_error(self):
        """GIVEN a manual override with a whitespace-only rationale
        THEN ParameterMatrixError is raised.
        """
        with pytest.raises(ParameterMatrixError):
            BuilderAgent().generate_parameter_matrix(
                BuildConfig(sl_atr=True),
                rationale_overrides={"sl_atr": "   "},
            )

    def test_hypothesis_ref_propagated(self):
        agent = BuilderAgent()
        cfg = BuildConfig(generations=50)
        cfg.hypothesis = "trend_following"
        matrix = agent.generate_parameter_matrix(
            cfg,
            rationale_overrides={"generations": "population search depth"},
        )
        assert len(matrix) == 1
        assert matrix[0]["hypothesis_ref"] == "trend_following"

    def test_none_fields_excluded(self):
        agent = BuilderAgent()
        matrix = agent.generate_parameter_matrix(
            BuildConfig(generations=50),
            rationale_overrides={"generations": "population search depth"},
        )
        assert len(matrix) == 1
        assert matrix[0]["parameter"] == "generations"

    def test_populated_config_returns_mixed_sources(self):
        agent = BuilderAgent()
        cfg = BuildConfig(
            exit_at_end_of_day=False,  # == template default → "default"
            sl_atr=True,               # template default false → manual override
            min_sl_pips=10,            # template default 30 → manual override
            ranking_type="Fitness",    # template default ReturnDDRatio → manual
            generations=50,            # template default 100 → manual override
        )
        matrix = agent.generate_parameter_matrix(
            cfg,
            rationale_overrides={
                "sl_atr": "ATR stop-loss for regime A",
                "min_sl_pips": "tighten to 10 pips for M1",
                "ranking_type": "rank by fitness",
                "generations": "search depth 50",
            },
        )
        assert len(matrix) == 5
        params = {entry["parameter"]: entry for entry in matrix}
        assert params["exit_at_end_of_day"]["tab"] == "Trading hours"
        assert params["exit_at_end_of_day"]["value"] is False
        assert params["exit_at_end_of_day"]["source"] == "default"
        assert params["sl_atr"]["tab"] == "MoneyManagement"
        assert params["sl_atr"]["source"] == "manual"
        assert params["min_sl_pips"]["tab"] == "MoneyManagement"
        assert params["min_sl_pips"]["source"] == "manual"
        assert params["ranking_type"]["tab"] == "Ranking"
        assert params["generations"]["tab"] == "Build options"
        assert params["generations"]["source"] == "manual"


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
            "rationale_overrides": {"generations": "population search depth"},
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
        assert ctx.artifacts["parameter_matrix"][0]["source"] == "manual"

    @pytest.mark.asyncio
    async def test_parameter_matrix_written_non_orchestrated(self):
        agent = BuilderAgent()
        ctx = MagicMock()
        ctx.artifacts = {"research_config": _minimal_research_config()}
        ctx.config = {
            "orchestrated": False,
            "campaign_id": "test_campaign_456",
            "build_config": BuildConfig(population=100),
            "rationale_overrides": {"population": "population size 100"},
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

    @pytest.mark.asyncio
    async def test_run_blocks_when_manual_override_lacks_rationale(self):
        """GIVEN a build config with an unjustified manual override
        WHEN the orchestrated run generates the matrix
        THEN ParameterMatrixError propagates and the run is blocked from
        advancing (spec scenario "Missing rationale blocks advancement").
        """
        agent = BuilderAgent()
        ctx = MagicMock()
        ctx.artifacts = {"research_config": _minimal_research_config()}
        ctx.config = {
            "orchestrated": True,
            "campaign_id": "test_campaign_999",
            "build_config": BuildConfig(sl_atr=True),  # template default false — no rationale
        }

        agent._translate = AsyncMock(return_value=(b"cfx", {}))
        agent._validate = AsyncMock(return_value={"valid": True})
        agent._check_license = AsyncMock(return_value={"valid": True})

        with pytest.raises(ParameterMatrixError):
            await agent.run(ctx)


class TestBuildArtifactPersistence:
    """builder-agent REQ-2: CFX + matrix persist to Knowledge Lake before handoff."""

    @pytest.mark.asyncio
    async def test_orchestrated_run_persists_cfx_and_matrix_before_handoff(self, tmp_path):
        """GIVEN an orchestrated run with a knowledge root
        WHEN the builder finishes (before the dispatch boundary)
        THEN the CFX archive and matrix are on disk for recovery — a later
        handoff failure leaves the build artifact preserved.
        """
        agent = BuilderAgent()
        ctx = MagicMock()
        ctx.artifacts = {"research_config": _minimal_research_config()}
        ctx.config = {
            "orchestrated": True,
            "campaign_id": "persist_001",
            "knowledge_root": str(tmp_path / "knowledge"),
            "build_config": BuildConfig(generations=10),
            "rationale_overrides": {"generations": "population search depth"},
        }

        agent._translate = AsyncMock(return_value=(b"cfx-bytes-content", {}))
        agent._validate = AsyncMock(return_value={"valid": True})
        agent._check_license = AsyncMock(return_value={"valid": True})

        result = await agent.run(ctx)

        assert result["phase_type"] == "builder"
        cfx_file = (
            tmp_path / "knowledge" / "structured" / "persist_001" / "configs" / "persist_001.cfx"
        )
        assert cfx_file.is_file(), "CFX archive must be preserved before handoff"
        assert cfx_file.read_bytes() == b"cfx-bytes-content"
        matrix_file = (
            tmp_path / "knowledge" / "parameter-matrix" / "persist_001" / "parameter_matrix.json"
        )
        assert matrix_file.is_file(), "parameter matrix must be persisted to the lake"
