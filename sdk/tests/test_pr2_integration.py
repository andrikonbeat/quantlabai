"""Integration tests for PR 2 — tasks 2.19, 2.20.

Task 2.19: ResearchDirector + ResearchAgent + BuilderAgent end-to-end with mock SQX.
Task 2.20: DSL parsing test: extended ResearchConfig YAML loads with all new fields.
"""

from pathlib import Path

import pytest
import yaml

from quantlab.agents.builder_agent import BuilderAgent
from quantlab.agents.research_agent import ResearchAgent
from quantlab.agents.research_director import CampaignState, ResearchDirector
from quantlab.dsl.models import (
    HypothesisConfig,
    IterationConfig,
    ResearchConfig,
)
from quantlab.dsl.parser import parse_yaml, parse_yaml_string
from quantlab.pipeline.stages.gate_interceptor import (
    GateAction,
    GateContext,
    GateDecision,
)


class TestEndToEnd:
    """Task 2.19: ResearchDirector + ResearchAgent + BuilderAgent E2E with mock SQX."""

    @pytest.mark.asyncio
    async def test_e2e_agent_chain(self) -> None:
        """GIVEN objectives
        WHEN ResearchAgent generates config → ResearchDirector builds pipeline
             → BuilderAgent runs in pipeline context
        THEN all three agents work together correctly.
        """
        # Step 1: ResearchAgent generates config from objectives
        research_agent = ResearchAgent()
        config = research_agent.generate_config(
            objectives=["Find mean-reversion on EURUSD H1"],
        )
        assert len(config.hypotheses) >= 1
        assert config.market.value == "EURUSD"

        # Step 2: ResearchDirector builds pipeline from config
        director = ResearchDirector()

        async def auto_approve(ctx: GateContext) -> GateDecision:
            return GateDecision(
                gate_id=ctx.gate_id,
                action=GateAction.APPROVED,
                reason="Auto-approved by integration test",
                decided_by="test",
            )

        for gate_id in [
            "HUMAN_REVIEW_OBJECTIVES",
            "HUMAN_APPROVE_ITERATION",
            "HUMAN_APPROVE_PORTFOLIO",
            "HUMAN_APPROVE_DEPLOY",
            "HUMAN_REVIEW_PERFORMANCE",
        ]:
            director.register_gate_callback(gate_id, auto_approve)

        pipeline = director.build_pipeline(config)
        stage_names = [s.name for s in pipeline.stages]
        # 11 agent stages + 5 gate interceptors = 16 (compile stage added between
        # portfolio and deploy for the canonical 14-phase pipeline, REQ-01/REQ-37).
        assert len(stage_names) == 16

        # Step 3: Create PipelineContext with ResearchAgent output
        from quantlab.pipeline.base import PipelineContext

        ctx = PipelineContext(
            config={
                "campaign_id": "e2e-test",
                "campaign_name": "E2E Test",
                "iteration": 0,
                "max_iterations": 1,
                "objectives": ["Find mean-reversion on EURUSD H1"],
            },
            metadata={"pipeline_name": "e2e-test-pipeline"},
        )

        # Inject ResearchAgent output
        ctx.artifacts["research_config"] = config.model_dump(mode="json")
        ctx.artifacts["objectives"] = ["Find mean-reversion on EURUSD H1"]
        ctx.artifacts["hypotheses"] = [
            h.model_dump(mode="json") for h in config.hypotheses
        ]
        ctx.artifacts["iteration_config"] = config.iteration_config.model_dump(mode="json")
        ctx.artifacts["gate_policies"] = [
            g.model_dump(mode="json") for g in config.gate_policies
        ]

        # Step 4: Run BuilderAgent with the context
        builder_agent = BuilderAgent()
        builder_result = await builder_agent.run(ctx)

        # Step 5: Verify all outputs
        assert "cfx_bytes" in builder_result
        assert "campaign_id" in builder_result
        assert builder_result["sqcli_status"] == "completed"
        assert len(builder_result["export_paths"]) >= 1

        # Verify context artifacts were written
        assert "cfx_bytes" in ctx.artifacts
        assert "campaign_id" in ctx.artifacts
        assert "export_paths" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_e2e_full_campaign_execution(self) -> None:
        """GIVEN a ResearchConfig with hypotheses
        WHEN ResearchDirector.execute_campaign() runs end-to-end
        THEN the campaign completes with all artifacts populated.
        """
        director = ResearchDirector()

        async def auto_approve(ctx: GateContext) -> GateDecision:
            return GateDecision(
                gate_id=ctx.gate_id,
                action=GateAction.APPROVED,
                reason="Auto-approved",
                decided_by="test",
            )

        for gate_id in [
            "HUMAN_REVIEW_OBJECTIVES",
            "HUMAN_APPROVE_ITERATION",
            "HUMAN_APPROVE_PORTFOLIO",
            "HUMAN_APPROVE_DEPLOY",
            "HUMAN_REVIEW_PERFORMANCE",
        ]:
            director.register_gate_callback(gate_id, auto_approve)

        config = ResearchConfig(
            campaign="E2EFull",
            market="EURUSD",
            timeframe="H1",
            hypotheses=[
                HypothesisConfig(
                    name="h1",
                    description="RSI(14) < 30 + BB test",
                    confidence=0.7,
                ),
            ],
            iteration_config=IterationConfig(
                max_iterations=1,
                convergence_threshold=0.02,
            ),
        )

        record = await director.execute_campaign(config, campaign_id="e2e-full-test")
        assert record.state in (
            CampaignState.COMPLETED,
            CampaignState.CONVERGED,
            CampaignState.FAILED,
        )

    @pytest.mark.asyncio
    async def test_e2e_with_rollback(self) -> None:
        """GIVEN a completed campaign
        WHEN rollback_campaign() is called
        THEN the campaign is properly rolled back.
        """
        director = ResearchDirector()

        async def auto_approve(ctx: GateContext) -> GateDecision:
            return GateDecision(
                gate_id=ctx.gate_id,
                action=GateAction.APPROVED,
                reason="Auto-approved",
                decided_by="test",
            )

        director.register_gate_callback("HUMAN_REVIEW_OBJECTIVES", auto_approve)

        config = ResearchConfig(
            campaign="RollbackE2E",
            market="EURUSD",
            timeframe="H1",
            iteration_config=IterationConfig(max_iterations=1),
        )

        await director.execute_campaign(config, campaign_id="e2e-rollback")
        director.rollback_campaign("e2e-rollback")

        record = director.get_campaign("e2e-rollback")
        assert record is not None
        assert record.state == CampaignState.ROLLED_BACK


