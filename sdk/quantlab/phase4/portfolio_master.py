"""Phase 4 — Portfolio Master for genetic portfolio building via sqcli.

PortfolioMaster generates a Portfolio Master CFX with genetic builder config,
runs it via sqcli (CommandDispatcher), and extracts selected strategies.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from quantlab.phase4.templates import CfxTemplateBuilder
from quantlab.phase4.daemon import SQXDaemonManager
from quantlab.phase4.command_dispatcher import CommandDispatcher
from quantlab.phase4.errors import PortfolioError, PortfolioMasterError


# ── Result dataclasses ─────────────────────────────────────────────────────────


@dataclass
class SelectedStrategy:
    """Individual strategy selected by Portfolio Master genetic builder.

    Attributes:
        strategy_id: SQX strategy identifier.
        weight: Allocated weight in the portfolio.
        rank: Ranking by weight (1 = highest weight).
        fitness: Optional fitness score for this strategy.
    """

    strategy_id: str
    weight: float
    rank: int
    fitness: Optional[float] = None


@dataclass
class PortfolioMasterResult:
    """Complete Portfolio Master genetic builder result.

    Attributes:
        strategies: List of SelectedStrategy sorted by rank (descending weight).
        total_count: Total number of selected strategies.
        source_format: Format the result was parsed from ("csv" or "xml").
    """

    strategies: list[SelectedStrategy] = field(default_factory=list)
    total_count: int = 0
    source_format: str = ""


# ── CSV column name aliases (case-insensitive) ─────────────────────────────

_CSV_STRATEGY_ALIASES = {"strategyid", "strategy_id", "strategy id", "id"}
_CSV_WEIGHT_ALIASES = {"weight", "weights"}
_CSV_RANK_ALIASES = {"rank", "ranking", "ranks"}
_CSV_FITNESS_ALIASES = {"fitness", "fitnessvalue", "fitness_value", "fit"}


def _resolve_col(headers: list[str], aliases: set[str]) -> Optional[str]:
    """Find first header matching any of the aliases (case-insensitive, stripped)."""
    for h in headers:
        stripped = h.strip().lower()
        if stripped in aliases:
            return h
    return None


# ── PortfolioMaster ────────────────────────────────────────────────────────────


class PortfolioMaster:
    """Runs Portfolio Master genetic builder via sqcli.

    Workflow:
        1. Build CFX with AutomaticPortfolioBuilder config (generations, population, fitness)
        2. Run via sqcli: loadconfig → start → status → export
        3. Extract selected strategies from result CSV/XML
    """

    def __init__(
        self,
        sqx_install_path: str | Path,
        *,
        daemon_manager: Optional[SQXDaemonManager] = None,
        dispatcher: Optional[CommandDispatcher] = None,
    ):
        self.sqx_install_path = Path(sqx_install_path).resolve()
        self.daemon_manager = daemon_manager
        self.dispatcher = dispatcher or CommandDispatcher()
        self._daemon: Optional[SQXDaemonManager] = None

    async def __aenter__(self) -> "PortfolioMaster":
        if self.daemon_manager:
            self._daemon = self.daemon_manager
            await self._daemon.start()
        return self

    async def __aexit__(self, *args) -> None:
        if self._daemon:
            await self._daemon.stop()

    async def build_portfolio(
        self,
        strategies: list[str],
        *,
        generations: int = 50,
        population: int = 200,
        fitness: str = "NetProfit",
        min_strategies: int = 2,
        max_strategies: int = 10,
        rebalance: str = "Monthly",
        campaign_name: str = "PortfolioMaster",
        output_dir: Optional[Path] = None,
    ) -> PortfolioMasterResult:
        """Run Portfolio Master genetic builder and return selected strategies.

        Args:
            strategies: List of strategy IDs to include in portfolio.
            generations: Genetic generations.
            population: Population size.
            fitness: Fitness function (NetProfit, SharpeRatio, ReturnDDRatio, etc.)
            min_strategies: Minimum strategies in portfolio.
            max_strategies: Maximum strategies in portfolio.
            rebalance: Rebalancing period.
            campaign_name: Name for the campaign/project.
            output_dir: Directory for output CFX/results.

        Returns:
            PortfolioMasterResult with selected strategies from the genetic search.

        Raises:
            PortfolioMasterError: If build fails.
        """
        if not strategies:
            raise PortfolioMasterError("At least one strategy ID is required")

        # Build CFX
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(
            strategies=strategies,
            generations=generations,
            population=population,
            fitness=fitness,
            min_strategies=min_strategies,
            max_strategies=max_strategies,
            rebalance=rebalance,
        )

        # Save CFX
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            cfx_path = Path(tmp.name)

        try:
            # Run via sqcli (async HTTP API)
            # 1. Load config
            await self.dispatcher.load_config(cfx_path)
            # 2. Start project
            await self.dispatcher.start_project(campaign_name)
            # 3. Wait for completion (poll status)
            await self._wait_for_completion(campaign_name)
            # 4. Export results
            results = await self.dispatcher.export_results(campaign_name)
            # 5. Extract selected strategies
            return self._extract_selected_strategies(results)
        finally:
            cfx_path.unlink(missing_ok=True)

    async def _wait_for_completion(self, campaign_name: str, timeout: float = 3600.0) -> None:
        """Poll project status until complete or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            status = await self.dispatcher.get_status(campaign_name)
            if status.is_complete:
                return
            if status.is_failed:
                raise PortfolioMasterError(f"Campaign failed: {status.error_message}")
            await asyncio.sleep(5.0)
        raise PortfolioMasterError(f"Timeout waiting for {campaign_name}")

    # ── Public parsing methods ─────────────────────────────────────────────

    @staticmethod
    def parse_csv_results(csv_content: str) -> PortfolioMasterResult:
        """Parse Portfolio Master results from CSV format.

        Detects columns by common aliases: StrategyId, Weight, Rank, Fitness.
        Columns are matched case-insensitively.

        Args:
            csv_content: Raw CSV string.

        Returns:
            PortfolioMasterResult with parsed strategies.

        Raises:
            PortfolioMasterError: If CSV is empty, has no recognizable columns,
                or contains non-numeric values where numbers are expected.
        """
        content = csv_content.strip()
        if not content:
            raise PortfolioMasterError("Cannot parse empty CSV content")

        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise PortfolioMasterError("CSV has no headers")

        headers = reader.fieldnames
        strategy_col = _resolve_col(headers, _CSV_STRATEGY_ALIASES)
        weight_col = _resolve_col(headers, _CSV_WEIGHT_ALIASES)
        rank_col = _resolve_col(headers, _CSV_RANK_ALIASES)
        fitness_col = _resolve_col(headers, _CSV_FITNESS_ALIASES)

        if not strategy_col:
            raise PortfolioMasterError(
                f"No strategy ID column found in CSV headers: {headers}"
            )

        strategies: list[SelectedStrategy] = []
        for row_num, row in enumerate(reader, start=2):
            raw_sid = row.get(strategy_col)
            sid = raw_sid.strip() if raw_sid else ""
            if not sid:
                continue

            weight = 0.0
            if weight_col:
                raw_w = row.get(weight_col)
                raw_w = raw_w.strip() if raw_w else ""
                if raw_w:
                    try:
                        weight = float(raw_w)
                    except (ValueError, TypeError):
                        raise PortfolioMasterError(
                            f"Non-numeric weight '{raw_w}' at row {row_num}"
                        )

            rank = 0
            if rank_col:
                raw_r = row.get(rank_col)
                raw_r = raw_r.strip() if raw_r else ""
                if raw_r:
                    try:
                        rank = int(float(raw_r))
                    except (ValueError, TypeError):
                        raise PortfolioMasterError(
                            f"Non-numeric rank '{raw_r}' at row {row_num}"
                        )

            fitness: Optional[float] = None
            if fitness_col:
                raw_f = row.get(fitness_col)
                raw_f = raw_f.strip() if raw_f else ""
                if raw_f:
                    try:
                        fitness = float(raw_f)
                    except (ValueError, TypeError):
                        raise PortfolioMasterError(
                            f"Non-numeric fitness '{raw_f}' at row {row_num}"
                        )

            strategies.append(SelectedStrategy(
                strategy_id=sid,
                weight=weight,
                rank=rank,
                fitness=fitness,
            ))

        if not strategies:
            raise PortfolioMasterError("CSV contained no strategy rows")

        # Sort by rank (ascending, with 0 = last), then by weight descending
        strategies.sort(key=lambda s: (s.rank if s.rank > 0 else 9999, -s.weight))

        return PortfolioMasterResult(
            strategies=strategies,
            total_count=len(strategies),
            source_format="csv",
        )

    @staticmethod
    def parse_xml_results(xml_content: str) -> PortfolioMasterResult:
        """Parse Portfolio Master results from XML format.

        Handles the SQX result XML with <SelectedStrategy> elements:
        .. code-block:: xml

            <PortfolioMasterResults>
              <SelectedStrategy id="strat_123" weight="0.3" rank="1" fitness="1.5"/>
            </PortfolioMasterResults>

        Args:
            xml_content: Raw XML string.

        Returns:
            PortfolioMasterResult with parsed strategies.

        Raises:
            PortfolioMasterError: If XML is empty, malformed, or contains no
                <SelectedStrategy> elements with an id attribute.
        """
        from xml.etree import ElementTree

        content = xml_content.strip()
        if not content:
            raise PortfolioMasterError("Cannot parse empty XML content")

        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as e:
            raise PortfolioMasterError(f"Malformed XML: {e}")

        strategies: list[SelectedStrategy] = []
        for strat in root.findall(".//SelectedStrategy"):
            sid = strat.get("id", "").strip()
            if not sid:
                continue

            weight = 0.0
            raw_weight = strat.get("weight", "").strip()
            if raw_weight:
                try:
                    weight = float(raw_weight)
                except (ValueError, TypeError):
                    raise PortfolioMasterError(
                        f"Non-numeric weight '{raw_weight}' for strategy '{sid}'"
                    )

            rank = 0
            raw_rank = strat.get("rank", "").strip()
            if raw_rank:
                try:
                    rank = int(float(raw_rank))
                except (ValueError, TypeError):
                    raise PortfolioMasterError(
                        f"Non-numeric rank '{raw_rank}' for strategy '{sid}'"
                    )

            fitness: Optional[float] = None
            raw_fitness = strat.get("fitness", "").strip()
            if raw_fitness:
                try:
                    fitness = float(raw_fitness)
                except (ValueError, TypeError):
                    raise PortfolioMasterError(
                        f"Non-numeric fitness '{raw_fitness}' for strategy '{sid}'"
                    )

            strategies.append(SelectedStrategy(
                strategy_id=sid,
                weight=weight,
                rank=rank,
                fitness=fitness,
            ))

        if not strategies:
            raise PortfolioMasterError(
                "No <SelectedStrategy> elements with an id found in XML"
            )

        # Sort by rank (ascending, with 0 = last), then by weight descending
        strategies.sort(key=lambda s: (s.rank if s.rank > 0 else 9999, -s.weight))

        return PortfolioMasterResult(
            strategies=strategies,
            total_count=len(strategies),
            source_format="xml",
        )

    @staticmethod
    def _extract_selected_strategies(results: str) -> PortfolioMasterResult:
        """Parse results to extract selected strategies.

        Tries XML or CSV based on content heuristics.
        Content starting with '<' is tried as XML first; otherwise CSV first.
        Falls back to the other format if the first attempt fails.

        Args:
            results: Raw result string (CSV or XML).

        Returns:
            PortfolioMasterResult with parsed strategies.

        Raises:
            PortfolioMasterError: If neither CSV nor XML parsing succeeds.
        """
        stripped = results.strip()
        if not stripped:
            raise PortfolioMasterError("Empty results — nothing to parse")

        is_xml_like = stripped.startswith("<")

        # ── Try primary format ──────────────────────────────────────────
        if is_xml_like:
            try:
                return PortfolioMaster.parse_xml_results(stripped)
            except PortfolioMasterError:
                pass  # fall through to CSV
        else:
            try:
                return PortfolioMaster.parse_csv_results(stripped)
            except PortfolioMasterError:
                pass  # fall through to XML

        # ── Try fallback format ─────────────────────────────────────────
        last_error: Optional[Exception] = None
        if is_xml_like:
            try:
                return PortfolioMaster.parse_csv_results(stripped)
            except PortfolioMasterError as e:
                last_error = e
        else:
            try:
                return PortfolioMaster.parse_xml_results(stripped)
            except PortfolioMasterError as e:
                last_error = e

        raise PortfolioMasterError(
            "Could not parse results — not valid CSV or XML"
        ) from last_error

    def dry_run_cfx(
        self,
        strategies: list[str],
        generations: int = 50,
        population: int = 200,
        fitness: str = "NetProfit",
    ) -> str:
        """Generate Portfolio Master CFX and return as base64 JSON (dry-run)."""
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(
            strategies=strategies,
            generations=generations,
            population=population,
            fitness=fitness,
        )
        # Return JSON representation
        return base64.b64encode(cfx_bytes).decode()