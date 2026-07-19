"""Phase 4 — Retester for Monte Carlo / Walk-Forward robustness testing via sqcli."""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from quantlab.phase4.templates import CfxTemplateBuilder
from quantlab.phase4.command_dispatcher import CommandDispatcher
from quantlab.phase4.errors import (
    RetesterError,
    RetesterRunError,
    RetesterDatabankError,
    DatabankPathError,
)


# Databank name validation pattern (e.g., EURUSD_H1, GBPUSD_M15)
DATABANK_PATTERN = re.compile(r"^[A-Z]{6}_[A-Z]\d+$")


# ── Result dataclasses ────────────────────────────────────────────────────────


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation results for a retest campaign."""

    runs: int
    percentile: int
    percentile_net_profit: float
    percentile_sharpe: float
    percentile_drawdown: float
    confidence_interval: tuple[float, float]


@dataclass
class WalkForwardResult:
    """Walk-Forward analysis results for a retest campaign."""

    cycles: int
    avg_sharpe_ratio: float
    avg_profit_factor: float
    avg_drawdown: float
    stability: float


@dataclass
class RetestResult:
    """Complete retest campaign result.

    Carries the parsed Monte Carlo and Walk-Forward results plus paths
    to the exported HTML and CSV reports.
    """

    strategy_id: str
    monte_carlo: MonteCarloResult
    walk_forward: WalkForwardResult
    html_path: Optional[Path] = None
    csv_path: Optional[Path] = None

    @property
    def html_report(self) -> Optional[Path]:
        """Return the HTML report path (backward-compatible alias)."""
        return self.html_path


class RetesterConfig:
    """Configuration for retesting a strategy with Monte Carlo / Walk-Forward."""

    def __init__(
        self,
        strategy_id: str,
        *,
        databanks: list[str],
        monte_carlo_runs: int = 100,
        mc_percentile: int = 95,
        walkforward_cycles: int = 5,
        min_trades: int = 30,
        confidence_level: float = 0.95,
    ):
        self.strategy_id = strategy_id

        # Validate databank names
        for db in databanks:
            if not DATABANK_PATTERN.match(db):
                raise RetesterDatabankError(
                    f"Invalid databank name: '{db}'. Must match ^[A-Z]{{6}}_[A-Z]\\d+$"
                )
        self.databanks = databanks

        if not (1 <= monte_carlo_runs <= 10000):
            raise ValueError("monte_carlo_runs must be in [1, 10000]")
        self.monte_carlo_runs = monte_carlo_runs

        if not (1 <= mc_percentile <= 99):
            raise ValueError("mc_percentile must be in [1, 99]")
        self.mc_percentile = mc_percentile

        if not (1 <= walkforward_cycles <= 50):
            raise ValueError("walkforward_cycles must be in [1, 50]")
        self.walkforward_cycles = walkforward_cycles

        if not (1 <= min_trades <= 10000):
            raise ValueError("min_trades must be in [1, 10000]")
        self.min_trades = min_trades

        if not (0.5 < confidence_level < 0.99):
            raise ValueError("confidence_level must be in (0.5, 0.99)")
        self.confidence_level = confidence_level


class Retester:
    """Runs Monte Carlo / Walk-Forward retesting via sqcli.

    Workflow:
        1. Build Retester CFX with MC/WF config
        2. Run via sqcli: loadconfig → start → poll status → export
        3. Return RetestResult with paths to HTML + CSV reports
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
        config: RetesterConfig,
        campaign_name: str = "Retester",
        output_dir: Optional[Path] = None,
        timeout: float = 7200.0,
    ) -> RetestResult:
        """Run retester and return a RetestResult with HTML + CSV reports.

        Args:
            config: RetesterConfig with all parameters.
            campaign_name: Name for the campaign/project.
            output_dir: Directory for output HTML/CSV.
            timeout: Maximum time to wait for completion.

        Returns:
            RetestResult with parsed metrics and report paths.

        Raises:
            RetesterRunError: If retesting fails.
        """
        # Build CFX
        cfx_bytes = CfxTemplateBuilder.build_retester_cfx(
            strategy_id=config.strategy_id,
            databanks=config.databanks,
            mc_runs=config.monte_carlo_runs,
            mc_percentile=config.mc_percentile,
            walkforward_cycles=config.walkforward_cycles,
            min_trades=config.min_trades,
            confidence_level=config.confidence_level,
        )

        # Save CFX to temp file
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            cfx_path = Path(tmp.name)

        html_path: Optional[Path] = None
        csv_path: Optional[Path] = None

        try:
            # Load config
            await self.dispatcher.load_config(cfx_path)

            # Start campaign
            await self.dispatcher.start_project(campaign_name)

            # Wait for completion
            await self._wait_for_completion(campaign_name, timeout)

            out_dir = output_dir or Path.cwd()

            # Export HTML report
            html_result = await self.dispatcher.export_retest_report(
                campaign_name, out_dir
            )
            html_path = Path(html_result)

            # Export CSV results
            csv_result = await self.dispatcher.export_retest_csv(
                campaign_name, out_dir / f"{campaign_name}_retest.csv"
            )
            csv_path = Path(csv_result)

            # Parse CSV into RetestResult
            result = self.parse_csv(csv_path)
            result.html_path = html_path
            result.csv_path = csv_path
            result.strategy_id = config.strategy_id
            return result

        except RetesterRunError:
            raise
        except Exception as exc:
            raise RetesterRunError(str(exc)) from exc

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
        raise RetesterRunError(f"Timeout after {timeout}s")

    # ── CSV parsing ───────────────────────────────────────────────────────────

    @staticmethod
    def parse_csv(csv_path: str | Path) -> RetestResult:
        """Parse an SQX retester CSV export into a RetestResult.

        Supports two formats:

        *Key-value format* — two columns (Metric, Value) with row-wise metric
        names:

            Metric,Value
            MC_Runs,100
            MC_Percentile,95
            ...

        *Multi-column format* — a header row with column names and at least one
        data row containing metric values.

        Args:
            csv_path: Path to the CSV file exported by SQX.

        Returns:
            RetestResult with parsed Monte Carlo and Walk-Forward data.

        Raises:
            RetesterRunError: If the file is unreadable or contains no
                parseable metrics.
        """
        path = Path(csv_path)

        if not path.exists():
            raise RetesterRunError(f"CSV file not found: {csv_path}")

        try:
            raw = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise RetesterRunError(
                f"Cannot read CSV file: {csv_path}: {exc}"
            ) from exc

        # Try key-value format first (most common for SQX retester exports)
        metrics = Retester._parse_kv_csv(raw)

        # Fallback: multi-column format
        if not metrics:
            metrics = Retester._parse_multicolumn_csv(raw)

        if not metrics:
            raise RetesterRunError(
                f"No parseable metrics found in CSV: {csv_path}"
            )

        return Retester._build_result(metrics, path)

    @staticmethod
    def _parse_kv_csv(raw: str) -> dict[str, str]:
        """Parse key-value CSV (Metric,Value columns).

        Detects the format by checking:
          1. Whether the first row has a known key-value header
             (e.g. ``Metric``, ``Key``, ``Parameter`` for the key column;
             ``Value``, ``Result`` for the value column).
          2. OR the first data row already starts with a known metric prefix
             (``MC_``, ``WF_``, ``CI_``) — this is a headerless kv CSV.

        Returns a dict of metric name -> raw string value, or empty dict if
        the format does not match.
        """
        lines = raw.splitlines()
        non_empty = [ln.strip() for ln in lines if ln.strip()]
        if len(non_empty) < 2:
            return {}

        first_cell = non_empty[0].split(",")[0].strip()
        first_lower = first_cell.lower()

        # ── Sniff 1: explicit key-value header ────────────────────────
        KV_HEADER_KEYS = {"metric", "key", "name", "parameter", "statistic"}
        KV_HEADER_VALS = {"value", "result", "data"}
        second_cell = non_empty[0].split(",")[1].strip().lower() if "," in non_empty[0] else ""

        has_kv_header = (
            first_lower in KV_HEADER_KEYS
            or second_cell in KV_HEADER_VALS
        )

        # ── Sniff 2: headerless kv — first row is already a metric label
        is_headerless_kv = first_cell.upper().startswith(("MC_", "WF_", "CI_"))

        if not has_kv_header and not is_headerless_kv:
            return {}

        metrics: dict[str, str] = {}

        if is_headerless_kv:
            # Headerless: csv.reader, treat first column as key, second as value
            reader = csv.reader(io.StringIO(raw))
            for row in reader:
                if len(row) >= 2:
                    k = row[0].strip()
                    v = row[1].strip()
                    if k and v:
                        normalised = Retester._normalise_metric_name(k)
                        metrics[normalised] = v
            return metrics

        # With header: DictReader
        reader = csv.DictReader(io.StringIO(raw))
        if reader.fieldnames is None or len(reader.fieldnames) < 2:
            return {}

        key_col = reader.fieldnames[0]
        val_col = reader.fieldnames[1]

        for row in reader:
            k = row.get(key_col, "").strip()
            v = row.get(val_col, "").strip()
            if k and v:
                metrics[k] = v

        return metrics

    @staticmethod
    def _parse_multicolumn_csv(raw: str) -> dict[str, str]:
        """Parse multi-column CSV format.

        Scans header columns for known metric keywords and extracts values
        from the first data row(s).

        Returns a dict of normalised metric name -> value.
        """
        metrics: dict[str, str] = {}
        reader = csv.reader(io.StringIO(raw))
        rows = list(reader)

        if len(rows) < 2:
            return {}

        # ── Keyword-to-metric mapping for column header scanning ──
        HEADER_MAP = {
            "runs": "MC_Runs",
            "percentile": "MC_Percentile",
            "netprofit": "MC_NetProfit",
            "net_profit": "MC_NetProfit",
            "net profit": "MC_NetProfit",
            "sharpe": "MC_Sharpe",
            "sharpe_ratio": "MC_Sharpe",
            "sharpe ratio": "MC_Sharpe",
            "drawdown": "MC_Drawdown",
            "max drawdown": "MC_Drawdown",
            "ci_lower": "CI_Lower",
            "lower": "CI_Lower",
            "ci_upper": "CI_Upper",
            "upper": "CI_Upper",
            "avg_sharpe": "WF_AvgSharpe",
            "avg sharpe": "WF_AvgSharpe",
            "avg sharpe ratio": "WF_AvgSharpe",
            "avgsharpe": "WF_AvgSharpe",
            "avg_profit_factor": "WF_AvgProfitFactor",
            "avg profit factor": "WF_AvgProfitFactor",
            "avgprofitfactor": "WF_AvgProfitFactor",
            "avg_drawdown": "WF_AvgDrawdown",
            "avg drawdown": "WF_AvgDrawdown",
            "avgdrawdown": "WF_AvgDrawdown",
            "stability": "WF_Stability",
            "cycles": "WF_Cycles",
            "wf_cycles": "WF_Cycles",
        }

        # Phase A: try to find keyword columns in the header row
        headers = [h.strip().lower() for h in rows[0]]
        header_indices: dict[str, int] = {}
        for col_idx, h in enumerate(headers):
            if h in HEADER_MAP:
                header_indices[HEADER_MAP[h]] = col_idx

        if header_indices:
            # Extract values from the first data row that has content
            data_row: list[str] | None = None
            for row in rows[1:]:
                if any(cell.strip() for cell in row):
                    data_row = row
                    break

            if data_row is not None:
                for metric_key, col_idx in header_indices.items():
                    if col_idx < len(data_row):
                        val = data_row[col_idx].strip()
                        if val:
                            metrics[metric_key] = val

            # If we found enough metrics, return
            if "MC_Runs" in metrics or "MC_NetProfit" in metrics or "MC_Percentile" in metrics:
                return metrics

        # Phase B: scan each row for a known-label prefix
        for row in rows:
            if not row:
                continue
            label = row[0].strip()
            if not label:
                continue
            upper = label.upper()
            if upper == "MC_RUNS" and len(row) > 1:
                metrics["MC_Runs"] = row[1].strip()
            elif upper == "MC_PERCENTILE" and len(row) > 1:
                metrics["MC_Percentile"] = row[1].strip()
            elif upper in ("MC_NETPROFIT", "MC_NET_PROFIT") and len(row) > 1:
                metrics["MC_NetProfit"] = row[1].strip()
            elif upper in ("MC_SHARPE", "MC_SHARPE_RATIO") and len(row) > 1:
                metrics["MC_Sharpe"] = row[1].strip()
            elif upper in ("MC_DRAWDOWN", "MC_MAX_DRAWDOWN") and len(row) > 1:
                metrics["MC_Drawdown"] = row[1].strip()
            elif upper in ("CI_LOWER", "CI_LOWER_BOUND", "LOWER") and len(row) > 1:
                metrics["CI_Lower"] = row[1].strip()
            elif upper in ("CI_UPPER", "CI_UPPER_BOUND", "UPPER") and len(row) > 1:
                metrics["CI_Upper"] = row[1].strip()
            elif upper == "WF_CYCLES" and len(row) > 1:
                metrics["WF_Cycles"] = row[1].strip()
            elif upper in ("WF_AVGSHARPE", "WF_AVG_SHARPE") and len(row) > 1:
                metrics["WF_AvgSharpe"] = row[1].strip()
            elif upper in ("WF_AVGPROFITFACTOR", "WF_AVG_PROFIT_FACTOR") and len(row) > 1:
                metrics["WF_AvgProfitFactor"] = row[1].strip()
            elif upper in ("WF_AVGDRAWDOWN", "WF_AVG_DRAWDOWN") and len(row) > 1:
                metrics["WF_AvgDrawdown"] = row[1].strip()
            elif upper == "WF_STABILITY" and len(row) > 1:
                metrics["WF_Stability"] = row[1].strip()

        return metrics

    @staticmethod
    def _normalise_metric_name(raw: str) -> str:
        """Map a raw CSV metric label to the canonical metric key.

        Handles case variation, underscores vs. spaces, and known aliases.
        """
        normalised = raw.strip().upper().replace(" ", "_").replace("-", "_")

        # Remove redundant parts for fuzzy matching
        # e.g. MC_MAX_DRAWDOWN → MC_DRAWDOWN, CI_LOWER_BOUND → CI_LOWER
        for sep in ("__", "___"):
            while sep in normalised:
                normalised = normalised.replace(sep, "_")

        KNOWN = {
            "MC_RUNS": "MC_Runs",
            "MC_PERCENTILE": "MC_Percentile",
            "MC_NETPROFIT": "MC_NetProfit",
            "MC_NET_PROFIT": "MC_NetProfit",
            "MC_SHARPE": "MC_Sharpe",
            "MC_SHARPE_RATIO": "MC_Sharpe",
            "MC_DRAWDOWN": "MC_Drawdown",
            "MC_MAX_DRAWDOWN": "MC_Drawdown",
            "CI_LOWER": "CI_Lower",
            "CI_LOWER_BOUND": "CI_Lower",
            "LOWER": "CI_Lower",
            "CI_UPPER": "CI_Upper",
            "CI_UPPER_BOUND": "CI_Upper",
            "UPPER": "CI_Upper",
            "WF_CYCLES": "WF_Cycles",
            "WF_AVGSHARPE": "WF_AvgSharpe",
            "WF_AVG_SHARPE": "WF_AvgSharpe",
            "WF_AVGPROFITFACTOR": "WF_AvgProfitFactor",
            "WF_AVG_PROFIT_FACTOR": "WF_AvgProfitFactor",
            "WF_AVGDRAWDOWN": "WF_AvgDrawdown",
            "WF_AVG_DRAWDOWN": "WF_AvgDrawdown",
            "WF_STABILITY": "WF_Stability",
        }
        return KNOWN.get(normalised, raw.strip())

    @staticmethod
    def _build_result(
        metrics: dict[str, str],
        csv_path: Path,
    ) -> RetestResult:
        """Construct a RetestResult from a parsed metrics dict.

        Missing metrics are silently defaulted to zero / sensible fallbacks
        so that partial data still produces a usable result.
        """
        # Helper to safely parse floats with a fallback
        def _f(key: str, default: float = 0.0) -> float:
            raw = metrics.get(key)
            if raw is None:
                return default
            raw = raw.strip().replace(",", "").replace("%", "")
            try:
                return float(raw)
            except (ValueError, TypeError):
                return default

        def _i(key: str, default: int = 0) -> int:
            raw = metrics.get(key)
            if raw is None:
                return default
            raw = raw.strip().replace(",", "")
            try:
                return int(float(raw))
            except (ValueError, TypeError):
                return default

        mc = MonteCarloResult(
            runs=_i("MC_Runs", default=100),
            percentile=_i("MC_Percentile", default=95),
            percentile_net_profit=_f("MC_NetProfit"),
            percentile_sharpe=_f("MC_Sharpe"),
            percentile_drawdown=_f("MC_Drawdown"),
            confidence_interval=(
                _f("CI_Lower"),
                _f("CI_Upper"),
            ),
        )

        wf = WalkForwardResult(
            cycles=_i("WF_Cycles"),
            avg_sharpe_ratio=_f("WF_AvgSharpe"),
            avg_profit_factor=_f("WF_AvgProfitFactor"),
            avg_drawdown=_f("WF_AvgDrawdown"),
            stability=_f("WF_Stability"),
        )

        return RetestResult(
            strategy_id="",
            monte_carlo=mc,
            walk_forward=wf,
            csv_path=csv_path,
        )

    # ── HTML report generation ────────────────────────────────────────────────

    @staticmethod
    def to_html(result: RetestResult, output_path: str | Path) -> Path:
        """Generate a self-contained HTML report for a RetestResult.

        The report includes:
          - Strategy identifier
          - Monte Carlo percentile table with confidence interval
          - Walk-Forward summary table

        Args:
            result: Parsed RetestResult to render.
            output_path: Destination path for the HTML file.

        Returns:
            The resolved Path to the generated HTML file.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        strategy_display = result.strategy_id or "(unknown)"
        ci_lower, ci_upper = result.monte_carlo.confidence_interval

        def _fmt(v: float, decimals: int = 2) -> str:
            """Format a float nicely, defaulting to '-' for zeros."""
            if v == 0.0:
                return "0.00"
            return f"{v:,.{decimals}f}"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Retest Report — {strategy_display}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
    max-width: 960px; margin: 2em auto; padding: 0 1em;
    color: #1a1a1a; background: #fafafa;
    line-height: 1.6;
  }}
  h1 {{ font-size: 1.6rem; border-bottom: 2px solid #2563eb; padding-bottom: 0.3em; margin-bottom: 1em; }}
  h2 {{ font-size: 1.2rem; color: #2563eb; margin-top: 1.6em; margin-bottom: 0.6em; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1em 0; background: #fff;
           border: 1px solid #d1d5db; border-radius: 6px; overflow: hidden; }}
  th {{ background: #2563eb; color: #fff; text-align: left; padding: 8px 12px;
        font-weight: 600; font-size: 0.9rem; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:nth-child(even) td {{ background: #f9fafb; }}
  .section {{ margin: 1.5em 0; }}
  .ci {{ font-size: 1.1rem; font-weight: 600; color: #2563eb; }}
  .stability-good {{ color: #16a34a; font-weight: 600; }}
  .stability-warn {{ color: #ca8a04; font-weight: 600; }}
  .stability-poor {{ color: #dc2626; font-weight: 600; }}
  .meta {{ font-size: 0.85rem; color: #6b7280; margin-top: 2em; padding-top: 0.8em;
           border-top: 1px solid #d1d5db; }}
</style>
</head>
<body>

<h1>Retest Report — {strategy_display}</h1>

<div class="section">
  <h2>Monte Carlo Simulation</h2>
  <table>
    <thead><tr><th>Metric</th><th>Value</th></tr></thead>
    <tbody>
      <tr><td>Runs</td><td>{result.monte_carlo.runs}</td></tr>
      <tr><td>Percentile</td><td>{result.monte_carlo.percentile}%</td></tr>
      <tr><td>Net Profit (P{result.monte_carlo.percentile})</td><td>{_fmt(result.monte_carlo.percentile_net_profit)}</td></tr>
      <tr><td>Sharpe Ratio (P{result.monte_carlo.percentile})</td><td>{_fmt(result.monte_carlo.percentile_sharpe)}</td></tr>
      <tr><td>Drawdown (P{result.monte_carlo.percentile})</td><td>{_fmt(result.monte_carlo.percentile_drawdown)}%</td></tr>
    </tbody>
  </table>
</div>

<div class="section">
  <h2>Confidence Interval (P{result.monte_carlo.percentile})</h2>
  <table>
    <thead><tr><th>Bound</th><th>Net Profit</th></tr></thead>
    <tbody>
      <tr><td>Lower</td><td>{_fmt(ci_lower)}</td></tr>
      <tr><td>Upper</td><td>{_fmt(ci_upper)}</td></tr>
    </tbody>
  </table>
  <p class="ci">Net Profit range: {_fmt(ci_lower)} – {_fmt(ci_upper)}</p>
</div>

<div class="section">
  <h2>Walk-Forward Analysis</h2>
  <table>
    <thead><tr><th>Metric</th><th>Value</th></tr></thead>
    <tbody>
      <tr><td>Cycles</td><td>{result.walk_forward.cycles}</td></tr>
      <tr><td>Avg Sharpe Ratio</td><td>{_fmt(result.walk_forward.avg_sharpe_ratio)}</td></tr>
      <tr><td>Avg Profit Factor</td><td>{_fmt(result.walk_forward.avg_profit_factor)}</td></tr>
      <tr><td>Avg Drawdown</td><td>{_fmt(result.walk_forward.avg_drawdown)}%</td></tr>
      <tr><td>Stability</td><td class="{Retester._stability_class(result.walk_forward.stability)}">{_fmt(result.walk_forward.stability, 2)}%</td></tr>
    </tbody>
  </table>
</div>

<div class="meta">
  Generated by QuantLab SDK — Retester
  {(" &middot; CSV: " + str(result.csv_path.name)) if result.csv_path else ""}
</div>

</body>
</html>"""

        path.write_text(html, encoding="utf-8")
        return path

    @staticmethod
    def _stability_class(stability: float) -> str:
        """Return a CSS class for stability-based colouring."""
        if stability >= 0.8:
            return "stability-good"
        elif stability >= 0.6:
            return "stability-warn"
        return "stability-poor"

    # ── Dry run ───────────────────────────────────────────────────────────────

    def dry_run(self, config: RetesterConfig) -> str:
        """Generate CFX as base64 JSON for dry-run testing."""
        cfx_bytes = CfxTemplateBuilder.build_retester_cfx(
            strategy_id=config.strategy_id,
            databanks=config.databanks,
            mc_runs=config.monte_carlo_runs,
            mc_percentile=config.mc_percentile,
            walkforward_cycles=config.walkforward_cycles,
            min_trades=config.min_trades,
            confidence_level=config.confidence_level,
        )
        return base64.b64encode(cfx_bytes).decode()
