"""Pydantic models for the QuantLab research DSL.

Defines the domain model for quantitative research campaigns:
markets, timeframes, strategy building blocks, and acceptance criteria.

Extended for multi-agent pipeline with agent configs, gate configs, memory, and risk.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from quantlab.costs.models import CostsConfig


# ── Enums ──────────────────────────────────────────────────────────────────────


class Market(str, Enum):
    """Recognised financial markets."""

    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    USDJPY = "USDJPY"
    AUDUSD = "AUDUSD"
    USDCAD = "USDCAD"
    USDCHF = "USDCHF"
    NZDUSD = "NZDUSD"
    EURGBP = "EURGBP"
    EURJPY = "EURJPY"
    GBPJPY = "GBPJPY"

    # Indices
    SP500 = "SP500"
    NASDAQ = "NASDAQ"
    DOWJONES = "DOWJONES"
    DAX = "DAX"
    FTSE100 = "FTSE100"

    # Commodities
    XAUUSD = "XAUUSD"
    XAGUSD = "XAGUSD"
    BTCUSD = "BTCUSD"
    ETHUSD = "ETHUSD"


class Timeframe(str, Enum):
    """Recognised chart timeframes."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"
    MN = "MN"


class StrategyDirection(str, Enum):
    """Direction a strategy may trade."""

    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


# ── Building blocks ────────────────────────────────────────────────────────────


class IndicatorConfig(BaseModel):
    """Configuration for a single technical indicator.

    Examples:
        - ``{name: "RSI", params: {period: 14}}``
        - ``{name: "EMA", params: {period: 200}}``
    """

    name: str = Field(..., description="Indicator name (e.g. RSI, EMA, BB)")
    params: dict[str, Any] = Field(default_factory=dict, description="Indicator parameters")


class EntryRule(BaseModel):
    """Condition that triggers a trade entry."""

    description: str = Field(..., description="Human-readable rule description")
    conditions: list[str] = Field(default_factory=list, description="Condition expressions")


class ExitRule(BaseModel):
    """Condition that triggers a trade exit."""

    description: str = Field(..., description="Human-readable rule description")
    conditions: list[str] = Field(default_factory=list, description="Condition expressions")


class BuildingBlock(BaseModel):
    """A reusable trading logic component (indicator + rules)."""

    name: str = Field(..., description="Unique building-block name")
    indicator: IndicatorConfig
    entry: EntryRule | None = None
    exit: ExitRule | None = None


# ── Acceptance criteria ────────────────────────────────────────────────────────


class AcceptanceCriterion(BaseModel):
    """A measurable acceptance criterion for a research campaign."""

    metric: str = Field(..., description="Metric name (e.g. profit_factor, sharpe)")
    operator: str = Field(..., description="Comparison operator (>, >=, <, <=, ==)")
    value: float = Field(..., description="Threshold value")


# ── Strategy ────────────────────────────────────────────────────────────────────


class Strategy(BaseModel):
    """A named strategy composed of building blocks."""

    name: str = Field(..., description="Unique strategy name within campaign")
    direction: StrategyDirection = StrategyDirection.BOTH
    building_blocks: list[str] = Field(
        default_factory=list,
        description="Names of building blocks this strategy uses",
    )


# ── Extended configs for multi-agent pipeline ──────────────────────────────────


