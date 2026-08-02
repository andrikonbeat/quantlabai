"""Tests for ConfigReviewer — REQ-05 (ConfigReviewStage) + REQ-06 (HUMAN_APPROVE_CONFIG gate).

Covers:
- Verdicts: BLOCK on contradictory SL/PT risk settings, MODIFY with concrete
  diff-able ``proposed_changes``, APPROVE on a safe config.
- CostConfigReview note surfacing preset-vs-live cost profiles.
- ConfigReviewStage emits the verdict and NEVER auto-applies MODIFY changes (D3).
"""

import pytest

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.config_review_stage import ConfigReviewStage
from quantlab.sqx.project_builder import BuildConfig

from quantlab.agents.config_reviewer import ConfigReviewer, ConfigReviewVerdict


class TestConfigReviewerVerdicts:
    """REQ-05 scenario: unsafe config blocked; MODIFY carries concrete diff."""

    def test_sl_required_pt_stricter_blocks(self) -> None:
        """GIVEN SL required but PT stricter than SL (max_pt_pips < min_sl_pips)
        WHEN the reviewer reviews the BuildConfig
        THEN verdict is BLOCK with a concrete reason.
        """
        cfg = BuildConfig(
            sl_required=True,
            pt_required=True,
            min_sl_pips=30,
            max_pt_pips=10,
        )
        verdict = ConfigReviewer().review(cfg)

        assert isinstance(verdict, ConfigReviewVerdict)
        assert verdict.action == "BLOCK"
        assert "SL" in verdict.reason and "PT" in verdict.reason

    def test_inverted_rrr_range_blocks(self) -> None:
        """GIVEN an inverted RRR range (from > to) while RRR limiting is enabled
        WHEN the reviewer reviews the BuildConfig
        THEN verdict is BLOCK.
        """
        cfg = BuildConfig(
            limit_slpt_rrr=True,
            limit_slpt_rrr_from=5,
            limit_slpt_rrr_to=2,
        )
        verdict = ConfigReviewer().review(cfg)

        assert verdict.action == "BLOCK"
        assert "RRR" in verdict.reason.upper() or "risk" in verdict.reason.lower()

    def test_inverted_sl_range_blocks(self) -> None:
        """GIVEN an inverted SL pips range (min > max)
        WHEN the reviewer reviews the BuildConfig
        THEN verdict is BLOCK.
        """
        cfg = BuildConfig(
            sl_required=True,
            sl_value_type="pips",
            min_sl_pips=50,
            max_sl_pips=20,
        )
        verdict = ConfigReviewer().review(cfg)

        assert verdict.action == "BLOCK"

    def test_inverted_pt_range_blocks(self) -> None:
        """GIVEN an inverted PT pips range (min > max)
        WHEN the reviewer reviews the BuildConfig
        THEN verdict is BLOCK.
        """
        cfg = BuildConfig(
            pt_required=True,
            pt_value_type="pips",
            min_pt_pips=40,
            max_pt_pips=15,
        )
        verdict = ConfigReviewer().review(cfg)

        assert verdict.action == "BLOCK"

    def test_modify_carries_concrete_diff_when_sl_type_missing(self) -> None:
        """GIVEN SL required but no SL value type selected
        WHEN the reviewer returns MODIFY
        THEN proposed_changes are concrete BuildConfig field diffs for human review.
        """
        cfg = BuildConfig(sl_required=True, sl_value_type=None)
        verdict = ConfigReviewer().review(cfg)

        assert verdict.action == "MODIFY"
        assert verdict.proposed_changes, "MODIFY must carry concrete changes"
        assert "sl_value_type" in verdict.proposed_changes
        assert verdict.proposed_changes["sl_value_type"] in (
            "pips",
            "atr",
            "percent",
            "indicator",
        )

    def test_modify_carries_diff_when_pt_type_missing(self) -> None:
        """GIVEN PT required but no PT value type selected
        WHEN the reviewer returns MODIFY
        THEN a concrete pt_value_type diff is proposed.
        """
        cfg = BuildConfig(pt_required=True, pt_value_type=None)
        verdict = ConfigReviewer().review(cfg)

        assert verdict.action == "MODIFY"
        assert verdict.proposed_changes["pt_value_type"] in (
            "pips",
            "atr",
            "percent",
            "indicator",
        )

    def test_approve_on_safe_config(self) -> None:
        """GIVEN a BuildConfig with consistent SL/PT settings and value types
        WHEN the reviewer reviews it
        THEN verdict is APPROVE with no proposed changes.
        """
        cfg = BuildConfig(
            sl_required=True,
            sl_value_type="pips",
            min_sl_pips=20,
            max_sl_pips=50,
            pt_required=True,
            pt_value_type="pips",
            min_pt_pips=30,
            max_pt_pips=60,
        )
        verdict = ConfigReviewer().review(cfg)

        assert verdict.action == "APPROVE"
        assert verdict.proposed_changes == {}

    def test_blank_config_approves(self) -> None:
        """GIVEN a BuildConfig with no risk constraints configured
        WHEN the reviewer reviews it
        THEN verdict is APPROVE (nothing contradictory, nothing to adjust).
        """
        verdict = ConfigReviewer().review(BuildConfig())

        assert verdict.action == "APPROVE"


