"""QuantLab CLI — Entry point for Phase 4 automation commands.

Provides subcommands for:
- daemon: SQX -gui server lifecycle (start/stop/status)
- portfolio: Portfolio Master genetic builder
- optimizer: Walk-forward optimization
- retester: Monte Carlo / Walk-Forward retesting
- jforex: JForex 4 strategy/indicator deployment
- pipeline: Pipeline execution and management (Phase 5d)

All commands use async HTTP API via CommandDispatcher with automatic
daemon management and dry-run support.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from quantlab.phase4.daemon import SQXDaemonManager
from quantlab.phase4.command_dispatcher import CommandDispatcher
from quantlab.phase4.templates import CfxTemplateBuilder
from quantlab.phase4.errors import (
    SQXDaemonStartError,
    SQXBindingError,
    JForexStrategyNotFoundError,
    SQXSessionLockError,
    OptimizerRunError,
    RetesterRunError,
    RetesterDatabankError,
    DatabankPathError,
)
from quantlab.phase4.http_client import AsyncSQXClient
from quantlab.phase4.jforex_deploy import JForexDeployer
from quantlab.phase4.optimizer import Optimizer, OptimizerConfig
from quantlab.phase4.portfolio_master import PortfolioMaster
from quantlab.phase4.retester import Retester, RetesterConfig
from quantlab.translate.cfx import CfxArchiveFactory, CfxResult

# Pipeline command handlers (Phase 5d)
from quantlab.cli.pipeline_commands import (
    cmd_pipeline_run,
    cmd_pipeline_list,
    cmd_pipeline_history,
)

# Knowledge command handlers (Phase 5c)
from quantlab.cli.knowledge_commands import add_knowledge_subparser
from quantlab.cli.agent_commands import add_agent_subparser

# ──────────────────────────────────────────────────────────────────────────────
# Constants & Defaults
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_SQX_PATH = "/opt/StrategyQuantX"
DEFAULT_PORT = 8888
DEFAULT_OUTPUT_DIR = Path.cwd() / "_output"
DEFAULT_DRY_RUN_DIR = Path.cwd() / "_output"

EXIT_OK = 0
EXIT_ERROR = 1


# ──────────────────────────────────────────────────────────────────────────────
# Helper: Output formatting
# ──────────────────────────────────────────────────────────────────────────────


def print_json(data: dict | list, pretty: bool = True) -> None:
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


def print_error(message: str) -> None:
    """Print error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────────────
# Daemon Management
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_daemon_start(args: argparse.Namespace) -> int:
    """Start SQX -gui daemon."""
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    print_human(f"Starting SQX daemon at {sqx_path}:{port}...")

    try:
        daemon = SQXDaemonManager(
            str(sqx_path),
            port=port,
            startup_timeout=args.timeout,
        )
        base_url = await daemon.start()
        print_human(f"Daemon started: {base_url}")
        return EXIT_OK
    except SQXDaemonStartError as e:
        print_error(f"Failed to start daemon: {e}")
        return EXIT_ERROR
    except SQXBindingError as e:
        print_error(f"Binding error: {e}")
        return EXIT_ERROR
    except FileNotFoundError:
        print_error(
            f"SQX not found at {sqx_path}. Use --sqx-path to specify install location."
        )
        return EXIT_ERROR


async def cmd_daemon_stop(args: argparse.Namespace) -> int:
    """Stop SQX -gui daemon."""
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    print_human(f"Stopping SQX daemon at {sqx_path}:{port}...")

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        await daemon.stop(force=args.force)
        print_human("Daemon stopped.")
        return EXIT_OK
    except Exception as e:
        print_error(f"Failed to stop daemon: {e}")
        return EXIT_ERROR


async def cmd_daemon_status(args: argparse.Namespace) -> int:
    """Check SQX daemon health."""
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    healthy = await daemon.health_check()

    if args.json:
        print_json({"healthy": healthy, "url": daemon.base_url})
    else:
        status = "healthy" if healthy else "unhealthy"
        print_human(f"Daemon at {daemon.base_url}: {status}")

    return EXIT_OK if healthy else EXIT_ERROR


# ──────────────────────────────────────────────────────────────────────────────
# Portfolio Master
# ──────────────────────────────────────────────────────────────────────────────


def _parse_strategies(args: argparse.Namespace) -> list[str]:
    """Parse strategy IDs from args (comma-separated or space-separated)."""
    if args.strategies:
        # Handle comma-separated or space-separated
        strategies = []
        for s in args.strategies:
            strategies.extend(s.split(","))
        return [s.strip() for s in strategies if s.strip()]
    return []