class LLMConfig(BaseModel):
    """Configuration for an LLM provider used in research agent.

    Provider validation ensures only known vendors are accepted.
    ``api_key_env`` is auto-derived from the provider name when not explicitly set.

    ``provider="opencode"`` targets the **OpenCode Zen** free tier by default:
    ``base_url`` defaults to ``https://opencode.ai/zen/v1`` and ``model`` to
    ``deepseek-v4-flash-free`` (both overridable explicitly). This is the
    standalone/headless SDK research path; the orchestrated campaign flow
    consumes the OpenCode subagent's own model and never needs an API key.

    Attributes:
        provider: LLM provider name (``"openai"``, ``"anthropic"``, or ``"opencode"``).
        model: Model identifier (e.g. ``"gpt-4"``, ``"claude-3-opus-20240229"``,
            ``"deepseek-v4-flash-free"``).
        api_key_env: Environment variable holding the API key.
        base_url: Optional custom API base URL (e.g. for Ollama, OpenCode local).
        temperature: Sampling temperature 0.0–2.0 (default 0.7).
        max_tokens: Maximum output tokens (default 2048, must be >= 1).
        web_sources: Enabled web/news sources for context enrichment.
    """

    VALID_PROVIDERS: set[str] = {"openai", "anthropic", "opencode"}
    _PROVIDER_ENV_MAP: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "opencode": "OPENCODE_API_KEY",
    }
    # OpenCode Zen free-tier defaults for provider="opencode" (standalone/headless
    # SDK research only). Explicit values always win.
    _OPENCODE_ZEN_BASE_URL: str = "https://opencode.ai/zen/v1"
    _OPENCODE_ZEN_MODEL: str = "deepseek-v4-flash-free"

    provider: str = Field(
        default="openai",
        description="LLM provider name",
    )
    model: str = Field(default="gpt-4", description="Model identifier")
    api_key_env: str = Field(default="OPENAI_API_KEY", description="Env var for the API key")
    base_url: str | None = Field(
        default=None,
        description="Custom API base URL. For provider='opencode' this defaults "
        "to OpenCode Zen (https://opencode.ai/zen/v1); pass e.g. "
        "http://localhost:11434/v1 to override with a local Ollama server",
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature 0.0–2.0"
    )
    max_tokens: int = Field(
        default=2048, ge=1, description="Maximum output tokens"
    )
    web_sources: list[str] = Field(
        default_factory=list,
        description="Enabled web/news sources for context enrichment",
    )

    @model_validator(mode="after")
    def _validate_provider_and_derive_env(self) -> LLMConfig:
        """Validate provider is known and derive default api_key_env."""
        if self.provider not in self.VALID_PROVIDERS:
            from quantlab.tools.exceptions import ValidationError

            raise ValidationError(
                f"Unknown LLM provider '{self.provider}'. "
                f"Valid providers: {', '.join(sorted(self.VALID_PROVIDERS))}"
            )
        # Auto-derive api_key_env from provider if not explicitly overridden
        derived = self._PROVIDER_ENV_MAP.get(self.provider, f"{self.provider.upper()}_API_KEY")
        # If api_key_env is the default string, derive it; otherwise respect explicit value
        if self.api_key_env == "OPENAI_API_KEY" and self.provider != "openai":
            self.api_key_env = derived
        # OpenCode Zen defaults: point the standalone SDK research path at the
        # free OpenCode Zen endpoint + model. An explicit base_url/model is
        # preserved; only the unset (or field-default) value is replaced.
        if self.provider == "opencode":
            if self.base_url is None or self.base_url == "":
                self.base_url = self._OPENCODE_ZEN_BASE_URL
            if self.model == "gpt-4":  # field default → Zen free model
                self.model = self._OPENCODE_ZEN_MODEL
        return self


class HypothesisConfig(BaseModel):
    """A research hypothesis with testable parameters.

    Extended for LLM agent integration with audit fields:
    ``llm_rationale``, ``source_urls``, and ``data_sources``.
    """

    name: str = Field(..., description="Hypothesis identifier")
    description: str = Field(..., description="What this hypothesis tests")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Hypothesis parameters")
    expected_outcome: str = Field(default="", description="Expected result if hypothesis holds")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Prior confidence 0-1")

    # LLM audit trail fields
    llm_rationale: str | None = Field(
        default=None, description="LLM reasoning that generated this hypothesis"
    )
    source_urls: list[str] = Field(
        default_factory=list, description="URLs used as evidence for this hypothesis"
    )
    data_sources: list[str] = Field(
        default_factory=list, description="Provider names that supplied the data"
    )


class IterationConfig(BaseModel):
    """Configuration for iterative research loops."""

    max_iterations: int = Field(default=5, ge=1, le=50, description="Maximum iteration cycles")
    convergence_threshold: float = Field(default=0.01, gt=0.0, description="Improvement threshold to stop")
    early_stop_patience: int = Field(default=2, ge=0, description="Iterations without improvement before stop")
    auto_iterate: bool = Field(default=True, description="Automatically iterate on ITERATE decision")


class GatePolicyConfig(BaseModel):
    """Policy for a specific gate in the pipeline."""

    gate_id: str = Field(..., description="Gate identifier (e.g., HUMAN_REVIEW_OBJECTIVES)")
    required: bool = Field(default=True, description="Whether gate must pass")
    auto_approve_on_timeout: bool = Field(default=False, description="Auto-approve if timeout")
    escalation_path: list[str] = Field(default_factory=list, description="Escalation contacts")


class AgentRefConfig(BaseModel):
    """Reference to an agent with optional config override."""

    name: str = Field(..., description="Agent name (research, builder, statistics, review, portfolio, deploy, monitor)")
    config_overrides: dict[str, Any] = Field(default_factory=dict, description="Override agent default config")