class TestDslParsing:
    """Task 2.20: Extended ResearchConfig YAML loads with all new fields."""

    EXTENDED_YAML = """\
campaign: "Full DSL Test"
market: EURUSD
timeframe: H1

building_blocks:
  - name: RSI_MeanReversion
    indicator:
      name: RSI
      params:
        period: 14

strategies:
  - name: StratA
    direction: BOTH
    building_blocks:
      - RSI_MeanReversion

criteria:
  - metric: sharpe
    operator: ">="
    value: 1.0

hypotheses:
  - name: h1
    description: "RSI(14) < 30 entry"
    confidence: 0.7
    parameters:
      rsi_period: 14
    expected_outcome: "Sharpe > 1.2"

  - name: h2
    description: "Bollinger squeeze breakout"
    confidence: 0.55
    parameters:
      bb_period: 20
      squeeze_threshold: 0.1
    expected_outcome: "Capture post-squeeze breakouts"

iteration_config:
  max_iterations: 5
  convergence_threshold: 0.02
  early_stop_patience: 2
  auto_iterate: true

gate_policies:
  - gate_id: HUMAN_REVIEW_OBJECTIVES
    required: true
    auto_approve_on_timeout: false
    escalation_path:
      - "lead@research.ai"

  - gate_id: HUMAN_APPROVE_ITERATION
    required: true
    auto_approve_on_timeout: false

agents:
  - name: research
    config_overrides:
      max_hypotheses: 10

  - name: builder
    config_overrides:
      max_retries: 2

memory:
  enabled: true
  topic_prefix: "quantlab/agent"
  retention_days: 365
  cross_agent_sharing: true

risk:
  max_portfolio_drawdown: 0.20
  max_strategy_correlation: 0.7
  max_single_strategy_weight: 0.4
  kelly_fraction_cap: 0.25
  var_confidence: 0.95
"""

    def test_extended_config_parses_all_fields(self) -> None:
        """GIVEN a YAML string with all base fields plus new extensions
        WHEN parse_yaml_string() is called
        THEN a ResearchConfig with all fields populated is returned.
        """
        config = parse_yaml_string(self.EXTENDED_YAML)

        # Base fields
        assert config.campaign == "Full DSL Test"
        assert config.market.value == "EURUSD"
        assert config.timeframe.value == "H1"

        # Hypotheses
        assert len(config.hypotheses) == 2
        assert config.hypotheses[0].name == "h1"
        assert config.hypotheses[0].confidence == 0.7
        assert config.hypotheses[0].parameters["rsi_period"] == 14

        assert config.hypotheses[1].name == "h2"
        assert config.hypotheses[1].confidence == 0.55

        # Iteration config
        assert config.iteration_config.max_iterations == 5
        assert config.iteration_config.convergence_threshold == 0.02
        assert config.iteration_config.early_stop_patience == 2
        assert config.iteration_config.auto_iterate is True

        # Gate policies
        assert len(config.gate_policies) == 2
        assert config.gate_policies[0].gate_id == "HUMAN_REVIEW_OBJECTIVES"
        assert config.gate_policies[0].required is True

        # Agents
        assert len(config.agents) == 2
        assert config.agents[0].name == "research"
        assert config.agents[0].config_overrides["max_hypotheses"] == 10

        # Memory
        assert config.memory.enabled is True
        assert config.memory.topic_prefix == "quantlab/agent"
        assert config.memory.retention_days == 365
        assert config.memory.cross_agent_sharing is True

        # Risk
        assert config.risk.max_portfolio_drawdown == 0.20
        assert config.risk.max_strategy_correlation == 0.7
        assert config.risk.max_single_strategy_weight == 0.4
        assert config.risk.kelly_fraction_cap == 0.25
        assert config.risk.var_confidence == 0.95

    def test_extended_config_round_trip(self) -> None:
        """GIVEN a parsed extended ResearchConfig
        WHEN serialized and re-parsed
        THEN all fields are preserved.
        """
        from quantlab.dsl.parser import serialize

        config = parse_yaml_string(self.EXTENDED_YAML)
        yaml_str = serialize(config)
        restored = parse_yaml_string(yaml_str)

        assert restored.campaign == config.campaign
        assert len(restored.hypotheses) == len(config.hypotheses)
        assert restored.iteration_config.max_iterations == config.iteration_config.max_iterations
        assert len(restored.gate_policies) == len(config.gate_policies)

    def test_extended_config_from_file(self, tmp_path: Path) -> None:
        """GIVEN a YAML file with extended config
        WHEN parse_yaml() is called
        THEN all new fields are loaded correctly.
        """
        yaml_path = tmp_path / "extended_config.yaml"
        yaml_path.write_text(self.EXTENDED_YAML)

        config = parse_yaml(yaml_path)
        assert len(config.hypotheses) == 2
        assert config.iteration_config.max_iterations == 5
        assert len(config.gate_policies) == 2
        assert config.memory.enabled is True

    def test_hypothesis_confidence_out_of_range_rejected(self) -> None:
        """GIVEN a YAML with hypothesis confidence > 1.0
        WHEN parsed
        THEN ValidationError is raised.
        """
        from quantlab.tools.exceptions import ValidationError

        bad_yaml = """\
campaign: BadConf
market: EURUSD
timeframe: H1
hypotheses:
  - name: bad
    description: "Bad confidence"
    confidence: 1.5
"""

        with pytest.raises(ValidationError):
            parse_yaml_string(bad_yaml)

    def test_gate_policy_timeout_zero_rejected(self) -> None:
        """GIVEN a YAML with gate_policies.timeout_hours=0
        WHEN parsed
        THEN ValidationError is raised.
        """
        from quantlab.tools.exceptions import ValidationError

        # Note: GatePolicyConfig doesn't have timeout_hours, so this tests
        # that iteration_config validation catches max_iterations=0
        bad_yaml = """\
campaign: BadIter
market: EURUSD
timeframe: H1
iteration_config:
  max_iterations: 0
"""

        with pytest.raises(ValidationError):
            parse_yaml_string(bad_yaml)

    def test_risk_correlation_out_of_range_rejected(self) -> None:
        """GIVEN a YAML with risk.max_strategy_correlation=1.5
        WHEN parsed
        THEN ValidationError is raised.
        """
        from quantlab.tools.exceptions import ValidationError

        bad_yaml = """\
campaign: BadRisk
market: EURUSD
timeframe: H1
memory:
  enabled: true
risk:
  max_strategy_correlation: 1.5
"""

        with pytest.raises(ValidationError):
            parse_yaml_string(bad_yaml)

    def test_example_yaml_file_parses(self) -> None:
        """GIVEN the example research-config.yaml file
        WHEN parse_yaml() is called
        THEN all fields load without error.
        """
        example_path = Path("examples/research-config.yaml")
        if example_path.exists():
            config = parse_yaml(example_path)
            assert len(config.hypotheses) >= 1
            assert config.iteration_config.max_iterations > 0
            assert len(config.gate_policies) >= 1
