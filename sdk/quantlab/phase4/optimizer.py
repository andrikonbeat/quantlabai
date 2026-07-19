"""Phase 4 — Optimizer for walk-forward optimization via sqcli."""

from __future__ import annotations

import asyncio
import base64
import csv
import statistics
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from quantlab.phase4.templates import CfxTemplateBuilder
from quantlab.phase4.command_dispatcher import CommandDispatcher
from quantlab.phase4.errors import OptimizerError, OptimizerRunError


# ── Known SQX metric column names (lowercased, no spaces/dashes/underscores) ──

_KNOWN_METRICS: frozenset[str] = frozenset({
    "sharpe",
    "sharperatio",
    "profitfactor",
    "drawdown",
    "maxdrawdown",
    "netprofit",
    "grossprofit",
    "grossloss",
    "totaltrades",
    "winrate",
    "recoveryfactor",
    "return",
    "totalreturn",
    "avgtrade",
    "stddev",
    "kelly",
    "kellyvalue",
    "rsquared",
    "rsquare",
    "correlation",
    "mae",
    "mfe",
    "duration",
    "exposure",
    "largestloss",
    "largestwin",
    "avgbars",
    "numbars",
    "expectancy",
    "nperiods",
    "numperiods",
    "kratio",
    "tradesperyear",
    "marketexposure",
    "exposuretime",
})


def _normalize_header(name: str) -> str:
    """Lowercase and strip separators for metric matching."""
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


def _is_loss_metric(safe_name: str) -> bool:
    """Heuristic: metrics related to drawdown or loss."""
    return any(kw in safe_name for kw in ("drawdown", "loss", "dd"))


# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class WalkForwardCycle:
    """A single walk-forward optimization cycle.

    Attributes:
        cycle: Cycle number.
        in_sample_start: In-sample period start date (YYYY-MM-DD).
        in_sample_end: In-sample period end date.
        out_sample_start: Out-of-sample period start date.
        out_sample_end: Out-of-sample period end date.
        parameters: Optimized parameter values (name → value).
        metrics: Performance metrics (name → value).
    """

    cycle: int
    in_sample_start: str
    in_sample_end: str
    out_sample_start: str
    out_sample_end: str
    parameters: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class OptimizationResult:
    """Parsed result from an SQX optimizer CSV export.

    Attributes:
        strategy_id: The strategy that was optimized.
        cycles: Walk-forward cycles, one per data row in the CSV.
        summary: Aggregated metrics (num_cycles, avg_*, best_*, worst_*).
        csv_path: Path to the original CSV file (if parsed from one).
        raw_path: Backward-compatible property returning csv_path.
    """

    strategy_id: str
    cycles: list[WalkForwardCycle] = field(default_factory=list)
    summary: dict[str, float] = field(default_factory=dict)
    csv_path: Optional[Path] = None

    @property
    def raw_path(self) -> Optional[Path]:
        """Return the raw CSV path for backward compatibility with ``run()``."""
        return self.csv_path


# ── Config ────────────────────────────────────────────────────────────────────


class OptimizerConfig:
    """Configuration for walk-forward optimization."""

    def __init__(
        self,
        strategy_id: str,
        *,
        method: str = "Genetic",
        objective: str = "SharpeRatio",
        walkforward_cycles: int = 10,
        population: int = 100,
        generations: int = 50,
        crossover: float = 0.8,
        mutation: float = 0.1,
        databanks: Optional[list[str]] = None,
    ):
        self.strategy_id = strategy_id
        self.method = method
        self.objective = objective
        self.walkforward_cycles = walkforward_cycles
        self.population = population
        self.generations = generations
        self.crossover = crossover
        self.mutation = mutation
        self.databanks = databanks or []


# ── Optimizer ─────────────────────────────────────────────────────────────────