class MemoryConfig(BaseModel):
    """Engram agent memory configuration."""

    enabled: bool = Field(default=True, description="Enable agent memory persistence")
    topic_prefix: str = Field(default="quantlab/agent", description="Engram topic prefix")
    retention_days: int = Field(default=365, gt=0, description="Memory retention period")
    cross_agent_sharing: bool = Field(default=True, description="Allow cross-agent memory access")


class RiskConfig(BaseModel):
    """Portfolio risk limits configuration."""

    max_portfolio_drawdown: float = Field(default=0.20, gt=0.0, le=1.0, description="Max portfolio drawdown")
    max_strategy_correlation: float = Field(default=0.7, ge=0.0, le=1.0, description="Max pairwise strategy correlation")
    max_single_strategy_weight: float = Field(default=0.4, gt=0.0, le=1.0, description="Max weight per strategy")
    kelly_fraction_cap: float = Field(default=0.25, gt=0.0, le=1.0, description="Kelly fraction cap")
    var_confidence: float = Field(default=0.95, gt=0.0, lt=1.0, description="VaR confidence level")


class AnalysisConfig(BaseModel):
    """Thresholds and weights for the analysis stage."""

    min_trades: int = Field(default=50, ge=0, description="Minimum trades to avoid extreme-metric flag")
    extreme_pf: float = Field(default=3.0, gt=0.0, description="Profit factor above this is extreme with low trades")
    extreme_sharpe: float = Field(default=2.0, gt=0.0, description="Sharpe above this is extreme with low trades")
    oos_is_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum OOS/IS Sharpe ratio")
    score_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "pf_weight": 0.25,
            "sharpe_weight": 0.20,
            "win_rate_weight": 0.15,
            "mdd_weight": 0.15,
            "mar_weight": 0.10,
            "recovery_weight": 0.10,
            "expectancy_weight": 0.05,
        },
        description="Per-metric weights for composite score (must sum to 1.0)",
    )


# ── Retest / Optimize blocks (REQ-19) ─────────────────────────────────────────


class RetestBlock(BaseModel):
    """Optional ``retest`` block for a research campaign (REQ-19).

    Mirrors ``RetesterConfig`` (``quantlab.phase4.retester``) plus
    ``max_iterations`` for the bounded retest loop. When ``max_iterations`` is
    None the loop uses ``ResearchConfig.iteration_config.max_iterations``.
    """

    strategy_id: str = Field(..., description="Strategy to retest")
    databanks: list[str] = Field(..., description="Databank names to retest against")
    monte_carlo_runs: int = Field(default=100, description="Monte Carlo reruns")
    mc_percentile: int = Field(default=95, description="Monte Carlo percentile")
    walkforward_cycles: int = Field(default=5, description="Walk-forward cycles")
    min_trades: int = Field(default=30, description="Minimum trades to accept")
    confidence_level: float = Field(default=0.95, description="Confidence level")
    broker_profile: Any | None = Field(default=None, description="Broker profile override")
    cost_config: Any | None = Field(default=None, description="Cost config override")
    max_iterations: int | None = Field(
        default=None,
        description="Bounded retest iterations (falls back to iteration_config)",
    )


class OptimizeBlock(BaseModel):
    """Optional ``optimize`` block for a research campaign (REQ-19).

    Mirrors ``OptimizerConfig`` (``quantlab.phase4.optimizer``).
    """

    strategy_id: str = Field(..., description="Strategy to optimize")
    method: str = Field(default="Genetic", description="Optimization method")
    objective: str = Field(default="SharpeRatio", description="Optimization objective")
    walkforward_cycles: int = Field(default=10, description="Walk-forward cycles")
    population: int = Field(default=100, description="Population size")
    generations: int = Field(default=50, description="Generation count")
    crossover: float = Field(default=0.8, description="Crossover probability")
    mutation: float = Field(default=0.1, description="Mutation probability")
    databanks: list[str] | None = Field(default=None, description="Databanks to optimize on")


# ── Root config ────────────────────────────────────────────────────────────────


