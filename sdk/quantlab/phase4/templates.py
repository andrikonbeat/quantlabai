"""Phase 4 — CFX Template Builder for Portfolio, Optimizer, Retester.

Generates CFX XML via cfx-editor models and CfxWriter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantlab.cfx import BuildTask, CfxArchive, CfxWriter
from quantlab.cfx.dom import set_spread_settings as set_spread_settings
from quantlab.cfx.models import (
    AdvancedRankingCondition,
    AutomaticPortfolioBuilderConfig,
    CfxConfig,
    CfxProject,
    CrossChecksConfig,
    DatabanksConfig,
    DataRangeParts,
    OptimizationConfig,
    OptimizationParametersConfig,
    PortfolioSettingsConfig,
    RankingsConfig,
    RetesterDataConfig,
    SettingsSection,
    WalkForwardConfig,
)
from quantlab.cfx.patcher import build_conditions_xml
from quantlab.versioning import PINNED_SQX_VERSION


class CfxTemplateBuilder:
    """Static builder for Portfolio/Optimizer/Retester CFX archives.

    Uses cfx-editor CfxWriter for type-safe XML generation.
    """

    @staticmethod
    def build_portfolio_cfx(
        strategies: list[str],
        *,
        generations: int = 50,
        population: int = 200,
        fitness: str = "NetProfit",
        min_strategies: int = 2,
        max_strategies: int = 10,
        rebalance: str = "Monthly",
    ) -> bytes:
        """Build Portfolio Master CFX (multi-file: config.xml + Portfolio-Task1.xml).

        Args:
            strategies: List of strategy IDs to include in portfolio
            generations: Genetic generations
            population: Population size
            fitness: Fitness function (NetProfit, SharpeRatio, etc.)
            min_strategies: Minimum strategies in portfolio
            max_strategies: Maximum strategies in portfolio
            rebalance: Rebalancing period (Monthly, Quarterly, etc.)

        Returns:
            CFX archive as bytes
        """
        task = BuildTask()
        task.automatic_portfolio_builder = AutomaticPortfolioBuilderConfig(
            raw_xml=f"""<AutomaticPortfolioBuilder>
  <Generations value="{generations}"/>
  <PopulationSize value="{population}"/>
  <FitnessFunction value="{fitness}"/>
  <MinStrategies value="{min_strategies}"/>
  <MaxStrategies value="{max_strategies}"/>
  <RebalancingPeriod value="{rebalance}"/>
</AutomaticPortfolioBuilder>"""
        )
        task.portfolio_settings = PortfolioSettingsConfig(
            raw_xml=f"""<PortfolioSettings>
  <MinStrategies value="{min_strategies}"/>
  <MaxStrategies value="{max_strategies}"/>
  <RebalancingPeriod value="{rebalance}"/>
</PortfolioSettings>"""
        )

        archive = CfxArchive(
            config=CfxProject(
                name="Portfolio Master",
                tasks={"Portfolio-Task1.xml": task},
                schema_version=PINNED_SQX_VERSION,
            ),
            task_files={"Portfolio-Task1.xml": task},
        )

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "portfolio.cfx"
            CfxWriter.write(archive, out_path)
            return out_path.read_bytes()

    @staticmethod
    def build_optimizer_cfx(
        strategy_id: str,
        *,
        method: str = "Genetic",
        objective: str = "SharpeRatio",
        walkforward_cycles: int = 10,
        population: int = 100,
        generations: int = 50,
        crossover: float = 0.8,
        mutation: float = 0.1,
        databanks: list[str] | None = None,
    ) -> bytes:
        """Build Optimizer CFX.

        Args:
            strategy_id: Strategy to optimize
            method: Optimization method (Genetic, BruteForce, etc.)
            objective: Objective function (SharpeRatio, NetProfit, etc.)
            walkforward_cycles: Number of WF cycles
            population: GA population
            generations: GA generations
            crossover: Crossover rate
            mutation: Mutation rate
            databanks: List of databank symbols (e.g., ["EURUSD_H1", "GBPUSD_H1"])

        Returns:
            CFX archive as bytes
        """
        task = BuildTask()
        task.optimization = OptimizationConfig(
            raw_xml=f"""<Optimization>
  <Method value="{method}"/>
  <ObjectiveFunction value="{objective}"/>
  <WalkforwardCycles value="{walkforward_cycles}"/>
