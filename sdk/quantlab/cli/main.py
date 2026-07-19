"""QuantLab CLI — main entry point with subcommand dispatch.

Usage::

    quantlab pipeline run <name> [--dry-run] [--json]
    quantlab pipeline list [--json]
    quantlab pipeline history [--limit N] [--status] [--json]
    quantlab report generate <campaign_id> [--html] [--json] [--theme]
    quantlab knowledge query [--sharpe ...] [--tags ...] [--json]
    quantlab knowledge tag <campaign_id> <tags>...
    quantlab knowledge link <parent> <children>...
    quantlab knowledge export <format> [--output]
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the main argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="quantlab",
        description="QuantLab AI — Quantitative research SDK",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="quantlab 0.1.0",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Available commands",
    )

    # pipeline subcommand
    from quantlab.cli.pipeline_commands import add_pipeline_subparser

    add_pipeline_subparser(subparsers)

    # report subcommand
    from quantlab.cli.report_commands import add_report_subparser

    add_report_subparser(subparsers)

    # knowledge subcommand
    from quantlab.cli.knowledge_commands import add_knowledge_subparser

    add_knowledge_subparser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the QuantLab CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        # Dispatch using func attribute set by each subparser
        func = getattr(args, "func", None)
        if func is None:
            parser.print_help()
            return 0

        result = func(args)
        # Handle async commands
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
