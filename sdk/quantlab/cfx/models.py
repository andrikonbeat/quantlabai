"""Pydantic v2 models for .cfx archive contents.

Mirrors the CFX XML schema 1:1 via element.attrib → field mapping.
All models use Pydantic v2 BaseModel with strict mode disabled to
accommodate string-typed attribute values from XML parsing.
"""

from __future__ import annotations

from typing import Union

from pydantic import BaseModel, Field


# ── Section Types ────────────────────────────────────────────────────


class SettingsSection(BaseModel):
    """Simple key-value section (Options, Data, Rankings, etc.)."""

    name: str
    settings: dict[str, str]


class RawXmlSection(BaseModel):
    """Byte-for-byte passthrough for unrecognized sections."""

    name: str
    raw_xml: str


# ── Complex Section Models ───────────────────────────────────────────


class BlockConfig(BaseModel):
    """Typed model for the <Blocks> section."""

    raw_xml: str = ""


class AtmConfig(BaseModel):
    """Typed model for the <ATMs> section."""

    raw_xml: str = ""


class DataBankConfig(BaseModel):
    """Typed model for the <DataBanks> section."""

    raw_xml: str = ""


class ResourceConfig(BaseModel):
    """Typed model for the <Resources> section."""

    raw_xml: str = ""


# ── Phase 4 Complex Section Models ───────────────────────────────────


class AutomaticPortfolioBuilderConfig(BaseModel):
    """Typed model for <AutomaticPortfolioBuilder> section (Portfolio Master)."""

    raw_xml: str = ""


class PortfolioSettingsConfig(BaseModel):
    """Typed model for <PortfolioSettings> section."""

    raw_xml: str = ""


class OptimizationConfig(BaseModel):
    """Typed model for <Optimization> section (Optimizer)."""

    raw_xml: str = ""


class OptimizationParametersConfig(BaseModel):
    """Typed model for <OptimizationParameters> section."""

    raw_xml: str = ""


class WalkForwardConfig(BaseModel):
    """Typed model for <WalkForward> section."""

    raw_xml: str = ""


class DatabanksConfig(BaseModel):
    """Typed model for <Databanks> section (Optimizer/Retester)."""

    raw_xml: str = ""


class RankingsConfig(BaseModel):
    """Typed model for <Rankings> section (Retester)."""

    raw_xml: str = ""


class CrossChecksConfig(BaseModel):
    """Typed model for <CrossChecks> section (Retester)."""

    raw_xml: str = ""


class RetesterDataConfig(BaseModel):
    """Typed model for <RetesterData> section."""

    raw_xml: str = ""


# ── BuildTask ────────────────────────────────────────────────────────


class BuildTask(BaseModel):
    """A single build task extracted from a CFX archive."""

    # Standard sections
    options: SettingsSection | None = None
    what_to_build: SettingsSection | None = None
    risk_money_mgmt: SettingsSection | None = None
    data: SettingsSection | None = None
    rankings: SettingsSection | None = None
    parts_to_improve: SettingsSection | None = None
    cross_checks: SettingsSection | None = None
    notes: SettingsSection | None = None

    # Complex sections
    blocks: BlockConfig | None = None
    atms: AtmConfig | None = None
    databanks: DataBankConfig | None = None
    resources: ResourceConfig | None = None

    # Commission / spread metadata (for post-backtest processing)
    commission_costs: SettingsSection | None = None

    # Phase 4 sections
    automatic_portfolio_builder: AutomaticPortfolioBuilderConfig | None = None
    portfolio_settings: PortfolioSettingsConfig | None = None
    optimization: OptimizationConfig | None = None
    optimization_parameters: OptimizationParametersConfig | None = None
    walk_forward: WalkForwardConfig | None = None
    databanks_section: DatabanksConfig | None = None
    rankings_section: RankingsConfig | None = None
    cross_checks_section: CrossChecksConfig | None = None
    retester_data: RetesterDataConfig | None = None

    unknown_sections: list[RawXmlSection] = Field(default_factory=list)


# ── Archive Models ───────────────────────────────────────────────────


class CfxConfig(BaseModel):
    """Single-file config: <Task> root, one BuildTask."""

    task: BuildTask
    schema_version: str

    @property
    def task_type(self) -> str:
        return "config"


class CfxProject(BaseModel):
    """Multi-file project: <Project> root, task routing."""

    name: str
    tasks: dict[str, BuildTask]
    schema_version: str

    @property
    def task_type(self) -> str:
        return "project"


class CfxArchive(BaseModel):
    """Top-level CFX archive holding config/project + task file lookup."""

    config: CfxConfig | CfxProject
    task_files: dict[str, BuildTask] = Field(default_factory=dict)


