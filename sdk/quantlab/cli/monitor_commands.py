"""Monitor CLI command handlers — PR 3: CLI Integration.

Implements::
    quantlab monitor start --strategy X [--config path] [--daemon]
    quantlab monitor stop [--strategy X]
    quantlab monitor status [--strategy X]

Follows the ``add_*_subparser`` pattern from ``agent_commands.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from quantlab.agents.autonomous_monitor import (
    AutonomousMonitorDaemon,
    MonitorConfig,
)


# ──────────────────────────────────────────────────────────────────────────────
# Output formatting (matches agent_commands.py pattern)
# ──────────────────────────────────────────────────────────────────────────────


def print_json(data: dict[str, Any] | list[Any], pretty: bool = True) -> None:
    """Print JSON to stdout."""
    if pretty:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(json.dumps(data, default=str))


def print_human(message: str, *, error: bool = False) -> None:
    """Print human-readable message to stdout/stderr."""
    if error:
        print(message, file=sys.stderr)
    else:
        print(message)


# ──────────────────────────────────────────────────────────────────────────────
# Build config
# ──────────────────────────────────────────────────────────────────────────────


def _build_config(args: argparse.Namespace) -> MonitorConfig:
    """Build MonitorConfig from parsed CLI args.

    Prefers YAML config file when ``--config`` is provided, otherwise
    creates a config with the given strategy ID and defaults.
    """
    if getattr(args, "config", None):
        return MonitorConfig.from_yaml(args.config)
    return MonitorConfig(
        strategy_id=args.strategy,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Command handlers (async — called via asyncio.run in main.py)
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_monitor_start(args: argparse.Namespace) -> int:
    """Start the autonomous monitor daemon.

    Creates a ``MonitorConfig`` (from YAML or CLI args), instantiates
    ``AutonomousMonitorDaemon``, and calls ``start()``. The daemon runs
    as a background asyncio task.
    """
    config = _build_config(args)
    daemon = AutonomousMonitorDaemon(config)
    await daemon.start()
    print_human(f"Monitor daemon started for strategy '{config.strategy_id}'")
    return 0


async def cmd_monitor_stop(args: argparse.Namespace) -> int:
    """Stop the autonomous monitor daemon gracefully.

    Creates a ``MonitorConfig`` with the given strategy ID (or a default
    when omitted), instantiates the daemon, and calls ``stop()``.
    """
    strategy = getattr(args, "strategy", None) or "default"
    config = MonitorConfig(strategy_id=strategy)
    daemon = AutonomousMonitorDaemon(config)
    await daemon.stop()
    print_human(f"Monitor daemon stopped for strategy '{config.strategy_id}'")
    return 0


async def cmd_monitor_status(args: argparse.Namespace) -> int:
    """Display autonomous monitor daemon status as JSON.

    Creates a ``MonitorConfig``, instantiates the daemon, and prints
    the ``status()`` dict as formatted JSON.
    """
    strategy = getattr(args, "strategy", None) or "default"
    config = MonitorConfig(strategy_id=strategy)
    daemon = AutonomousMonitorDaemon(config)
    status = daemon.status()
    print_json(status)
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# Parser registration
# ──────────────────────────────────────────────────────────────────────────────


def add_monitor_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add ``monitor`` subcommand with ``start``, ``stop``, ``status``.

    Registers a ``monitor`` parser on *subparsers* with three subcommands:

    - **start**: Launch the autonomous monitor daemon. Requires ``--strategy``.
    - **stop**: Gracefully stop the daemon.
    - **status**: Show daemon status as JSON.

    Usage::

        quantlab monitor start --strategy X [--config path] [--daemon]
        quantlab monitor stop [--strategy X]
        quantlab monitor status [--strategy X]
    """
    p_monitor = subparsers.add_parser(
        "monitor",
        help="Autonomous monitor daemon lifecycle",
    )
    monitor_sub = p_monitor.add_subparsers(
        dest="monitor_cmd",
        required=True,
    )

    # ── monitor start ─────────────────────────────────────────────────────
    p_start = monitor_sub.add_parser(
        "start",
        help="Start the autonomous monitor daemon",
    )
    p_start.add_argument(
        "--strategy",
        required=True,
        help="Strategy ID to monitor",
    )
    p_start.add_argument(
        "--config",
        help="Path to YAML configuration file",
    )
    p_start.add_argument(
        "--daemon",
        action="store_true",
        help="Run as background daemon (detach from terminal)",
    )
    p_start.set_defaults(func=cmd_monitor_start)

    # ── monitor stop ──────────────────────────────────────────────────────
    p_stop = monitor_sub.add_parser(
        "stop",
        help="Stop the autonomous monitor daemon",
    )
    p_stop.add_argument(
        "--strategy",
        help="Strategy ID (optional — stops first matching daemon if omitted)",
    )
    p_stop.set_defaults(func=cmd_monitor_stop)

    # ── monitor status ────────────────────────────────────────────────────
    p_status = monitor_sub.add_parser(
        "status",
        help="Show autonomous monitor daemon status",
    )
    p_status.add_argument(
        "--strategy",
        help="Strategy ID (optional — shows status for any matching daemon)",
    )
    p_status.set_defaults(func=cmd_monitor_status)