class ResearchConfig(BaseModel):
    """Top-level research campaign configuration.

    Serialises to/from YAML for versionable, human-readable definitions.
    Extended for multi-agent pipeline with agent configs, gate configs, memory, and risk.
    Extended for MetaGuardian integration with guardian state.
    """

    # Core campaign fields
    campaign: str = Field(..., description="Campaign name / identifier")
    market: Market
    timeframe: Timeframe
    building_blocks: list[BuildingBlock] = Field(default_factory=list)
    strategies: list[Strategy] = Field(default_factory=list)
    criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    default_criteria: list[AcceptanceCriterion] = Field(
        default_factory=lambda: [
            AcceptanceCriterion(metric="profit_factor", operator=">", value=1.0),
            AcceptanceCriterion(metric="return_dd_ratio", operator=">", value=1.0),
            AcceptanceCriterion(metric="avg_trades_per_month", operator=">", value=0.5),
        ],
        description="Default acceptance criteria used when criteria list is empty",
    )

    # Multi-agent extensions
    hypotheses: list[HypothesisConfig] = Field(default_factory=list, description="Research hypotheses to test")
    iteration_config: IterationConfig = Field(default_factory=IterationConfig, description="Iteration control")
    gate_policies: list[GatePolicyConfig] = Field(default_factory=list, description="Per-gate policies")
    agents: list[AgentRefConfig] = Field(default_factory=list, description="Agent references with config overrides")
    memory: MemoryConfig = Field(default_factory=MemoryConfig, description="Agent memory configuration")
    risk: RiskConfig = Field(default_factory=RiskConfig, description="Portfolio risk limits")
    
    # LLM configuration (optional)
    llm_config: Optional[LLMConfig] = Field(
        default=None,
        description="Optional LLM configuration for AI-powered research agents",
    )

    # Cost configuration (broker-aware cost modelling)
    costs: Optional[CostsConfig] = Field(
        default=None,
        description="Optional cost configuration for broker-aware cost modelling",
    )

    # Analysis configuration
    analysis: AnalysisConfig = Field(
        default_factory=AnalysisConfig,
        description="Analysis stage thresholds and scoring weights",
    )

    # MetaGuardian integration
    guardian_state: Optional[dict] = Field(default=None, description="Current MetaGuardian state for DSL translation")

    # Retest / optimize blocks (REQ-19) — optional; absent means no block.
    retest: Optional[RetestBlock] = Field(
        default=None,
        description="Optional retest block for the bounded retest loop",
    )
    optimize: Optional[OptimizeBlock] = Field(
        default=None,
        description="Optional optimize block for the optimizer stage",
    )

    @model_validator(mode="after")
    def _validate_unique_strategy_names(self) -> ResearchConfig:
        """Ensure all strategy names are unique within a campaign."""
        names = [s.name for s in self.strategies]
        if len(names) != len(set(names)):
            seen: set[str] = set()
            dups = {n for n in names if n in seen or seen.add(n)}
            from quantlab.tools.exceptions import ValidationError

            raise ValidationError(
                f"Duplicate strategy names: {', '.join(sorted(dups))}"
            )
        return self

    @model_validator(mode="after")
    def _validate_building_block_references(self) -> ResearchConfig:
        """Ensure all building-block references in strategies exist."""
        block_names = {b.name for b in self.building_blocks}
        for strategy in self.strategies:
            for ref in strategy.building_blocks:
                if ref not in block_names:
                    from quantlab.tools.exceptions import ValidationError

                    raise ValidationError(
                        f"Strategy '{strategy.name}' references unknown building "
                        f"block '{ref}'. Available: {', '.join(sorted(block_names)) or '(none)'}"
                    )
        return self

    @model_validator(mode="after")
    def _validate_agent_names(self) -> ResearchConfig:
        """Validate agent names against known agents."""
        known_agents = {
            "research", "builder", "statistics", "review",
            "portfolio", "deploy", "monitor", "research_director",
            "analysis",
        }
        for agent in self.agents:
            if agent.name not in known_agents:
                from quantlab.tools.exceptions import ValidationError

                raise ValidationError(
                    f"Unknown agent '{agent.name}'. Known agents: {', '.join(sorted(known_agents))}"
                )
        return self

    @model_validator(mode="after")
    def _validate_gate_policies(self) -> ResearchConfig:
        """Validate gate policies reference known gates."""
        known_gates = {
            "HUMAN_REVIEW_OBJECTIVES",
            "HUMAN_APPROVE_ITERATION",
            "HUMAN_APPROVE_PORTFOLIO",
            "HUMAN_APPROVE_DEPLOY",
            "HUMAN_REVIEW_PERFORMANCE",
        }
        for policy in self.gate_policies:
            if policy.gate_id not in known_gates:
                from quantlab.tools.exceptions import ValidationError

                raise ValidationError(
                    f"Unknown gate_id '{policy.gate_id}' in gate_policies. "
                    f"Known gates: {', '.join(sorted(known_gates))}"
                )
        return self