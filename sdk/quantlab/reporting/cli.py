"""Reporting CLI — command line interface for report generation."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from quantlab.reporting.generator import generate_report, ReportGenerator
from quantlab.reporting.models import ReportConfig, ReportFormat, ReportTheme
from quantlab.knowledge.store import KnowledgeStore


def generate_report_command(args: argparse.Namespace) -> int:
    """Execute `quantlab report generate` command."""

    # Parse formats
    formats = []
    if args.html:
        formats.append(ReportFormat.HTML)
    if args.json:
        formats.append(ReportFormat.JSON)
    if not formats:
        formats = [ReportFormat.HTML, ReportFormat.JSON]

    config = ReportConfig(
        campaign_id=args.campaign_id,
        output_dir=Path(args.output_dir),
        formats=formats,
        include_charts=not args.no_charts,
        theme=ReportTheme(args.theme),
        title=args.title,
        template_path=Path(args.template) if args.template else None,
    )

    # Load campaign data from Knowledge Lake
    try:
        store = KnowledgeStore(args.knowledge_root)
        trades, equity, statistics = _load_campaign_data(store, args.campaign_id)
    except FileNotFoundError as e:
        print(f"Error: Campaign not found: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error loading campaign data: {e}", file=sys.stderr)
        return 2

    # Load benchmark equity if provided
    benchmark_equity = None
    if args.benchmark:
        try:
            benchmark_equity = _load_benchmark_equity(args.benchmark)
        except Exception as e:
            print(f"Warning: Failed to load benchmark: {e}", file=sys.stderr)

    try:
        result = generate_report(
            campaign_id=args.campaign_id,
            trades=trades,
            equity=equity,
            statistics=statistics,
            config=config,
        )

        if args.json:
            print(f"JSON report: {result.json_path}")
        if args.html:
            print(f"HTML report: {result.html_path}")

        if result.warnings:
            for w in result.warnings:
                print(f"WARNING: {w}", file=sys.stderr)

        return 0 if result.is_successful() else 2

    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        return 2


def _load_benchmark_equity(path: str) -> list[dict]:
    """Load benchmark equity data from CSV file."""
    import csv
    from datetime import datetime

    equity = []
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Try common column names
            timestamp = row.get("timestamp") or row.get("Timestamp") or row.get("time") or row.get("Time")
            equity_val = row.get("equity") or row.get("Equity") or row.get("value") or row.get("Value")

            if timestamp and equity_val:
                try:
                    equity.append({
                        "timestamp": datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if 'T' in timestamp else timestamp,
                        "equity": float(equity_val)
                    })
                except (ValueError, TypeError):
                    pass  # Skip invalid rows

    return equity


def _load_campaign_data(store: KnowledgeStore, campaign_id: str):
    """Load campaign trades, equity, and statistics from Knowledge Lake."""
    from quantlab.readers.models import Trade, EquityPoint
    from quantlab.stats.engine import StatisticsEngine
    import yaml

    # Load stats YAML
    stats_path = store.root / "stats" / f"{campaign_id}.yaml"
    if not stats_path.exists():
        raise FileNotFoundError(f"Stats file not found: {stats_path}")

    with open(stats_path) as f:
        stats_data = yaml.safe_load(f) or {}

    # Load trades CSV
    trades_path = store.root / "results" / f"{campaign_id}.csv"
    trades = []
    if trades_path.exists():
        import csv
        with open(trades_path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map CSV columns to Trade model
                trade = Trade(
                    entry_time=row.get("entry_time", row.get("EntryTime", "")),
                    exit_time=row.get("exit_time", row.get("ExitTime", "")),
                    direction=row.get("direction", row.get("Direction", "long")),
                    lots=float(row.get("lots", row.get("Lots", 1.0))),
                    profit=float(row.get("profit", row.get("Profit", 0.0))),
                )
                trades.append(trade)

    # Load equity curve CSV
    equity_path = store.root / "structured" / f"{campaign_id}_equity.csv"
    equity = []
    if equity_path.exists():
        import csv
        with open(equity_path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                eq = EquityPoint(
                    timestamp=row.get("timestamp", row.get("Timestamp", row.get("Time", ""))),
                    equity=float(row.get("equity", row.get("Equity", row.get("Value", 0.0)))),
                )
                equity.append(eq)

    # Create StatsResult from loaded data
    engine = StatisticsEngine()
    if trades and equity:
        # Compute returns from equity
        returns = []
        if len(equity) >= 2:
            eq_vals = [e.equity for e in equity]
            for i in range(1, len(eq_vals)):
                if eq_vals[i - 1] != 0:
                    returns.append((eq_vals[i] - eq_vals[i - 1]) / eq_vals[i - 1])

        computed_stats = engine.compute_all(
            trades=trades,
            equity=equity,
            returns=returns if returns else None,
        )
        # Merge with loaded stats
        stats_dict = computed_stats.model_dump() if hasattr(computed_stats, "model_dump") else computed_stats.__dict__
        stats_dict.update({k: v for k, v in stats_data.items() if v is not None})
        statistics = type('StatsResult', (), stats_dict)()
    else:
        # Fallback to loaded stats only
        statistics = type('StatsResult', (), stats_data)()

    return trades, equity, statistics


def add_report_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add `report` subcommand to main parser."""

    report_parser = subparsers.add_parser(
        "report",
        help="Generate campaign reports",
    )
    report_sub = report_parser.add_subparsers(dest="report_cmd", required=True)

    # generate subcommand
    gen = report_sub.add_parser("generate", help="Generate campaign report")
    gen.add_argument("campaign_id", help="Campaign ID")
    gen.add_argument("--output-dir", default="reports", help="Output directory")
    gen.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root path")
    gen.add_argument("--html", action="store_true", default=True, help="Generate HTML")
    gen.add_argument("--no-html", action="store_false", dest="html", help="Skip HTML")
    gen.add_argument("--json", action="store_true", default=True, help="Generate JSON")
    gen.add_argument("--no-json", action="store_false", dest="json", help="Skip JSON")
    gen.add_argument("--theme", choices=["light", "dark"], default="light")
    gen.add_argument("--no-charts", action="store_true", help="Skip charts in HTML")
    gen.add_argument("--title", help="Custom report title")
    gen.add_argument("--template", help="Custom Jinja2 template file path")
    gen.add_argument("--benchmark", help="Benchmark equity CSV file for comparison")
    gen.set_defaults(func=generate_report_command)