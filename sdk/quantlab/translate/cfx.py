"""CFX archive factory — creates .cfx files from ResearchConfig using cfx-editor models.

Replaces the old XML-string-based approach with model-driven archive generation
using CfxArchive, CfxPatcher, and CfxWriter from quantlab.cfx.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from pydantic import BaseModel, Field

from quantlab.cfx import CfxArchive as CfxArchiveModel, CfxWriter, BuildTask
from quantlab.dsl.models import ResearchConfig
from quantlab.translate.translator import (
    generate_cfx_archive,
    generate_portfolio_cfx_archive,
    generate_optimizer_cfx_archive,
    generate_retester_cfx_archive,
)


#: Default output subdirectory used by both normal and dry-run modes.
DEFAULT_OUTPUT_DIR = "_output"


class CfxResult(BaseModel):
    """Structured result from a CFX archive operation.

    Attributes:
        xml_content: The generated XML string (config.xml content in normal mode,
                     model JSON in dry-run mode).
        path: Filesystem path to the written artifact (ZIP or raw JSON).
    """

    xml_content: str | None = None
    path: Path | None = None


def _sanitize_filename(campaign: str) -> str:
    """Replace non-alphanumeric characters with underscores."""
    sanitized = re.sub(r"[^\w\-.]", "_", campaign)
    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Strip leading/trailing underscores
    return sanitized.strip("_")


def _dry_run_output_dir(output_dir: str | Path) -> Path:
    """Derive the dry-run output directory from a normal output dir.

    If *output_dir* is a custom path (not the default), dry-run files are
    written to a sibling ``_output/`` directory so they do not pollute the
    real output location.  When the default output dir is used, dry-run
    writes to the default ``_output/``.
    """
    out = Path(output_dir)
    if out.resolve() == Path(DEFAULT_OUTPUT_DIR).resolve():
        # Using the default — stay in _output/
        return out
    # Custom output_dir — write to a sibling _output/
    return out.parent / DEFAULT_OUTPUT_DIR


class CfxArchiveFactory:
    """Factory for creating CFX archive files from ``ResearchConfig`` models.

    Usage::

        result = CfxArchiveFactory.from_model(config, dry_run=True)
        print(result.xml_content)

        # Phase 4 generators
        portfolio = CfxArchiveFactory.from_portfolio(strategies=["strat-1", "strat-2"])
        optimizer = CfxArchiveFactory.from_optimizer(strategy_id="strat-1")
        retester = CfxArchiveFactory.from_retester(strategy_id="strat-1", databanks=["EURUSD_H1"])
    """

    @staticmethod
    def from_model(
        config: ResearchConfig,
        output_dir: str | None = None,
        dry_run: bool = False,
    ) -> CfxResult:
        """Translate a ``ResearchConfig`` and write the result to disk.

        Args:
            config: A validated ``ResearchConfig`` instance.
            output_dir: Directory for the output file(s).
                        Defaults to ``_output/`` in the current working directory.
            dry_run: When True, writes model JSON to ``_output/`` instead of
                     creating a ZIP archive.

        Returns:
            A ``CfxResult`` containing the content and the output path.
        """
        # Resolve output directory
        out_dir = Path(output_dir) if output_dir is not None else Path(DEFAULT_OUTPUT_DIR)

        # Generate CFX archive using new cfx-editor models
        archive: CfxArchiveModel = generate_cfx_archive(config)

        # Build a safe filename from the campaign name
        safe_name = _sanitize_filename(config.campaign) or "campaign"

        if dry_run:
            # Write model JSON to _output/ (or sibling _output/)
            dst_dir = _dry_run_output_dir(out_dir)
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_path = dst_dir / f"{safe_name}.cfx.json"

            # Get JSON content via dry_run (model serialization)
            json_str = CfxWriter.dry_run(archive)
            dst_path.write_text(json_str, encoding="utf-8")
            return CfxResult(xml_content=json_str, path=dst_path)

        # Normal mode: create a ZIP archive with .cfx extension
        dst_dir = out_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = (dst_dir / safe_name).with_suffix(".cfx")

        CfxWriter.write(archive, dst_path)

        # Read config.xml from the written archive for inspection
        with zipfile.ZipFile(dst_path, "r") as zf:
            config_xml = zf.read("config.xml").decode("utf-8")

        return CfxResult(xml_content=config_xml, path=dst_path)

    # ── Phase 4 — Portfolio / Optimizer / Retester ─────────────────────

    @staticmethod
    def from_portfolio(
        strategies: list[str],
        *,
        generations: int = 50,
        population: int = 200,
        fitness: str = "NetProfit",
        min_strategies: int = 2,
        max_strategies: int = 10,
        rebalance: str = "Monthly",
        output_dir: str | None = None,
        dry_run: bool = False,
    ) -> CfxResult:
        """Generate and write a Portfolio Master CFX archive.

        Args:
            strategies: List of strategy IDs to include in the portfolio.
            generations: Genetic algorithm generations.
            population: Population size.
            fitness: Fitness function (e.g. NetProfit, SharpeRatio).
            min_strategies: Minimum strategies in the portfolio.
            max_strategies: Maximum strategies in the portfolio.
            rebalance: Rebalancing period (Monthly, Quarterly, etc.).
            output_dir: Directory for the output file(s). Defaults to ``_output/``.
            dry_run: When True, writes model JSON instead of a ZIP archive.

        Returns:
            A ``CfxResult`` with content and output path.
        """
        out_dir = Path(output_dir) if output_dir is not None else Path(DEFAULT_OUTPUT_DIR)

        archive = generate_portfolio_cfx_archive(
            strategies,
            generations=generations,
            population=population,
            fitness=fitness,
            min_strategies=min_strategies,
            max_strategies=max_strategies,
            rebalance=rebalance,
        )

        safe_name = f"portfolio-{_sanitize_filename(strategies[0]) if strategies else 'master'}"

        if dry_run:
            dst_dir = _dry_run_output_dir(out_dir)
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_path = dst_dir / f"{safe_name}.cfx.json"
            json_str = CfxWriter.dry_run(archive)
            dst_path.write_text(json_str, encoding="utf-8")
            return CfxResult(xml_content=json_str, path=dst_path)

        dst_dir = out_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = (dst_dir / safe_name).with_suffix(".cfx")
        CfxWriter.write(archive, dst_path)

        with zipfile.ZipFile(dst_path, "r") as zf:
            config_xml = zf.read("config.xml").decode("utf-8")
        return CfxResult(xml_content=config_xml, path=dst_path)

    @staticmethod
    def from_optimizer(
        strategy_id: str,
        *,
        method: str = "Genetic",
        objective: str = "SharpeRatio",
        walkforward_cycles: int = 10,
        walkforward_oot_ratio: float = 0.3,
        population: int = 100,
        generations: int = 50,
        crossover: float = 0.8,
        mutation: float = 0.1,
        databanks: list[str] | None = None,
        output_dir: str | None = None,
        dry_run: bool = False,
    ) -> CfxResult:
        """Generate and write an Optimizer CFX archive.

        Args:
            strategy_id: Strategy identifier to optimize.
            method: Optimization method (Genetic, BruteForce, Grid).
            objective: Objective function (SharpeRatio, NetProfit, etc.).
            walkforward_cycles: Number of walk-forward cycles.
            walkforward_oot_ratio: Out-of-sample ratio.
            population: GA population size.
            generations: GA generations.
            crossover: Crossover rate.
            mutation: Mutation rate.
            databanks: Optional list of databank symbols.
            output_dir: Directory for the output file(s). Defaults to ``_output/``.
            dry_run: When True, writes model JSON instead of a ZIP archive.

        Returns:
            A ``CfxResult`` with content and output path.
        """
        out_dir = Path(output_dir) if output_dir is not None else Path(DEFAULT_OUTPUT_DIR)

        archive = generate_optimizer_cfx_archive(
            strategy_id,
            method=method,
            objective=objective,
            walkforward_cycles=walkforward_cycles,
            walkforward_oot_ratio=walkforward_oot_ratio,
            population=population,
            generations=generations,
            crossover=crossover,
            mutation=mutation,
            databanks=databanks,
        )

        safe_name = f"optimizer-{_sanitize_filename(strategy_id)}"

        if dry_run:
            dst_dir = _dry_run_output_dir(out_dir)
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_path = dst_dir / f"{safe_name}.cfx.json"
            json_str = CfxWriter.dry_run(archive)
            dst_path.write_text(json_str, encoding="utf-8")
            return CfxResult(xml_content=json_str, path=dst_path)

        dst_dir = out_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = (dst_dir / safe_name).with_suffix(".cfx")
        CfxWriter.write(archive, dst_path)

        with zipfile.ZipFile(dst_path, "r") as zf:
            config_xml = zf.read("config.xml").decode("utf-8")
        return CfxResult(xml_content=config_xml, path=dst_path)

    @staticmethod
    def from_retester(
        strategy_id: str,
        *,
        databanks: list[str],
        mc_runs: int = 100,
        mc_percentile: int = 95,
        walkforward_cycles: int = 5,
        min_trades: int = 30,
        confidence_level: float = 0.95,
        output_dir: str | None = None,
        dry_run: bool = False,
    ) -> CfxResult:
        """Generate and write a Retester CFX archive.

        Args:
            strategy_id: Strategy identifier to retest.
            databanks: List of databank symbols (e.g. ["EURUSD_H1"]).
            mc_runs: Monte Carlo simulation runs.
            mc_percentile: MC percentile for confidence bands.
            walkforward_cycles: Number of walk-forward cycles.
            min_trades: Minimum trades for acceptance.
            confidence_level: Confidence level (0.5 < level < 0.99).
            output_dir: Directory for the output file(s). Defaults to ``_output/``.
            dry_run: When True, writes model JSON instead of a ZIP archive.

        Returns:
            A ``CfxResult`` with content and output path.
        """
        out_dir = Path(output_dir) if output_dir is not None else Path(DEFAULT_OUTPUT_DIR)

        archive = generate_retester_cfx_archive(
            strategy_id,
            databanks=databanks,
            mc_runs=mc_runs,
            mc_percentile=mc_percentile,
            walkforward_cycles=walkforward_cycles,
            min_trades=min_trades,
            confidence_level=confidence_level,
        )

        safe_name = f"retester-{_sanitize_filename(strategy_id)}"

        if dry_run:
            dst_dir = _dry_run_output_dir(out_dir)
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_path = dst_dir / f"{safe_name}.cfx.json"
            json_str = CfxWriter.dry_run(archive)
            dst_path.write_text(json_str, encoding="utf-8")
            return CfxResult(xml_content=json_str, path=dst_path)

        dst_dir = out_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = (dst_dir / safe_name).with_suffix(".cfx")
        CfxWriter.write(archive, dst_path)

        with zipfile.ZipFile(dst_path, "r") as zf:
            config_xml = zf.read("config.xml").decode("utf-8")
        return CfxResult(xml_content=config_xml, path=dst_path)


def _get_primary_task(archive: CfxArchiveModel) -> BuildTask:
    """Get the primary BuildTask from an archive."""
    config = archive.config
    if hasattr(config, "task"):
        return config.task
    elif hasattr(config, "tasks") and config.tasks:
        return next(iter(config.tasks.values()))
    from quantlab.cfx.models import BuildTask

    return BuildTask()


# Backward compatibility alias
CfxArchive = CfxArchiveFactory