"""Phase 4 — CFX Template Builder for Portfolio, Optimizer, Retester.

Builds complete CFX archives using cfx-editor models.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Optional

from quantlab.cfx import CfxArchive, CfxWriter
from quantlab.cfx.models import (
    CfxConfig,
    CfxProject,
    BuildTask,
    SettingsSection,
    AutomaticPortfolioBuilder,
    PortfolioSettings,
    Optimization,
    OptimizationParameters,
    WalkForward,
    Databanks,
    Rankings,
    CrossChecks,
    RetesterData,
)
from quantlab.dsl import ResearchConfig, Market, Timeframe, Strategy


class CfxTemplateBuilder:
    """Static factory for Portfolio/Optimizer/Retester CFX archives."""

    @staticmethod
    def build_portfolio_cfx(
        strategies: list[str],
        generations: int = 50,
        population: int = 100,
        fitness: str = "NetProfit",
        min_strategies: int = 2,
        max_strategies: int = 10,
        rebalance: str = "Monthly",
    ) -> bytes:
        """Build Portfolio Master CFX with genetic portfolio builder config."""
        archive = CfxArchive()

        # Create Config (single <Task> root)
        config = CfxConfig(schema_version="144.2953")

        # Build task with AutomaticPortfolioBuilder
        task = BuildTask()
        task.automatic_portfolio_builder = AutomaticPortfolioBuilder(
            generations=generations,
            population_size=population,
            fitness_function=fitness,
        )
        task.portfolio_settings = PortfolioSettings(
            min_strategies=min_strategies,
            max_strategies=max_strategies,
            rebalancing_period=rebalance,
        )

        # Add strategies as entries (simplified - real impl would load each)
        # For now, just set the config
        config.task = task
        archive.config = config

        # Write to bytes
        buffer = io.BytesIO()
        CfxWriter.write(archive, buffer)
        return buffer.getvalue()

    @staticmethod
    def build_optimizer_cfx(
        strategy_id: str,
        method: str = "Genetic",
        objective: str = "SharpeRatio",
        walkforward_cycles: int = 10,
        population: int = 100,
        generations: int = 50,
        crossover: float = 0.8,
        mutation: float = 0.1,
        databanks: Optional[list[str]] = None,
    ) -> bytes:
        """Build Optimizer CFX with walk-forward + genetic params."""
        archive = CfxArchive()
        config = CfxConfig(schema_version="144.2953")

        task = BuildTask()
        task.optimization = Optimization(
            method=method,
            objective_function=objective,
            walkforward_cycles=walkforward_cycles,
        )
        task.optimization_parameters = OptimizationParameters(
            population=population,
            generations=generations,
            crossover_rate=crossover,
            mutation_rate=mutation,
        )
        task.walkforward = WalkForward(
            cycles=walkforward_cycles,
            out_of_sample_ratio=0.3,
        )
        task.databanks = Databanks(symbols=databanks or [])

        config.task = task
        archive.config = config

        buffer = io.BytesIO()
        CfxWriter.write(archive, buffer)
        return buffer.getvalue()

    @staticmethod
    def build_retester_cfx(
        strategy_id: str,
        databanks: list[str],
        monte_carlo_runs: int = 100,
        walkforward_cycles: int = 5,
        mc_percentile: int = 95,
        min_trades: int = 30,
        confidence_level: float = 0.95,
    ) -> bytes:
        """Build Retester CFX with MC/WF cross-checks."""
        archive = CfxArchive()
        config = CfxConfig(schema_version="144.2953")

        task = BuildTask()
        task.rankings = Rankings(
            min_trades=min_trades,
            confidence_level=confidence_level,
        )
        task.crosschecks = CrossChecks(
            monte_carlo_enabled=True,
            mc_runs=monte_carlo_runs,
            mc_percentile=mc_percentile,
            walkforward_enabled=True,
            wf_cycles=walkforward_cycles,
        )
        task.retester_data = RetesterData(
            databanks=databanks,
        )

        config.task = task
        archive.config = config

        buffer = io.BytesIO()
        CfxWriter.write(archive, buffer)
        return buffer.getvalue()

    @staticmethod
    def build_portfolio_composer_cfx(
        strategies: list[str],
        fitness: str = "ReturnDDRatio",
    ) -> bytes:
        """Build Portfolio Composer CFX for weight optimization."""
        archive = CfxArchive()
        config = CfxConfig(schema_version="144.2953")

        task = BuildTask()
        task.portfolio_settings = PortfolioSettings(
            min_strategies=len(strategies),
            max_strategies=len(strategies),
            rebalancing_period="Monthly",
        )
        task.automatic_portfolio_builder = AutomaticPortfolioBuilder(
            generations=0,  # 0 = use composer mode (no genetic)
            population_size=0,
            fitness_function=fitness,
        )

        config.task = task
        archive.config = config

        buffer = io.BytesIO()
        CfxWriter.write(archive, buffer)
        return buffer.getvalue()

    @staticmethod
    def cfx_bytes_to_file(cfx_bytes: bytes, output_path: Path) -> Path:
        """Save CFX bytes to file."""
        output_path.write_bytes(cfx_bytes)
        return output_path

    @staticmethod
    def cfx_bytes_to_temp(cfx_bytes: bytes, prefix: str = "phase4_") -> Path:
        """Save CFX bytes to temp file."""
        import tempfile
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=".cfx")
        os.close(fd)
        Path(path).write_bytes(cfx_bytes)
        return Path(path)