async def cmd_portfolio_run(args: argparse.Namespace) -> int:
    """Run Portfolio Master genetic builder."""
    strategies = _parse_strategies(args)
    if not strategies:
        print_error("At least one strategy ID required (use --strategies)")
        return EXIT_ERROR

    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        # Dry-run: generate CFX JSON without dispatching
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(
            strategies=strategies,
            generations=args.generations,
            population=args.population,
            fitness=args.fitness,
            min_strategies=args.min_strategies,
            max_strategies=args.max_strategies,
            rebalance=args.rebalance,
        )

        result = {
            "type": "portfolio",
            "dry_run": True,
            "strategies": strategies,
            "generations": args.generations,
            "population": args.population,
            "fitness": args.fitness,
            "min_strategies": args.min_strategies,
            "max_strategies": args.max_strategies,
            "rebalance": args.rebalance,
            "cfx_base64": base64.b64encode(cfx_bytes).decode(),
        }
        if args.json:
            print_json(result)
        else:
            print_human("Dry-run: Portfolio CFX generated (not dispatched)")
            print_human(f"Strategies: {', '.join(strategies)}")
            print_human(f"Generations: {args.generations}, Population: {args.population}")
            print_human(f"Fitness: {args.fitness}")
        return EXIT_OK

    # Real run: start daemon, dispatch via CommandDispatcher
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        base_url = await daemon.start()
        print_human(f"Daemon started: {base_url}")

        dispatcher = await CommandDispatcher.from_daemon(daemon)

        # Build CFX
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(
            strategies=strategies,
            generations=args.generations,
            population=args.population,
            fitness=args.fitness,
            min_strategies=args.min_strategies,
            max_strategies=args.max_strategies,
            rebalance=args.rebalance,
        )

        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            cfx_path = Path(tmp.name)

        try:
            campaign_name = args.name or "PortfolioMaster"
            dispatcher.load_config(cfx_path)
            dispatcher.start_project(campaign_name)

            # Wait for completion
            print_human(f"Running Portfolio Master campaign: {campaign_name}...")
            await _wait_for_completion(dispatcher, campaign_name)

            # Export results
            output_path = dispatcher.export_results(campaign_name, output_dir)
            print_human(f"Results exported to: {output_path}")

            if args.json:
                print_json({"campaign": campaign_name, "output": output_path})
        finally:
            cfx_path.unlink(missing_ok=True)

        return EXIT_OK

    except JForexStrategyNotFoundError as e:
        print_error(f"Strategy not found: {e}")
        return EXIT_ERROR
    except SQXSessionLockError as e:
        print_error(f"SQX session busy: {e}")
        return EXIT_ERROR
    except SQXDaemonStartError as e:
        print_error(f"Failed to start daemon: {e}")
        return EXIT_ERROR
    except Exception as e:
        print_error(f"Portfolio run failed: {e}")
        return EXIT_ERROR
    finally:
        if not args.no_daemon_stop:
            await daemon.stop()


async def cmd_portfolio_status(args: argparse.Namespace) -> int:
    """Get Portfolio Master campaign status."""
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        await daemon.start()
        dispatcher = await CommandDispatcher.from_daemon(daemon)
        status = await dispatcher.get_status(args.name)

        if args.json:
            print_json(
                {
                    "campaign": status.campaign_name,
                    "status": status.status,
                    "progress": status.progress,
                    "current_generation": status.current_generation,
                    "total_generations": status.total_generations,
                    "error": status.error_message,
                }
            )
        else:
            print_human(f"Campaign: {status.campaign_name}")
            print_human(f"Status: {status.status}")
            print_human(f"Progress: {status.progress:.1f}%")
            print_human(
                f"Generation: {status.current_generation}/{status.total_generations}"
            )
            if status.error_message:
                print_error(f"Error: {status.error_message}")

        return EXIT_OK
    except Exception as e:
        print_error(f"Status check failed: {e}")
        return EXIT_ERROR
    finally:
        await daemon.stop()


