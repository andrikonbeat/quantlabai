"""Report CLI command handlers — report generate, list."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quantlab.reporting.generator import generate_report
from quantlab.reporting.models import ReportConfig, ReportFormat, ReportTheme
from quantlab.knowledge.store import KnowledgeStore


def add_report_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add the ``report`` subcommand parser with subcommands.

    Registers::

        quantlab report generate
    """
    report_parser = subparsers.add_parser("report", help="Generate campaign reports")
    report_sub = report_parser.add_subparsers(dest="report_command", required=True)

    # report generate
    gen_parser = report_sub.add_parser("generate", help="Generate a campaign report")
    gen_parser.add_argument("campaign_id", help="Campaign identifier or name")
    gen_parser.add_argument("--output-dir", default="reports", help="Output directory for reports")
    gen_parser.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root directory")
    gen_parser.add_argument("--html", action="store_true", default=True, help="Generate HTML report")
    gen_parser.add_argument("--no-html", action="store_false", dest="html", help="Skip HTML report")
    gen_parser.add_argument("--json", action="store_true", default=True, help="Generate JSON report")
    gen_parser.add_argument("--no-json", action="store_false", dest="json", help="Skip JSON report")
    gen_parser.add_argument("--theme", choices=["light", "dark"], default="light", help="Report theme")
    gen_parser.add_argument("--no-charts", action="store_true", help="Disable chart generation")
    gen_parser.add_argument("--title", help="Report title (defaults to campaign name)")
    gen_parser.add_argument("--template", help="Path to custom Jinja2 template")
    gen_parser.add_argument("--benchmark", help="Benchmark campaign ID for comparison")


def report_generate_command(args: argparse.Namespace) -> int:
    """Execute ``quantlab report generate`` command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 = success, 1 = campaign not found, 2 = generation error).
    """
    try:
        # Build formats list
        formats = []
        if getattr(args, "html", True):
            formats.append(ReportFormat.HTML)
        if getattr(args, "json", True):
            formats.append(ReportFormat.JSON)
        if not formats:
            formats = [ReportFormat.HTML, ReportFormat.JSON]

        config = ReportConfig(
            campaign_id=args.campaign_id,
            output_dir=Path(args.output_dir),
            formats=formats,
            include_charts=not getattr(args, "no_charts", False),
            theme=ReportTheme(getattr(args, "theme", "light")),
            title=getattr(args, "title", None),
            template_path=Path(args.template) if getattr(args, "template", None) else None,
        )

        # Load campaign data from Knowledge Lake
        store = KnowledgeStore(getattr(args, "knowledge_root", "knowledge"))
        trades, equity, statistics = _load_campaign_data(store, args.campaign_id)

        # Generate report
        result = generate_report(
            campaign_id=args.campaign_id,
            trades=trades,
            equity=equity,
            statistics=statistics,
            config=config,
        )

        if result.warnings:
            for w in result.warnings:
                print(f"Warning: {w}", file=sys.stderr)

        return 0

    except FileNotFoundError as e:
        print(f"Error: Campaign not found: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        return 2


def _load_campaign_data(
    store: KnowledgeStore, campaign_id: str
) -> tuple[list, list, object]:
    """Load campaign data from Knowledge Lake.

    Args:
        store: KnowledgeStore instance.
        campaign_id: Campaign identifier.

    Returns:
        Tuple of (trades, equity, statistics).

    Raises:
        FileNotFoundError: If campaign data not found in Knowledge Lake.
    """
    # Try to load from knowledge/stats/{campaign_id}.yaml
    stats_path = store.root / "stats" / f"{campaign_id}.yaml"

    if not stats_path.exists():
        raise FileNotFoundError(f"No data found for campaign '{campaign_id}'")

    import yaml

    data = yaml.safe_load(stats_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise FileNotFoundError(f"Invalid campaign data for '{campaign_id}'")

    # Parse statistics
    from quantlab.stats.models import StatsResult

    statistics = StatsResult(
        profit_factor=data.get("profit_factor"),
        sharpe_ratio=data.get("sharpe_ratio"),
        sortino_ratio=data.get("sortino_ratio"),
        max_drawdown=data.get("max_drawdown"),
        mar_ratio=data.get("mar_ratio"),
        recovery_factor=data.get("recovery_factor"),
        expectancy=data.get("expectancy"),
        expectancy_ratio=data.get("expectancy_ratio"),
        win_rate=data.get("win_rate"),
        total_trades=data.get("total_trades"),
    )

    # Load trades
    from quantlab.readers.models import Trade

    trades = []
    raw_trades = data.get("trades", [])
    for t in raw_trades:
        if isinstance(t, dict):
            from datetime import datetime

            trades.append(
                Trade(
                    entry_time=datetime.fromisoformat(t["entry_time"]) if "entry_time" in t else datetime.now(),
                    exit_time=datetime.fromisoformat(t["exit_time"]) if "exit_time" in t else datetime.now(),
                    direction=t.get("direction", "long"),
                    lots=float(t.get("lots", 1.0)),
                    profit=float(t.get("profit", 0.0)),
                )
            )

    # Load equity
    from quantlab.readers.models import EquityPoint

    equity = []
    raw_equity = data.get("equity", [])
    for e in raw_equity:
        if isinstance(e, dict):
            from datetime import datetime

            equity.append(
                EquityPoint(
                    timestamp=datetime.fromisoformat(e["timestamp"]) if "timestamp" in e else datetime.now(),
                    equity=float(e.get("equity", 0.0)),
                )
            )

    return trades, equity, statistics