# ── PatchInstruction Types ───────────────────────────────────────────


class SetMarketInstruction(BaseModel):
    """Set the market symbol on the first data setup."""

    symbol: str
    instruction_type: str = "set_market"


class AddTimeframeInstruction(BaseModel):
    """Add a new timeframe/chart to the data section."""

    timeframe: str
    instruction_type: str = "add_timeframe"


class EnableBlockInstruction(BaseModel):
    """Enable a building block with an optional weight override."""

    block_key: str
    weight: int = 100
    instruction_type: str = "enable_block"


class DisableBlockInstruction(BaseModel):
    """Disable a building block by key."""

    block_key: str
    instruction_type: str = "disable_block"


class SetGeneticInstruction(BaseModel):
    """Configure genetic optimisation parameters."""

    enabled: bool
    generations: int
    population: int
    instruction_type: str = "set_genetic"


class SetDateRangeInstruction(BaseModel):
    """Set the date range for backtesting data."""

    start: str
    end: str
    instruction_type: str = "set_date_range"


class AddRankingConditionInstruction(BaseModel):
    """Add a ranking condition with metric, operator, and threshold."""

    metric: str
    operator: str
    value: float
    instruction_type: str = "add_ranking_condition"


class EnableCrosscheckInstruction(BaseModel):
    """Enable walk-forward and Monte-Carlo cross-checks."""

    wf_enabled: bool
    mc_enabled: bool
    wf_cycles: int = 50
    instruction_type: str = "enable_crosscheck"


# ── Phase 4 PatchInstruction Types ───────────────────────────────────


class SetAutomaticPortfolioBuilderInstruction(BaseModel):
    """Configure Automatic Portfolio Builder settings."""

    generations: int
    population: int
    fitness: str
    min_strategies: int = 1
    max_strategies: int | None = None
    rebalancing: str = "Monthly"
    instruction_type: str = "set_automatic_portfolio_builder"


class SetPortfolioSettingsInstruction(BaseModel):
    """Configure Portfolio Settings (weights, constraints)."""

    weight_constraints: dict[str, str] | None = None  # strategy_id -> constraint
    instruction_type: str = "set_portfolio_settings"


class SetOptimizationInstruction(BaseModel):
    """Configure Optimizer main settings."""

    method: str = "Genetic"
    objective_function: str = "NetProfit"
    walkforward_cycles: int = 5
    walkforward_oot_ratio: float = 0.3
    instruction_type: str = "set_optimization"


class SetOptimizationParametersInstruction(BaseModel):
    """Configure optimization parameter ranges."""

    parameters: dict[str, dict[str, float]]  # param_name -> {min, max, step}
    instruction_type: str = "set_optimization_parameters"


class SetWalkForwardInstruction(BaseModel):
    """Configure walk-forward settings."""

    cycles: int
    oot_ratio: float
    anchored: bool = False
    instruction_type: str = "set_walkforward"


class SetDatabanksInstruction(BaseModel):
    """Configure databanks for optimizer/retester."""

    databanks: list[str]
    instruction_type: str = "set_databanks"


class SetRankingsInstruction(BaseModel):
    """Configure retester rankings settings."""

    metrics: list[str]
    min_trades: int = 30
    instruction_type: str = "set_rankings"


class SetCrossChecksInstruction(BaseModel):
    """Configure retester cross-checks (Monte Carlo, Walk-Forward)."""

    mc_enabled: bool
    mc_runs: int = 100
    mc_percentile: int = 95
    wf_enabled: bool
    wf_cycles: int = 5
    confidence_level: float = 0.95
    instruction_type: str = "set_crosschecks"


class SetRetesterDataInstruction(BaseModel):
    """Configure retester data settings."""

    databanks: list[str]
    monte_carlo_runs: int = 100
    walkforward_cycles: int = 5
    confidence_level: float = 0.95
    min_trades: int = 30
    mc_percentile: int = 95
    instruction_type: str = "set_retester_data"


PatchInstruction = Union[
    # Original 8
    SetMarketInstruction,
    AddTimeframeInstruction,
    EnableBlockInstruction,
    DisableBlockInstruction,
    SetGeneticInstruction,
    SetDateRangeInstruction,
    AddRankingConditionInstruction,
    EnableCrosscheckInstruction,
    # Phase 4 (8 new)
    SetAutomaticPortfolioBuilderInstruction,
    SetPortfolioSettingsInstruction,
    SetOptimizationInstruction,
    SetOptimizationParametersInstruction,
    SetWalkForwardInstruction,
    SetDatabanksInstruction,
    SetRankingsInstruction,
    SetCrossChecksInstruction,
    SetRetesterDataInstruction,
]
"""Union of all 16 typed instruction models for CfxPatcher."""