async def cmd_portfolio_export(args: argparse.Namespace) -> int:
    """Export Portfolio Master results."""
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        await daemon.start()
        dispatcher = await CommandDispatcher.from_daemon(daemon)

        output_path = await dispatcher.export_results(args.name, output_dir)

        if args.json:
            print_json({"campaign": args.name, "output": output_path})
        else:
            print_human(f"Results exported to: {output_path}")

        return EXIT_OK
    except Exception as e:
        print_error(f"Export failed: {e}")
        return EXIT_ERROR
    finally:
        await daemon.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Optimizer
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_optimizer_run(args: argparse.Namespace) -> int:
    """Run walk-forward optimization."""
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        config = OptimizerConfig(
            strategy_id=args.strategy_id,
            method=args.method,
            objective=args.objective,
            walkforward_cycles=args.walkforward_cycles,
            population=args.population,
            generations=args.generations,
            crossover=args.crossover,
            mutation=args.mutation,
            databanks=args.databanks or [],
        )
        optimizer = Optimizer(str(args.sqx_path or DEFAULT_SQX_PATH))
        cfx_b64 = optimizer.dry_run(config)

        result = {
            "type": "optimizer",
            "dry_run": True,
            "strategy_id": args.strategy_id,
            "method": args.method,
            "objective": args.objective,
            "walkforward_cycles": args.walkforward_cycles,
            "population": args.population,
            "generations": args.generations,
            "crossover": args.crossover,
            "mutation": args.mutation,
            "databanks": args.databanks or [],
            "cfx_base64": cfx_b64,
        }
        if args.json:
            print_json(result)
        else:
            print_human("Dry-run: Optimizer CFX generated (not dispatched)")
            print_human(f"Strategy: {args.strategy_id}")
            print_human(f"Method: {args.method}, Objective: {args.objective}")
            print_human(f"WF Cycles: {args.walkforward_cycles}")
        return EXIT_OK

    # Real run
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        base_url = await daemon.start()
        print_human(f"Daemon started: {base_url}")

        config = OptimizerConfig(
            strategy_id=args.strategy_id,
            method=args.method,
            objective=args.objective,
            walkforward_cycles=args.walkforward_cycles,
            population=args.population,
            generations=args.generations,
            crossover=args.crossover,
            mutation=args.mutation,
            databanks=args.databanks or [],
        )

        optimizer = Optimizer(str(sqx_path))
        result = await optimizer.run(
            config,
            campaign_name=args.name or "Optimizer",
            output_dir=output_dir,
        )

        if args.json:
            print_json({
                "campaign": args.name or "Optimizer",
                "output": str(result.raw_path) if result.raw_path else None,
                "strategy_id": result.strategy_id,
                "num_cycles": len(result.cycles),
                "summary": result.summary,
            })
        else:
            csv_path = result.raw_path or "unknown"
            print_human(f"Optimization results: {csv_path}")
            print_human(f"Cycles: {len(result.cycles)}")
            if result.summary:
                sharpe = result.summary.get("avg_sharpe")
                if sharpe is not None:
                    print_human(f"Avg Sharpe: {sharpe:.4f}")

        return EXIT_OK

    except JForexStrategyNotFoundError as e:
        print_error(f"Strategy not found: {e}")
        return EXIT_ERROR
    except Exception as e:
        print_error(f"Optimizer run failed: {e}")
        return EXIT_ERROR
    finally:
        if not args.no_daemon_stop:
            await daemon.stop()


async def cmd_optimizer_status(args: argparse.Namespace) -> int:
    """Get optimizer campaign status."""
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        await daemon.start()
        dispatcher = await CommandDispatcher.from_daemon(daemon)
        status = await dispatcher.get_status(args.name)

        if args.json:
            print_json(
                {
                    "campaign": status.campaign_name,
                    "status": status.status,
                    "progress": status.progress,
                    "current_generation": status.current_generation,
                    "total_generations": status.total_generations,
                    "error": status.error_message,
                }
            )
        else:
            print_human(f"Campaign: {status.campaign_name}")
            print_human(f"Status: {status.status}")
            print_human(f"Progress: {status.progress:.1f}%")
            if status.error_message:
                print_error(f"Error: {status.error_message}")

        return EXIT_OK
    except Exception as e:
        print_error(f"Status check failed: {e}")
        return EXIT_ERROR
    finally:
        await daemon.stop()