class Optimizer:
    """Runs walk-forward optimization via sqcli.

    Workflow:
        1. Build Optimizer CFX with parameters, walk-forward, databanks
        2. Run via sqcli: loadconfig → start → poll status → export
        3. Parse exported CSV into ``OptimizationResult``
        4. Optionally generate HTML report via ``to_html()``
    """

    def __init__(
        self,
        sqx_install_path: str | Path,
        dispatcher: Optional[CommandDispatcher] = None,
    ):
        self.sqx_install_path = Path(sqx_install_path).resolve()
        self.dispatcher = dispatcher or CommandDispatcher()

    async def run(
        self,
        config: OptimizerConfig,
        campaign_name: str = "Optimizer",
        output_dir: Optional[Path] = None,
        timeout: float = 7200.0,
    ) -> OptimizationResult:
        """Run optimization and return parsed results.

        Args:
            config: OptimizerConfig with all parameters.
            campaign_name: Name for the campaign/project.
            output_dir: Directory for output CSV (default: current directory).
            timeout: Maximum time to wait for completion.

        Returns:
            OptimizationResult with parsed cycles and summary.
            Use ``.raw_path`` to get the original CSV path.

        Raises:
            OptimizerRunError: If optimization fails or CSV is unparseable.
        """
        # Build CFX
        cfx_bytes = CfxTemplateBuilder.build_optimizer_cfx(
            strategy_id=config.strategy_id,
            method=config.method,
            objective=config.objective,
            walkforward_cycles=config.walkforward_cycles,
            population=config.population,
            generations=config.generations,
            crossover=config.crossover,
            mutation=config.mutation,
            databanks=config.databanks,
        )

        # Save CFX to temp file
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            cfx_path = Path(tmp.name)

        try:
            # Load config
            await self.dispatcher.load_config(cfx_path)

            # Start campaign
            await self.dispatcher.start_project(campaign_name)

            # Wait for completion
            await self._wait_for_completion(campaign_name, timeout)

            # Export results
            csv_path = Path(
                await self.dispatcher.export_optimization_results(
                    campaign_name, output_dir or Path.cwd()
                )
            )

            # Parse and return
            return self.parse_csv(csv_path, config.strategy_id)

        finally:
            cfx_path.unlink(missing_ok=True)

    async def _wait_for_completion(self, campaign_name: str, timeout: float) -> None:
        """Poll sqcli status until complete."""
        start = time.time()
        while time.time() - start < timeout:
            status = await self.dispatcher.get_status(campaign_name)
            if status.is_complete:
                return
            await asyncio.sleep(10.0)
        raise OptimizerRunError(f"Timeout after {timeout}s")

    # ── CSV Parsing ───────────────────────────────────────────────────────────

    def parse_csv(
        self,
        csv_path: Path,
        strategy_id: str = "",
    ) -> OptimizationResult:
        """Parse an SQX optimizer CSV export into an OptimizationResult.

        Detects fixed columns (Cycle, InSampleStart, InSampleEnd,
        OutSampleStart, OutSampleEnd), identifies metric columns by known
        names, and treats everything else as parameter columns.  Column
        order is flexible; missing or unparseable values are skipped.

        Args:
            csv_path: Path to the SQX CSV export.
            strategy_id: Optional identifier to store on the result.

        Returns:
            OptimizationResult with parsed cycles and summary.

        Raises:
            OptimizerRunError: If the file is missing, empty, or malformed.
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise OptimizerRunError(f"CSV file not found: {csv_path}")

        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)

            # Skip empty/whitespace-only lines to find the header
            header_row: list[str] | None = None
            raw_header: list[str] | None = None
            data_rows: list[list[str]] = []

            for row in reader:
                cleaned = [c.strip() for c in row]
                if not any(cleaned):
                    continue
                if header_row is None:
                    header_row = [c.lower() for c in cleaned]
                    raw_header = list(cleaned)  # keep original case
                else:
                    data_rows.append(cleaned)

        if header_row is None:
            raise OptimizerRunError("CSV file is empty or has no header row")
        if not data_rows:
            raise OptimizerRunError("CSV has a header but no data rows")

        # ── Identify fixed columns ────────────────────────────────────────
        fixed_map: dict[str, int | None] = {
            "cycle": None,
            "insamplestart": None,
            "insampleend": None,
            "outsamplestart": None,
            "outsampleend": None,
        }

        for i, h in enumerate(header_row):
            n = _normalize_header(h)
            if n in fixed_map:
                fixed_map[n] = i

        missing = [k for k, v in fixed_map.items() if v is None]
        if missing:
            raise OptimizerRunError(
                f"Missing required columns in CSV header: {', '.join(missing)}"
            )

        fixed_indices: set[int] = {v for v in fixed_map.values() if v is not None}

        # ── Classify remaining columns ────────────────────────────────────
        param_cols: dict[int, str] = {}
        metric_cols: dict[int, str] = {}

        assert raw_header is not None and header_row is not None

        for i, h in enumerate(raw_header):
            if i in fixed_indices:
                continue
            if _normalize_header(h) in _KNOWN_METRICS:
                metric_cols[i] = h
            else:
                param_cols[i] = h

        # ── Parse cycles ──────────────────────────────────────────────────
        cycles: list[WalkForwardCycle] = []

        for row in data_rows:
            try:
                cycle_num = int(row[fixed_map["cycle"]])  # type: ignore[arg-type]
            except (ValueError, IndexError) as exc:
                raise OptimizerRunError(
                    f"Invalid or missing cycle number: {exc}"
                ) from exc

            try:
                cycle = WalkForwardCycle(
                    cycle=cycle_num,
                    in_sample_start=row[fixed_map["insamplestart"]],   # type: ignore[arg-type]
                    in_sample_end=row[fixed_map["insampleend"]],       # type: ignore[arg-type]
                    out_sample_start=row[fixed_map["outsamplestart"]],  # type: ignore[arg-type]
                    out_sample_end=row[fixed_map["outsampleend"]],      # type: ignore[arg-type]
                )
            except IndexError as exc:
                raise OptimizerRunError(
                    f"Missing date columns for cycle {cycle_num}"
                ) from exc

            # Parameters
            for col_idx, col_name in param_cols.items():
                try:
                    raw = row[col_idx].strip()
                    if raw:
                        cycle.parameters[col_name] = float(raw)
                except (ValueError, IndexError):
                    pass  # skip unparseable or missing

            # Metrics
            for col_idx, col_name in metric_cols.items():
                try:
                    raw = row[col_idx].strip()
                    if raw:
                        cycle.metrics[col_name] = float(raw)
                except (ValueError, IndexError):
                    pass  # skip unparseable or missing

            cycles.append(cycle)

        # ── Summary statistics ─────────────────────────────────────────────
        summary: dict[str, float] = {"num_cycles": float(len(cycles))}

        metric_values: dict[str, list[float]] = {}
        for c in cycles:
            for name, val in c.metrics.items():
                metric_values.setdefault(name, []).append(val)

        for name, values in metric_values.items():
            safe = name.lower().replace(" ", "_").replace("-", "_")
            if len(values) >= 1:
                summary[f"avg_{safe}"] = _round_sig(statistics.mean(values))
            if len(values) >= 2:
                if _is_loss_metric(safe):
                    summary[f"best_{safe}"] = _round_sig(min(values))
                    summary[f"worst_{safe}"] = _round_sig(max(values))
                else:
                    summary[f"best_{safe}"] = _round_sig(max(values))
                    summary[f"worst_{safe}"] = _round_sig(min(values))

        return OptimizationResult(
            strategy_id=strategy_id,
            cycles=cycles,
            summary=summary,
            csv_path=csv_path,
        )

    # ── HTML Export ────────────────────────────────────────────────────────────

    def to_html(
        self,
        result: OptimizationResult,
        output_path: Path,
    ) -> Path:
        """Generate a self-contained HTML report from an OptimizationResult.

        The HTML is valid, responsive, and has no external dependencies
        (all CSS is inline).  Includes a cycle detail table and a summary
        statistics section.

        Args:
            result: Parsed optimization result.
            output_path: Where to write the HTML file.

        Returns:
            The *output_path* (for chaining).
        """
        # ── Build parameter & metric column lists ─────────────────────────
        all_params: list[str] = []
        all_metrics: list[str] = []
        seen_params: set[str] = set()
        seen_metrics: set[str] = set()

        for c in result.cycles:
            for k in c.parameters:
                if k not in seen_params:
                    all_params.append(k)
                    seen_params.add(k)
            for k in c.metrics:
                if k not in seen_metrics:
                    all_metrics.append(k)
                    seen_metrics.add(k)

        # ── HTML parts ────────────────────────────────────────────────────
        parts: list[str] = [
            "<!DOCTYPE html>\n",
            '<html lang="en">\n',
            "<head>\n",
            '<meta charset="utf-8">\n',
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n',
            "<title>Optimization Report — ",
            _html_esc(result.strategy_id or "Untitled"),
            "</title>\n",
            "<style>\n",
            _CSS,
            "</style>\n",
            "</head>\n",
            "<body>\n",
            '<div class="container">\n',
        ]

        # ── Header ────────────────────────────────────────────────────────
        parts.append(f"<h1>Optimization Report</h1>\n")
        if result.strategy_id:
            parts.append(
                f'<p class="subtitle">Strategy: <strong>'
                f"{_html_esc(result.strategy_id)}</strong></p>\n"
            )
        if result.csv_path:
            parts.append(
                f'<p class="subtitle">Source: <code>'
                f"{_html_esc(str(result.csv_path))}</code></p>\n"
            )
        parts.append(
            f'<p class="subtitle">Cycles: <strong>{len(result.cycles)}</strong></p>\n'
        )

        # ── Summary ───────────────────────────────────────────────────────
        if result.summary:
            parts.append("<h2>Summary Statistics</h2>\n")
            parts.append('<div class="summary-grid">\n')
            # Show num_cycles first, then alphabetical
            summary_items = sorted(
                (k, v) for k, v in result.summary.items() if k != "num_cycles"
            )
            parts.append(
                _summary_card("num_cycles", str(len(result.cycles)), "Cycles")
            )
            for key, val in result.summary.items():
                if key == "num_cycles":
                    continue
                label = key.replace("_", " ").title()
                if isinstance(val, float):
                    display = _fmt_metric(val)
                else:
                    display = str(val)
                parts.append(_summary_card(key, display, label))
            parts.append("</div>\n")

        # ── Cycle Table ───────────────────────────────────────────────────
        if result.cycles:
            parts.append("<h2>Cycle Details</h2>\n")
            parts.append('<div class="table-wrap">\n')
            parts.append("<table>\n")
            parts.append("<thead>\n<tr>\n")
            parts.append("<th>Cycle</th>\n")
            parts.append("<th>In-Sample Start</th>\n")
            parts.append("<th>In-Sample End</th>\n")
            parts.append("<th>Out-of-Sample Start</th>\n")
            parts.append("<th>Out-of-Sample End</th>\n")
            for p in all_params:
                parts.append(f"<th>{_html_esc(p)}</th>\n")
            for m in all_metrics:
                parts.append(f"<th>{_html_esc(m)}</th>\n")
            parts.append("</tr>\n</thead>\n")
            parts.append("<tbody>\n")

            for c in result.cycles:
                parts.append("<tr>\n")
                parts.append(f"<td>{c.cycle}</td>\n")
                parts.append(f"<td>{_html_esc(c.in_sample_start)}</td>\n")
                parts.append(f"<td>{_html_esc(c.in_sample_end)}</td>\n")
                parts.append(f"<td>{_html_esc(c.out_sample_start)}</td>\n")
                parts.append(f"<td>{_html_esc(c.out_sample_end)}</td>\n")
                for p in all_params:
                    val = c.parameters.get(p)
                    parts.append(
                        f"<td class='num'>{_fmt_metric(val) if val is not None else '—'}</td>\n"
                    )
                for m in all_metrics:
                    val = c.metrics.get(m)
                    parts.append(
                        f"<td class='num'>{_fmt_metric(val) if val is not None else '—'}</td>\n"
                    )
                parts.append("</tr>\n")

            parts.append("</tbody>\n")
            parts.append("</table>\n")
            parts.append("</div>\n")
        else:
            parts.append('<p class="empty">No optimization data available.</p>\n')

        # ── Footer ────────────────────────────────────────────────────────
        parts.append(
            '<p class="footer">Generated by QuantLab AI — Phase 4 Optimizer</p>\n'
        )
        parts.append("</div>\n")
        parts.append("</body>\n")
        parts.append("</html>\n")

        output_path = Path(output_path)
        output_path.write_text("".join(parts), encoding="utf-8")
        return output_path

    # ── Dry-run helper ────────────────────────────────────────────────────────

    def dry_run(self, config: OptimizerConfig) -> str:
        """Generate CFX as base64 JSON for dry-run testing."""
        cfx_bytes = CfxTemplateBuilder.build_optimizer_cfx(
            strategy_id=config.strategy_id,
            method=config.method,
            objective=config.objective,
            walkforward_cycles=config.walkforward_cycles,
            population=config.population,
            generations=config.generations,
            crossover=config.crossover,
            mutation=config.mutation,
            databanks=config.databanks,
        )
        return base64.b64encode(cfx_bytes).decode()


# ── HTML Helpers ────────────────────────────────────────────────────────────────


_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               Helvetica, Arial, sans-serif;
  background: #f5f7fa;
  color: #1a1a2e;
  padding: 2rem 1rem;
  line-height: 1.6;
}
.container { max-width: 1200px; margin: 0 auto; }
h1 { font-size: 1.75rem; margin-bottom: 0.25rem; }
h2 {
  font-size: 1.25rem;
  margin: 1.5rem 0 0.75rem;
  padding-bottom: 0.25rem;
  border-bottom: 2px solid #e2e8f0;
}
.subtitle { color: #475569; margin-bottom: 0.25rem; font-size: 0.95rem; }
.subtitle code { background: #e2e8f0; padding: 0.1rem 0.4rem; border-radius: 3px; }
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.summary-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  text-align: center;
}
.summary-card .val {
  font-size: 1.4rem;
  font-weight: 700;
  color: #2563eb;
}
.summary-card .lbl {
  font-size: 0.8rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.table-wrap { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}
th, td {
  padding: 0.5rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
  white-space: nowrap;
  font-size: 0.875rem;
}
th {
  background: #f8fafc;
  font-weight: 600;
  color: #475569;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
td.num { text-align: right; font-variant-numeric: tabular-nums; }
tr:hover { background: #f1f5f9; }
.empty { color: #94a3b8; font-style: italic; padding: 2rem 0; text-align: center; }
.footer {
  margin-top: 2rem;
  font-size: 0.8rem;
  color: #94a3b8;
  text-align: center;
}
"""


def _html_esc(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt_metric(val: float) -> str:
    """Format a numeric metric for HTML display."""
    if abs(val) >= 10_000:
        return f"{val:,.2f}"
    if abs(val) >= 100:
        return f"{val:.2f}"
    if abs(val) >= 1:
        return f"{val:.4f}"
    return f"{val:.6f}"


def _round_sig(val: float) -> float:
    """Round to 6 significant-ish decimal places."""
    return round(val, 6)


def _summary_card(key: str, display: str, label: str) -> str:
    """Build a summary statistics card HTML."""
    return (
        f'<div class="summary-card">\n'
        f'<div class="val">{_html_esc(display)}</div>\n'
        f'<div class="lbl">{_html_esc(label)}</div>\n'
        f"</div>\n"
    )