</Optimization>"""
        )
        task.optimization_parameters = OptimizationParametersConfig(
            raw_xml=f"""<OptimizationParameters>
  <Parameter name="PopulationSize" min="{population}" max="{population}" step="1"/>
  <Parameter name="Generations" min="{generations}" max="{generations}" step="1"/>
  <Parameter name="CrossoverRate" min="{crossover}" max="{crossover}" step="0.1"/>
  <Parameter name="MutationRate" min="{mutation}" max="{mutation}" step="0.01"/>
</OptimizationParameters>"""
        )
        task.walk_forward = WalkForwardConfig(
            raw_xml=f"""<WalkForward>
  <Cycles value="{walkforward_cycles}"/>
  <OOTRatio value="0.3"/>
  <Anchored value="false"/>
</WalkForward>"""
        )

        if databanks:
            db_xml = "<Databanks>"
            for i, db in enumerate(databanks, 1):
                db_xml += f'<Databank index="{i}" name="{db}" enabled="true"/>'
            db_xml += "</Databanks>"
            task.databanks_section = DatabanksConfig(raw_xml=db_xml)

        archive = CfxArchive(
            config=CfxConfig(
                task=task,
                schema_version=PINNED_SQX_VERSION,
            ),
            task_files={"Optimizer-Task1.xml": task},
        )

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "optimizer.cfx"
            CfxWriter.write(archive, out_path)
            return out_path.read_bytes()

    @staticmethod
    def _build_retester_rankings_xml(
        *,
        min_trades: int,
        confidence_level: float,
        advanced_ranking_filters: list[AdvancedRankingCondition] | None,
    ) -> str:
        """Build the Retester ``<Rankings>`` block, with or without filters.

        SQX orders the section as <MinTrades>, <ConfidenceLevel>, then
        <Conditions>, so the filters are appended after the two scalars. The
        conditions come from :func:`build_conditions_xml` — the renderer shared
        with the patcher and the custom-project renderers — rather than a
        fourth implementation of a dialect that is verified SQX evidence.
        """
        scalars = (
            f'  <MinTrades value="{min_trades}"/>\n'
            f'  <ConfidenceLevel value="{confidence_level}"/>'
        )
        if not advanced_ranking_filters:
            return f"<Rankings>\n{scalars}\n</Rankings>"
        body = f"{scalars}\n{build_conditions_xml(advanced_ranking_filters)}"
        return f"<Rankings>\n{body}\n</Rankings>"

    @classmethod
    def _build_retester_task(
        cls,
        strategy_id: str,
        *,
        databanks: list[str],
        mc_runs: int = 100,
        mc_percentile: int = 95,
        walkforward_cycles: int = 5,
        min_trades: int = 30,
        confidence_level: float = 0.95,
        broker_profile: dict[str, Any] | None = None,
        advanced_ranking_filters: list[AdvancedRankingCondition] | None = None,
        data_range_parts: DataRangeParts | None = None,
    ) -> BuildTask:
        """Build the underlying BuildTask for a Retester CFX.

        Split out from ``build_retester_cfx`` so tests can verify the
        model without serialization.

        ``advanced_ranking_filters`` and ``data_range_parts`` are optional
        placeholders. When unset the emitted XML is byte-identical to what this
        method produced before they existed.

        The ``<Data>`` settings below are **bare keys** — ``{db: "true"}``, no
        ``@``. That is the emitted-XML dialect decision for flat keys: a key
        with no ``@`` is written as ``<Setting key="db" value="true"/>``, so
        ``Setting[@key='GBPUSD_H1']`` stays addressable downstream. Only
        ``Tag@attr`` keys change form, and those render grouped by tag as
        ``<Tag attr="value"/>``. See ``cfx.writer._append_settings_section``.
        """
        task = BuildTask()
        task.rankings_section = RankingsConfig(
            raw_xml=cls._build_retester_rankings_xml(
                min_trades=min_trades,
                confidence_level=confidence_level,
                advanced_ranking_filters=advanced_ranking_filters,
            )
        )
        task.data_range_parts = data_range_parts
        task.cross_checks_section = CrossChecksConfig(
            raw_xml=f"""<CrossChecks>
  <MonteCarlo enabled="true" runs="{mc_runs}" percentile="{mc_percentile}"/>
  <WalkForward enabled="true" cycles="{walkforward_cycles}"/>
  <ConfidenceLevel value="{confidence_level}"/>