async def cmd_optimizer_export(args: argparse.Namespace) -> int:
    """Export optimizer results."""
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        await daemon.start()
        dispatcher = await CommandDispatcher.from_daemon(daemon)

        output_path = await dispatcher.export_optimization_results(
            args.name, output_dir
        )

        if args.json:
            print_json({"campaign": args.name, "output": output_path})
        else:
            print_human(f"Results exported to: {output_path}")

        return EXIT_OK
    except Exception as e:
        print_error(f"Export failed: {e}")
        return EXIT_ERROR
    finally:
        await daemon.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Retester
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_retester_run(args: argparse.Namespace) -> int:
    """Run Monte Carlo / Walk-Forward retesting."""
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if not args.databanks:
        print_error("--databanks is required for retester")
        return EXIT_ERROR

    if args.dry_run:
        config = RetesterConfig(
            strategy_id=args.strategy_id,
            databanks=args.databanks,
            monte_carlo_runs=args.mc_runs,
            mc_percentile=args.mc_percentile,
            walkforward_cycles=args.walkforward_cycles,
            min_trades=args.min_trades,
            confidence_level=args.confidence_level,
        )
        retester = Retester(str(args.sqx_path or DEFAULT_SQX_PATH))
        cfx_b64 = retester.dry_run(config)

        result = {
            "type": "retester",
            "dry_run": True,
            "strategy_id": args.strategy_id,
            "databanks": args.databanks,
            "mc_runs": args.mc_runs,
            "mc_percentile": args.mc_percentile,
            "walkforward_cycles": args.walkforward_cycles,
            "min_trades": args.min_trades,
            "confidence_level": args.confidence_level,
            "cfx_base64": cfx_b64,
        }
        if args.json:
            print_json(result)
        else:
            print_human("Dry-run: Retester CFX generated (not dispatched)")
            print_human(f"Strategy: {args.strategy_id}")
            print_human(f"Databanks: {', '.join(args.databanks)}")
            print_human(f"MC Runs: {args.mc_runs}, Percentile: {args.mc_percentile}")
            print_human(f"WF Cycles: {args.walkforward_cycles}")
        return EXIT_OK

    # Real run
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        base_url = await daemon.start()
        print_human(f"Daemon started: {base_url}")

        config = RetesterConfig(
            strategy_id=args.strategy_id,
            databanks=args.databanks,
            monte_carlo_runs=args.mc_runs,
            mc_percentile=args.mc_percentile,
            walkforward_cycles=args.walkforward_cycles,
            min_trades=args.min_trades,
            confidence_level=args.confidence_level,
        )

        retester = Retester(str(sqx_path))
        html_path = await retester.run(
            config,
            campaign_name=args.name or "Retester",
            output_dir=output_dir,
        )

        if args.json:
            print_json({"campaign": args.name or "Retester", "output": str(html_path)})
        else:
            print_human(f"Retest report: {html_path}")

        return EXIT_OK

    except (RetesterRunError, RetesterDatabankError, DatabankPathError) as e:
        print_error(f"Retester failed: {e}")
        return EXIT_ERROR
    except Exception as e:
        print_error(f"Retester run failed: {e}")
        return EXIT_ERROR
    finally:
        if not args.no_daemon_stop:
            await daemon.stop()


async def cmd_retester_status(args: argparse.Namespace) -> int:
    """Get retester campaign status."""
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        await daemon.start()
        dispatcher = await CommandDispatcher.from_daemon(daemon)
        status = await dispatcher.get_status(args.name)

        if args.json:
            print_json(
                {
                    "campaign": status.campaign_name,
                    "status": status.status,
                    "progress": status.progress,
                    "error": status.error_message,
                }
            )
        else:
            print_human(f"Campaign: {status.campaign_name}")
            print_human(f"Status: {status.status}")
            print_human(f"Progress: {status.progress:.1f}%")
            if status.error_message:
                print_error(f"Error: {status.error_message}")

        return EXIT_OK
    except Exception as e:
        print_error(f"Status check failed: {e}")
        return EXIT_ERROR
    finally:
        await daemon.stop()


async def cmd_retester_export(args: argparse.Namespace) -> int:
    """Export retester reports."""
    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        await daemon.start()
        dispatcher = await CommandDispatcher.from_daemon(daemon)

        # Export both HTML and CSV
        html_path = await dispatcher.export_retest_report(args.name, output_dir)
        csv_path = await dispatcher.export_retest_csv(args.name, output_dir)

        if args.json:
            print_json(
                {
                    "campaign": args.name,
                    "html": str(html_path),
                    "csv": str(csv_path),
                }
            )
        else:
            print_human(f"HTML report: {html_path}")
            print_human(f"CSV results: {csv_path}")

        return EXIT_OK
    except Exception as e:
        print_error(f"Export failed: {e}")
        return EXIT_ERROR
    finally:
        await daemon.stop()


