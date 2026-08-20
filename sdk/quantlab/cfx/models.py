"""Pydantic v2 models for .cfx archive contents.

Mirrors the CFX XML schema 1:1 via element.attrib → field mapping.
All models use Pydantic v2 BaseModel with strict mode disabled to
accommodate string-typed attribute values from XML parsing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Union

from pydantic import BaseModel, Field

from quantlab.customproject.models import DatabankSpec


def _str_to_bool(value: str, default: bool = False) -> bool:
    """Convert a string value to bool."""
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes")


def _xml_text(el: ET.Element | None, default: str = "") -> str:
    """Safely extract text from an XML element."""
    if el is None or el.text is None:
        return default
    return el.text.strip()


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


# ── CrossChecks Typed Models ───────────────────────────────────────────


class CrossChecksGeneric(BaseModel):
    """Typed model for Generic CrossChecks dialect."""

    mc_enabled: bool = False
    mc_runs: int = 100
    mc_percentile: int = 95
    wf_enabled: bool = False
    wf_cycles: int = 5
    confidence_level: float = 0.95
    parameters: str | None = None


class RetestWithHigherPrecision(BaseModel):
    """Typed model for <RetestWithHigherPrecision> element."""

    use: bool = False
    precision: int | None = None
    spread: int | None = None


class MonteCarloRetest(BaseModel):
    """Typed model for <MonteCarloRetest> element."""

    use: bool = False
    number_of_simulations: int = 100


class MonteCarloManipulation(BaseModel):
    """Typed model for <MonteCarloManipulation> element."""

    use: bool = False


class RetestOnAdditionalMarkets(BaseModel):
    """Typed model for <RetestOnAdditionalMarkets> element."""

    use: bool = False


class WalkForwardOptimization(BaseModel):
    """Typed model for <WalkForwardOptimization> element."""

    use: bool = False
    walk_forward_type: str = ""
    period: str = ""
    optimization: str = ""
    optimize_periods: bool = False


class WalkForwardMatrix(BaseModel):
    """Typed model for <WalkForwardMatrix> element."""

    raw_xml: str = ""


class OptProfileSysParamPermutation(BaseModel):
    """Typed model for <OptProfileSysParamPermutation> element."""

    raw_xml: str = ""


class CrossChecksAutomaticRetest(BaseModel):
    """Typed model for AutomaticRetest CrossChecks dialect."""

    use: bool = True
    retest_with_higher_precision: RetestWithHigherPrecision | None = None
    monte_carlo_retest: MonteCarloRetest | None = None
    monte_carlo_manipulation: MonteCarloManipulation | None = None
    retest_on_additional_markets: RetestOnAdditionalMarkets | None = None
    walk_forward_optimization: WalkForwardOptimization | None = None
    walk_forward_matrix: WalkForwardMatrix | None = None
    opt_profile_sys_param_permutation: OptProfileSysParamPermutation | None = None


class CrossChecksConfig(BaseModel):
    """Typed model for <CrossChecks> section (Retester) with dual-dialect support."""

    raw_xml: str = ""
    dialect: str | None = None
    generic: CrossChecksGeneric | None = None
    automatic_retest: CrossChecksAutomaticRetest | None = None

    @classmethod
    def from_xml(cls, xml: str) -> CrossChecksConfig:
        """Parse CrossChecks XML into typed model with dialect detection.

        Args:
            xml: Raw CrossChecks XML string.

        Returns:
            CrossChecksConfig with typed fields populated and extras in raw_xml.
        """
        raw_xml_fallback = xml
        dialect: str | None = None
        generic: CrossChecksGeneric | None = None
        automatic_retest: CrossChecksAutomaticRetest | None = None
        extras: list[str] = []

        try:
            root = ET.fromstring(xml)
            child_tags = [child.tag for child in root]

            generic_tags = {"MonteCarlo", "WalkForward", "ConfidenceLevel"}
            auto_tags = {
                "RetestWithHigherPrecision",
                "MonteCarloRetest",
                "WalkForwardOptimization",
            }

            if any(t in generic_tags for t in child_tags):
                dialect = "generic"
                generic = cls._parse_generic(root)
                for child in root:
                    if child.tag not in generic_tags:
                        extras.append(ET.tostring(child, encoding="unicode"))
            elif any(t in auto_tags for t in child_tags):
                dialect = "automatic_retest"
                automatic_retest = cls._parse_automatic_retest(root)
                for child in root:
                    if child.tag not in auto_tags:
                        extras.append(ET.tostring(child, encoding="unicode"))
        except ET.ParseError:
            pass

        raw_xml = "\n".join(extras) if extras else ""
        if not dialect:
            raw_xml = raw_xml_fallback

        return cls(
            raw_xml=raw_xml,
            dialect=dialect,
            generic=generic,
            automatic_retest=automatic_retest,
        )

    def to_xml(self) -> str:
        """Serialize typed CrossChecks back to XML string.

        Returns:
            XML string with typed fields serialized and raw_xml extras appended.
        """
        if self.dialect == "generic" and self.generic:
            g = self.generic
            parts = [
                "<CrossChecks>",
                f'  <MonteCarlo enabled="{str(g.mc_enabled).lower()}" simulations="{g.mc_runs}" percentile="{g.mc_percentile}"/>',
            ]
            if g.parameters:
                parts.append(f"  {g.parameters.strip()}")
            parts.append(f'  <WalkForward enabled="{str(g.wf_enabled).lower()}" cycles="{g.wf_cycles}"/>')
            parts.append(f'  <ConfidenceLevel value="{g.confidence_level}"/>')
            if self.raw_xml:
                parts.append(f"  {self.raw_xml.strip()}")
            parts.append("</CrossChecks>")
            return "\n".join(parts)

        if self.dialect == "automatic_retest" and self.automatic_retest:
            ar = self.automatic_retest
            parts = [f'<CrossChecks use="{str(ar.use).lower()}">']

            if ar.retest_with_higher_precision is not None:
                rwp = ar.retest_with_higher_precision
                settings_parts = []
                if rwp.precision is not None:
                    settings_parts.append(f"<Precision>{rwp.precision}</Precision>")
                if rwp.spread is not None:
                    settings_parts.append(f"<Spread>{rwp.spread}</Spread>")
                settings_inner = "".join(settings_parts)
                parts.append(
                    f"  <RetestWithHigherPrecision use=\"{str(rwp.use).lower()}\">"
                    f"<Settings>{settings_inner}</Settings>"
                    f"<AcceptanceSettings><Conditions /></AcceptanceSettings>"
                    f"</RetestWithHigherPrecision>"
                )

            if ar.monte_carlo_retest is not None:
                mc = ar.monte_carlo_retest
                parts.append(
                    f"  <MonteCarloRetest use=\"{str(mc.use).lower()}\">"
                    f"<Settings><NumberOfSimulations value=\"{mc.number_of_simulations}\"/></Settings>"
                    f"<AcceptanceSettings><Conditions /></AcceptanceSettings>"
                    f"</MonteCarloRetest>"
                )

            if ar.monte_carlo_manipulation is not None:
                mc = ar.monte_carlo_manipulation
                parts.append(
                    f"  <MonteCarloManipulation use=\"{str(mc.use).lower()}\">"
                    f"<Settings><NumberOfSimulations value=\"100\"/></Settings>"
                    f"<AcceptanceSettings><Conditions /></AcceptanceSettings>"
                    f"</MonteCarloManipulation>"
                )

            if ar.retest_on_additional_markets is not None:
                rp = ar.retest_on_additional_markets
                parts.append(
                    f"  <RetestOnAdditionalMarkets use=\"{str(rp.use).lower()}\">"
                    f"<Settings><Setups /></Settings>"
                    f"<AcceptanceSettings><Conditions /></AcceptanceSettings>"
                    f"</RetestOnAdditionalMarkets>"
                )

            if ar.walk_forward_optimization is not None:
                wfo = ar.walk_forward_optimization
                parts.append(
                    f"  <WalkForwardOptimization use=\"{str(wfo.use).lower()}\">"
                    f"<Settings>"
                    f"<WalkForward type=\"{wfo.walk_forward_type}\" period=\"{wfo.period}\" optimization=\"{wfo.optimization}\">"
                    f"<Param1 value=\"\" /><Param2 value=\"\" />"
                    f"</WalkForward>"
                    f"<OptimizePeriods>{str(wfo.optimize_periods).lower()}</OptimizePeriods>"
                    f"</Settings>"
                    f"<AcceptanceSettings><Conditions CrossCheck=\"WalkForwardOptimization\" thresholdPct=\"50\" /></AcceptanceSettings>"
                    f"</WalkForwardOptimization>"
                )

            if ar.walk_forward_matrix is not None and ar.walk_forward_matrix.raw_xml:
                parts.append(f"  {ar.walk_forward_matrix.raw_xml.strip()}")

            if ar.opt_profile_sys_param_permutation is not None and ar.opt_profile_sys_param_permutation.raw_xml:
                parts.append(f"  {ar.opt_profile_sys_param_permutation.raw_xml.strip()}")

            if self.raw_xml:
                parts.append(f"  {self.raw_xml.strip()}")
            parts.append("</CrossChecks>")
            return "\n".join(parts)

        if self.raw_xml:
            return self.raw_xml
        return "<CrossChecks/>"

    def summary(self) -> dict:
        """Return a readable summary of configured parameters.

        Returns:
            Dictionary with dialect and typed field values.
        """
        result: dict = {"dialect": self.dialect}
        if self.generic is not None:
            result["generic"] = self.generic.model_dump()
        if self.automatic_retest is not None:
            ar = self.automatic_retest.model_dump()
            # Remove None values for cleaner summary
            result["automatic_retest"] = {k: v for k, v in ar.items() if v is not None}
        return result

    @staticmethod
    def _parse_generic(root: ET.Element) -> CrossChecksGeneric:
        """Parse Generic dialect child elements into CrossChecksGeneric."""
        mc_enabled = False
        mc_runs = 100
        mc_percentile = 95
        wf_enabled = False
        wf_cycles = 5
        confidence_level = 0.95
        parameters = None

        for child in root:
            if child.tag == "MonteCarlo":
                mc_enabled = _str_to_bool(child.get("enabled"), False)
                mc_runs = int(child.get("runs", "100"))
                mc_percentile = int(child.get("percentile", "95"))
            elif child.tag == "WalkForward":
                wf_enabled = _str_to_bool(child.get("enabled"), False)
                wf_cycles = int(child.get("cycles", "5"))
            elif child.tag == "ConfidenceLevel":
                confidence_level = float(child.get("value", "0.95"))
            elif child.tag == "Parameters":
                parameters = ET.tostring(child, encoding="unicode").strip()

        return CrossChecksGeneric(
            mc_enabled=mc_enabled,
            mc_runs=mc_runs,
            mc_percentile=mc_percentile,
            wf_enabled=wf_enabled,
            wf_cycles=wf_cycles,
            confidence_level=confidence_level,
            parameters=parameters,
        )

    @staticmethod
    def _parse_automatic_retest(root: ET.Element) -> CrossChecksAutomaticRetest:
        """Parse AutomaticRetest dialect child elements into CrossChecksAutomaticRetest."""
        use = _str_to_bool(root.get("use"), True)

        retest_with_higher_precision = None
        monte_carlo_retest = None
        monte_carlo_manipulation = None
        retest_on_additional_markets = None
        walk_forward_optimization = None
        walk_forward_matrix = None
        opt_profile_sys_param_permutation = None

        for child in root:
            if child.tag == "RetestWithHigherPrecision":
                rwp_use = _str_to_bool(child.get("use"), False)
                precision = None
                spread = None
                settings = child.find("Settings")
                if settings is not None:
                    prec = settings.find("Precision")
                    if prec is not None and prec.text:
                        precision = int(prec.text.strip())
                    spread_el = settings.find("Spread")
                    if spread_el is not None and spread_el.text:
                        spread = int(spread_el.text.strip())
                retest_with_higher_precision = RetestWithHigherPrecision(
                    use=rwp_use, precision=precision, spread=spread
                )
            elif child.tag == "MonteCarloRetest":
                mc_use = _str_to_bool(child.get("use"), False)
                num_sim = 100
                settings = child.find("Settings")
                if settings is not None:
                    nos = settings.find("NumberOfSimulations")
                    if nos is not None and nos.text:
                        num_sim = int(nos.text.strip())
                monte_carlo_retest = MonteCarloRetest(
                    use=mc_use, number_of_simulations=num_sim
                )
            elif child.tag == "MonteCarloManipulation":
                mc_use = _str_to_bool(child.get("use"), False)
                monte_carlo_manipulation = MonteCarloManipulation(use=mc_use)
            elif child.tag == "RetestOnAdditionalMarkets":
                rwp_use = _str_to_bool(child.get("use"), False)
                retest_on_additional_markets = RetestOnAdditionalMarkets(use=rwp_use)
            elif child.tag == "WalkForwardOptimization":
                wfo_use = _str_to_bool(child.get("use"), False)
                wf_type = ""
                period = ""
                optimization = ""
                optimize_periods = False
                settings = child.find("Settings")
                if settings is not None:
                    wf = settings.find("WalkForward")
                    if wf is not None:
                        wf_type = wf.get("type", "")
                        period = wf.get("period", "")
                        optimization = wf.get("optimization", "")
                    op = settings.find("OptimizePeriods")
                    if op is not None and op.text:
                        optimize_periods = op.text.strip().lower() == "true"
                walk_forward_optimization = WalkForwardOptimization(
                    use=wfo_use,
                    walk_forward_type=wf_type,
                    period=period,
                    optimization=optimization,
                    optimize_periods=optimize_periods,
                )
            elif child.tag == "WalkForwardMatrix":
                wfm_use = _str_to_bool(child.get("use"), False)
                raw_xml = ET.tostring(child, encoding="unicode").strip()
                walk_forward_matrix = WalkForwardMatrix(use=wfm_use, raw_xml=raw_xml)
            elif child.tag == "OptProfileSysParamPermutation":
                opsp_use = _str_to_bool(child.get("use"), False)
                raw_xml = ET.tostring(child, encoding="unicode").strip()
                opt_profile_sys_param_permutation = OptProfileSysParamPermutation(
                    use=opsp_use, raw_xml=raw_xml
                )

        return CrossChecksAutomaticRetest(
            use=use,
            retest_with_higher_precision=retest_with_higher_precision,
            monte_carlo_retest=monte_carlo_retest,
            monte_carlo_manipulation=monte_carlo_manipulation,
            retest_on_additional_markets=retest_on_additional_markets,
            walk_forward_optimization=walk_forward_optimization,
            walk_forward_matrix=walk_forward_matrix,
            opt_profile_sys_param_permutation=opt_profile_sys_param_permutation,
        )


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


class TaskMeta(BaseModel):
    """Per-task routing metadata emitted on the ``<Task>`` element.

    Lives alongside ``CfxProject.tasks`` (the ordered task XML seed) so the
    writer can emit the real per-task ``type``, ``name`` and ``active``
    attributes (REQ-23). Absent entries fall back to legacy behaviour
    (type ``Build``, name derived from the XML file name, active ``true``).
    """

    task_type: str = "Build"
    name: str = ""
    active: bool = True
    show_settings_overview: bool = False
    sample_name: str = "Custom"


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
    databanks: list[DatabankSpec] = Field(default_factory=list)
    task_meta: dict[str, TaskMeta] = Field(default_factory=dict)
    metadata: dict | None = None

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