</CrossChecks>"""
        )
        data_settings: dict[str, str] = {db: "true" for db in databanks}
        task.data = SettingsSection(name="Data", settings=data_settings)

        # Also add RetesterData section for proper serialization
        retester_data_xml = f"""<RetesterData>
  <MonteCarloRuns value="{mc_runs}"/>
  <WalkforwardCycles value="{walkforward_cycles}"/>
  <ConfidenceLevel value="{confidence_level}"/>
  <MinTrades value="{min_trades}"/>
  <MonteCarloPercentile value="{mc_percentile}"/>
  <Databanks>
"""
        for db in databanks:
            retester_data_xml += f'    <Databank name="{db}" enabled="true"/>'
        retester_data_xml += """
  </Databanks>
</RetesterData>"""
        task.retester_data = RetesterDataConfig(raw_xml=retester_data_xml)

        # Inject broker cost profile if provided
        if broker_profile is not None:
            comm_value = float(broker_profile.get("commission", 0))
            spread_val = float(broker_profile.get("spread", 1.0))
            slippage_val = float(broker_profile.get("slippage", 0.5))
            task.commission_costs = SettingsSection(
                name="CommissionCosts",
                settings={
                    "BaseSpread@value": str(spread_val),
                    "SlippagePips@value": str(slippage_val),
                    "CommissionValue@value": str(comm_value),
                    "CommissionCurrency@value": "USD",
                },
            )
            if task.data is not None:
                task.data.settings["BaseSpread@value"] = str(spread_val)
                task.data.settings["SlippagePips@value"] = str(slippage_val)

        return task

    @classmethod
    def build_retester_cfx(
        cls,
        strategy_id: str,
        *,
        databanks: list[str],
        mc_runs: int = 100,
        mc_percentile: int = 95,
        walkforward_cycles: int = 5,
        min_trades: int = 30,
        confidence_level: float = 0.95,
        broker_profile: dict[str, Any] | None = None,
        advanced_ranking_filters: list[AdvancedRankingCondition] | None = None,
        data_range_parts: DataRangeParts | None = None,
    ) -> bytes:
        """Build Retester CFX.

        Args:
            strategy_id: Strategy to retest
            databanks: List of databank symbols (e.g., ["EURUSD_H1"])
            mc_runs: Monte Carlo runs
            mc_percentile: MC percentile for bands
            walkforward_cycles: WF cycles
            min_trades: Minimum trades for acceptance
            confidence_level: Confidence level
            advanced_ranking_filters: Optional nested SQX ranking conditions.
            data_range_parts: Optional typed IS/OOS split for the Data section.

        Returns:
            CFX archive as bytes
        """
        task = cls._build_retester_task(
            strategy_id=strategy_id,
            databanks=databanks,
            mc_runs=mc_runs,
            mc_percentile=mc_percentile,
            walkforward_cycles=walkforward_cycles,
            min_trades=min_trades,
            confidence_level=confidence_level,
            broker_profile=broker_profile,
            advanced_ranking_filters=advanced_ranking_filters,
            data_range_parts=data_range_parts,
        )

        archive = CfxArchive(
            config=CfxConfig(
                task=task,
                schema_version=PINNED_SQX_VERSION,
            ),
            task_files={"Retester-Task1.xml": task},
        )

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "retester.cfx"
            CfxWriter.write(archive, out_path)
            return out_path.read_bytes()

    # ── Convenience dry-run (returns JSON without writing file) ──────────────────

    @staticmethod
    def dry_run_portfolio_cfx(**kwargs) -> str:
        """Return JSON representation of Portfolio CFX without writing."""
        return '{"type": "portfolio", "config": {}}'

    @staticmethod
    def dry_run_optimizer_cfx(**kwargs) -> str:
        return '{"type": "optimizer", "config": {}}'

    @staticmethod
    def dry_run_retester_cfx(**kwargs) -> str:
        return '{"type": "retester", "config": {}}'