class TestCostConfigReviewNote:
    """REQ-05: CostConfigReview note surfaces preset-vs-live cost profiles."""

    def test_no_costs_supplied_notes_preset_assumption(self) -> None:
        """GIVEN no cost config supplied
        WHEN the reviewer builds the cost note
        THEN the note surfaces the preset-cost assumption.
        """
        verdict = ConfigReviewer().review(BuildConfig(), costs=None)

        assert verdict.cost_note, "cost note must be populated"
        assert "preset" in verdict.cost_note.lower()

    def test_live_commission_override_note(self) -> None:
        """GIVEN a live commission override on the broker preset
        WHEN the reviewer builds the cost note
        THEN the note surfaces the preset-vs-live deviation.
        """
        from quantlab.costs.models import CommissionSchema, CommissionType, CostsConfig

        costs = CostsConfig(
            broker="dukascopy",
            commission_override=CommissionSchema(
                type=CommissionType.FIXED,
                value=2.5,
            ),
        )
        verdict = ConfigReviewer().review(BuildConfig(), costs=costs)

        assert "preset" in verdict.cost_note.lower()
        assert "dukascopy" in verdict.cost_note.lower()
        assert "live" in verdict.cost_note.lower()

    def test_matching_preset_note(self) -> None:
        """GIVEN a cost config with no live overrides
        WHEN the reviewer builds the cost note
        THEN the note states the profile matches the broker preset.
        """
        from quantlab.costs.models import CostsConfig

        costs = CostsConfig(broker="dukascopy")
        verdict = ConfigReviewer().review(BuildConfig(), costs=costs)

        assert "matches" in verdict.cost_note.lower()


class TestConfigReviewStage:
    """REQ-05 stage + D3: MODIFY must never auto-apply."""

    @pytest.mark.asyncio
    async def test_stage_emits_verdict_without_auto_applying_modify(self) -> None:
        """GIVEN a BuildConfig needing adjustment (MODIFY verdict)
        WHEN ConfigReviewStage executes
        THEN the verdict artifact is written AND the in-flight build_config is
        NOT mutated (D3 — auto-apply forbidden).
        """
        stage = ConfigReviewStage()
        cfg = BuildConfig(sl_required=True, sl_value_type=None)
        ctx = PipelineContext(config={})
        ctx.artifacts["build_config"] = cfg

        output = await stage.execute(ctx)

        verdict = ctx.artifacts["config_review_verdict"]
        assert verdict["action"] == "MODIFY"
        assert output["verdict"] == "MODIFY"
        # D3: the in-flight config is untouched — the human gate decides later.
        assert cfg.sl_value_type is None

    @pytest.mark.asyncio
    async def test_stage_emits_block_verdict(self) -> None:
        """GIVEN a contradictory BuildConfig
        WHEN ConfigReviewStage executes
        THEN the verdict artifact is BLOCK.
        """
        stage = ConfigReviewStage()
        cfg = BuildConfig(
            sl_required=True,
            pt_required=True,
            min_sl_pips=30,
            max_pt_pips=10,
        )
        ctx = PipelineContext(config={})
        ctx.artifacts["build_config"] = cfg

        await stage.execute(ctx)

        assert ctx.artifacts["config_review_verdict"]["action"] == "BLOCK"

    @pytest.mark.asyncio
    async def test_stage_passes_costs_to_reviewer(self) -> None:
        """GIVEN costs provided to the stage
        WHEN ConfigReviewStage executes
        THEN the cost note reflects the live-vs-preset comparison.
        """
        from quantlab.costs.models import CommissionSchema, CommissionType, CostsConfig

        costs = CostsConfig(
            broker="dukascopy",
            commission_override=CommissionSchema(type=CommissionType.FIXED, value=1.0),
        )
        stage = ConfigReviewStage(costs=costs)
        ctx = PipelineContext(config={})
        ctx.artifacts["build_config"] = BuildConfig()

        await stage.execute(ctx)

        note = ctx.artifacts["config_review_verdict"]["cost_note"]
        assert "preset" in note.lower()
        assert "dukascopy" in note.lower()