# ──────────────────────────────────────────────────────────────────────────────
# JForex Deploy
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_jforex_deploy(args: argparse.Namespace) -> int:
    """Export strategy to JForex 4 and optionally deploy indicators."""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sqx_path = Path(args.sqx_path or DEFAULT_SQX_PATH)
    port = args.port

    if args.dry_run:
        daemon = SQXDaemonManager(str(sqx_path), port=port)
        try:
            await daemon.start()
            client = AsyncSQXClient(daemon.base_url)
            deployer = JForexDeployer(client)
            java_source = await deployer.dry_run_export(args.strategy_id)
            await client.close()

            if args.json:
                print_json({"strategy_id": args.strategy_id, "java_source": java_source})
            else:
                print_human("Dry-run: JForex export (not written to disk)")
                print_human(f"Strategy: {args.strategy_id}")
        except Exception as e:
            print_error(f"Dry-run export failed: {e}")
            return EXIT_ERROR
        finally:
            await daemon.stop()
        return EXIT_OK

    # Real run
    daemon = SQXDaemonManager(str(sqx_path), port=port)
    try:
        base_url = await daemon.start()
        print_human(f"Daemon started: {base_url}")

        client = AsyncSQXClient(base_url)
        deployer = JForexDeployer(client)

        java_path = await deployer.export_strategy(
            args.strategy_id, output_dir, strategy_name=args.name
        )

        if args.json:
            print_json({"strategy_id": args.strategy_id, "output": str(java_path)})
        else:
            print_human(f"Exported: {java_path}")

        if args.deploy_indicators:
            if not args.jforex_dir:
                print_error("--jforex-dir required when --deploy-indicators is set")
                return EXIT_ERROR
            try:
                copied = await deployer.deploy_indicators(
                    args.jforex_dir,
                    sqx_custom_indicators_dir=args.sqx_indicators_dir,
                )
                if args.json:
                    print_json({"deployed_indicators": [str(p) for p in copied]})
                else:
                    print_human(f"Deployed {len(copied)} indicator files")
            except Exception as e:
                print_error(f"Indicator deployment failed: {e}")
                return EXIT_ERROR

        await client.close()
        return EXIT_OK

    except JForexStrategyNotFoundError as e:
        print_error(f"Strategy not found: {e}")
        return EXIT_ERROR
    except JForexConnectionError as e:
        print_error(f"Connection failed: {e}")
        return EXIT_ERROR
    except Exception as e:
        print_error(f"JForex deploy failed: {e}")
        return EXIT_ERROR
    finally:
        if not args.no_daemon_stop:
            await daemon.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Report Command Handlers
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_report_generate(args: argparse.Namespace) -> int:
    """Generate campaign report (HTML/JSON)."""
    from quantlab.reporting.cli import generate_report_command
    return generate_report_command(args)


async def _wait_for_completion(
    dispatcher: CommandDispatcher, campaign_name: str, timeout: float = 3600.0
) -> None:
    """Poll campaign status until complete."""
    import time

    start = time.time()
    while time.time() - start < timeout:
        status = await dispatcher.get_status(campaign_name)
        if status.is_complete:
            print_human(f"Campaign '{campaign_name}' completed!")
            return
        if status.is_failed:
            raise RuntimeError(f"Campaign failed: {status.error_message}")
        print_human(
            f"  Progress: {status.progress:.1f}% "
            f"(gen {status.current_generation}/{status.total_generations})"
        )
        await asyncio.sleep(10.0)
    raise TimeoutError(f"Timeout waiting for {campaign_name}")


# ──────────────────────────────────────────────────────────────────────────────
# Argument Parser Construction
# ──────────────────────────────────────────────────────────────────────────────


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments shared by all subcommands."""
    parser.add_argument(
        "--sqx-path",
        default=DEFAULT_SQX_PATH,
        help=f"Path to SQX installation (default: {DEFAULT_SQX_PATH})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"SQX -gui port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate CFX/export but do not dispatch to SQX",
    )
    parser.add_argument(
        "--no-daemon-stop",
        action="store_true",
        help="Leave daemon running after command completes",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the complete argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="quantlab-cli",
        description="QuantLab AI — Phase 4 SQX Automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--version", action="version", version="quantlab-cli 0.1.0"
    )

    subparsers = parser.add_subparsers(
        dest="command", metavar="COMMAND", required=True
    )

    # ── daemon ──────────────────────────────────────────────────────────────
    p_daemon = subparsers.add_parser(
        "daemon", help="SQX -gui daemon lifecycle"
    )
    daemon_sub = p_daemon.add_subparsers(dest="daemon_cmd", required=True)

    p_start = daemon_sub.add_parser("start", help="Start SQX daemon")
    _add_common_args(p_start)
    p_start.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Daemon startup timeout (seconds)",
    )
    p_start.set_defaults(func=cmd_daemon_start)

    p_stop = daemon_sub.add_parser("stop", help="Stop SQX daemon")
    _add_common_args(p_stop)
    p_stop.add_argument(
        "--force",
        action="store_true",
        help="Force kill (SIGKILL) instead of graceful shutdown",
    )
    p_stop.set_defaults(func=cmd_daemon_stop)

    p_status = daemon_sub.add_parser("status", help="Check daemon health")
    _add_common_args(p_status)
    p_status.set_defaults(func=cmd_daemon_status)

    # ── portfolio ───────────────────────────────────────────────────────────
    p_portfolio = subparsers.add_parser("portfolio", help="Portfolio Master")
    portfolio_sub = p_portfolio.add_subparsers(
        dest="portfolio_cmd", required=True
    )

    p_pf_run = portfolio_sub.add_parser("run", help="Run Portfolio Master genetic builder")
    _add_common_args(p_pf_run)
    p_pf_run.add_argument(
        "--strategies",
        nargs="+",
        required=True,
        help="Strategy IDs (comma or space separated)",
    )
    p_pf_run.add_argument(
        "--generations", type=int, default=50, help="GA generations"
    )
    p_pf_run.add_argument(
        "--population", type=int, default=200, help="GA population size"
    )
    p_pf_run.add_argument(
        "--fitness", default="NetProfit", help="Fitness function"
    )
    p_pf_run.add_argument(
        "--min-strategies", type=int, default=2, help="Min strategies in portfolio"
    )
    p_pf_run.add_argument(
        "--max-strategies", type=int, default=10, help="Max strategies in portfolio"
    )
    p_pf_run.add_argument(
        "--rebalance", default="Monthly", help="Rebalancing period"
    )
    p_pf_run.add_argument(
        "--name", default="PortfolioMaster", help="Campaign name"
    )
    p_pf_run.add_argument(
        "--output-dir", help="Output directory for results"
    )
    p_pf_run.set_defaults(func=cmd_portfolio_run)

    p_pf_status = portfolio_sub.add_parser("status", help="Get campaign status")
    _add_common_args(p_pf_status)
    p_pf_status.add_argument("name", help="Campaign name")
    p_pf_status.set_defaults(func=cmd_portfolio_status)

    p_pf_export = portfolio_sub.add_parser("export", help="Export campaign results")
    _add_common_args(p_pf_export)
    p_pf_export.add_argument("name", help="Campaign name")
    p_pf_export.add_argument("--output-dir", help="Output directory")
    p_pf_export.set_defaults(func=cmd_portfolio_export)

    # ── optimizer ───────────────────────────────────────────────────────────
    p_optimizer = subparsers.add_parser("optimizer", help="Walk-forward optimizer")
    optimizer_sub = p_optimizer.add_subparsers(dest="optimizer_cmd", required=True)

    p_opt_run = optimizer_sub.add_parser("run", help="Run optimization")
    _add_common_args(p_opt_run)
    p_opt_run.add_argument("strategy_id", help="Strategy ID to optimize")
    p_opt_run.add_argument(
        "--method", default="Genetic", help="Optimization method"
    )
    p_opt_run.add_argument(
        "--objective", default="SharpeRatio", help="Objective function"
    )
    p_opt_run.add_argument(
        "--walkforward-cycles", type=int, default=10, help="WF cycles"
    )
    p_opt_run.add_argument(
        "--population", type=int, default=100, help="GA population"
    )
    p_opt_run.add_argument(
        "--generations", type=int, default=50, help="GA generations"
    )
    p_opt_run.add_argument(
        "--crossover", type=float, default=0.8, help="Crossover rate"
    )
    p_opt_run.add_argument(
        "--mutation", type=float, default=0.1, help="Mutation rate"
    )
    p_opt_run.add_argument(
        "--databanks", nargs="+", help="Databank symbols (e.g., EURUSD_H1)"
    )
    p_opt_run.add_argument(
        "--name", default="Optimizer", help="Campaign name"
    )
    p_opt_run.add_argument("--output-dir", help="Output directory for CSV")
    p_opt_run.set_defaults(func=cmd_optimizer_run)

    p_opt_status = optimizer_sub.add_parser("status", help="Get campaign status")
    _add_common_args(p_opt_status)
    p_opt_status.add_argument("name", help="Campaign name")
    p_opt_status.set_defaults(func=cmd_optimizer_status)

    p_opt_export = optimizer_sub.add_parser("export", help="Export optimization results")
    _add_common_args(p_opt_export)
    p_opt_export.add_argument("name", help="Campaign name")
    p_opt_export.add_argument("--output-dir", help="Output directory")
    p_opt_export.set_defaults(func=cmd_optimizer_export)

    # ── retester ────────────────────────────────────────────────────────────
    p_retester = subparsers.add_parser("retester", help="Monte Carlo / Walk-Forward retester")
    retester_sub = p_retester.add_subparsers(dest="retester_cmd", required=True)

    p_rt_run = retester_sub.add_parser("run", help="Run retester")
    _add_common_args(p_rt_run)
    p_rt_run.add_argument("strategy_id", help="Strategy ID to retest")
    p_rt_run.add_argument(
        "--databanks", nargs="+", required=True, help="Databank symbols (e.g., EURUSD_H1)"
    )
    p_rt_run.add_argument(
        "--mc-runs", type=int, default=100, help="Monte Carlo runs"
    )
    p_rt_run.add_argument(
        "--mc-percentile", type=int, default=95, help="MC percentile"
    )
    p_rt_run.add_argument(
        "--walkforward-cycles", type=int, default=5, help="WF cycles"
    )
    p_rt_run.add_argument(
        "--min-trades", type=int, default=30, help="Minimum trades"
    )
    p_rt_run.add_argument(
        "--confidence-level", type=float, default=0.95, help="Confidence level"
    )
    p_rt_run.add_argument("--name", default="Retester", help="Campaign name")
    p_rt_run.add_argument("--output-dir", help="Output directory for HTML/CSV")
    p_rt_run.set_defaults(func=cmd_retester_run)

    p_rt_status = retester_sub.add_parser("status", help="Get campaign status")
    _add_common_args(p_rt_status)
    p_rt_status.add_argument("name", help="Campaign name")
    p_rt_status.set_defaults(func=cmd_retester_status)

    p_rt_export = retester_sub.add_parser("export", help="Export retester reports")
    _add_common_args(p_rt_export)
    p_rt_export.add_argument("name", help="Campaign name")
    p_rt_export.add_argument("--output-dir", help="Output directory")
    p_rt_export.set_defaults(func=cmd_retester_export)

    # ── jforex ──────────────────────────────────────────────────────────────
    p_jforex = subparsers.add_parser("jforex", help="JForex 4 deployment")
    jforex_sub = p_jforex.add_subparsers(dest="jforex_cmd", required=True)

    p_jf_deploy = jforex_sub.add_parser("deploy", help="Export strategy + deploy indicators")
    _add_common_args(p_jf_deploy)
    p_jf_deploy.add_argument("strategy_id", help="Strategy ID to export")
    p_jf_deploy.add_argument(
        "--output-dir", required=True, help="Output directory for .java file"
    )
    p_jf_deploy.add_argument(
        "--name", help="Custom Java class name (default: strategy_id)"
    )
    p_jf_deploy.add_argument(
        "--deploy-indicators", action="store_true", help="Deploy custom indicators"
    )
    p_jf_deploy.add_argument(
        "--jforex-dir", help="JForex SDK strategies directory"
    )
    p_jf_deploy.add_argument(
        "--sqx-indicators-dir", help="SQX custom_indicators/JForex directory"
    )
    p_jf_deploy.set_defaults(func=cmd_jforex_deploy)

# ── report ─────────────────────────────────────────────────────────────────
    p_report = subparsers.add_parser("report", help="Generate campaign reports")
    report_sub = p_report.add_subparsers(dest="report_cmd", required=True)

    p_rpt_gen = report_sub.add_parser("generate", help="Generate campaign report")
    # Don't use _add_common_args - it conflicts with explicit --json/--html/--dry-run
    p_rpt_gen.add_argument("--sqx-path", default=DEFAULT_SQX_PATH, help=f"Path to SQX installation (default: {DEFAULT_SQX_PATH})")
    p_rpt_gen.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"SQX -gui port (default: {DEFAULT_PORT})")
    p_rpt_gen.add_argument("--dry-run", action="store_true", help="Generate CFX only")
    p_rpt_gen.add_argument("--no-daemon-stop", action="store_true", help="Leave daemon running")
    p_rpt_gen.add_argument("campaign_id", help="Campaign ID")
    p_rpt_gen.add_argument("--output-dir", default="reports", help="Output directory")
    p_rpt_gen.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root path")
    p_rpt_gen.add_argument("--html", action="store_true", default=True, help="Generate HTML")
    p_rpt_gen.add_argument("--no-html", action="store_false", dest="html", help="Skip HTML")
    p_rpt_gen.add_argument("--json", action="store_true", default=True, help="Generate JSON")
    p_rpt_gen.add_argument("--no-json", action="store_false", dest="json", help="Skip JSON")
    p_rpt_gen.add_argument("--theme", choices=["light", "dark"], default="light")
    p_rpt_gen.add_argument("--no-charts", action="store_true", help="Skip charts in HTML")
    p_rpt_gen.add_argument("--title", help="Custom report title")
    p_rpt_gen.add_argument("--template", help="Custom Jinja2 template file path")
    p_rpt_gen.add_argument("--benchmark", help="Benchmark equity CSV file for comparison")
    p_rpt_gen.set_defaults(func=cmd_report_generate)

    # ── knowledge ──────────────────────────────────────────────────────────────
    add_knowledge_subparser(subparsers)

    # ── agent ──────────────────────────────────────────────────────────────────
    add_agent_subparser(subparsers)

    # ── pipeline ───────────────────────────────────────────────────────────────
    p_pipeline = subparsers.add_parser("pipeline", help="Pipeline execution and management")
    pipeline_sub = p_pipeline.add_subparsers(dest="pipeline_cmd", required=True)

    p_pipe_run = pipeline_sub.add_parser("run", help="Run a pipeline")
    # Don't use _add_common_args - it conflicts with explicit --dry-run
    p_pipe_run.add_argument("--sqx-path", default=DEFAULT_SQX_PATH, help=f"Path to SQX installation (default: {DEFAULT_SQX_PATH})")
    p_pipe_run.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"SQX -gui port (default: {DEFAULT_PORT})")
    p_pipe_run.add_argument("--dry-run", action="store_true", help="Generate CFX only")
    p_pipe_run.add_argument("--no-daemon-stop", action="store_true", help="Leave daemon running")
    p_pipe_run.add_argument("name", help="Pipeline name")
    p_pipe_run.add_argument("--config", help="Pipeline config YAML")
    p_pipe_run.add_argument("--output-dir", default="_output", help="Output directory")
    p_pipe_run.add_argument("--json", action="store_true", help="Output JSON")
    p_pipe_run.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root path")
    p_pipe_run.set_defaults(func=cmd_pipeline_run)

    p_pipe_list = pipeline_sub.add_parser("list", help="List available pipelines")
    p_pipe_list.add_argument("--config", help="Pipeline config directory or file")
    p_pipe_list.add_argument("--json", action="store_true", help="Output JSON")
    p_pipe_list.add_argument("--sqx-path", default=DEFAULT_SQX_PATH, help=f"Path to SQX installation (default: {DEFAULT_SQX_PATH})")
    p_pipe_list.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"SQX -gui port (default: {DEFAULT_PORT})")
    p_pipe_list.set_defaults(func=cmd_pipeline_list)

    p_pipe_hist = pipeline_sub.add_parser("history", help="Show pipeline run history")
    p_pipe_hist.add_argument("--json", action="store_true", help="Output JSON")
    p_pipe_hist.add_argument("--knowledge-root", default="knowledge", help="Path to Knowledge Lake (default: knowledge)")
    p_pipe_hist.add_argument("--sqx-path", default=DEFAULT_SQX_PATH, help=f"Path to SQX installation (default: {DEFAULT_SQX_PATH})")
    p_pipe_hist.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"SQX -gui port (default: {DEFAULT_PORT})")
    p_pipe_hist.add_argument("--limit", type=int, default=10)
    p_pipe_hist.add_argument("--status", choices=["running", "completed", "failed"])
    p_pipe_hist.set_defaults(func=cmd_pipeline_history)

    return parser


# ──────────────────────────────────────────────────────────────────────────────
# Entry Points
# ──────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Synchronous entry point — bridges to async command handler."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_ERROR

    # Run async command
    try:
        return asyncio.run(args.func(args))
    except KeyboardInterrupt:
        print_human("\nInterrupted.", error=True)
        return EXIT_ERROR
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return EXIT_ERROR


def cli_entry() -> int:
    """Console script entry point for pyproject.toml [project.scripts]."""
    return main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())