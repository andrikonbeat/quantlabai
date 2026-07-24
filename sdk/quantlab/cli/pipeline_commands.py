"""Pipeline CLI command handlers.

Implements: pipeline run, pipeline list, pipeline history.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.registry import PipelineRegistry
from quantlab.pipeline.models import PipelineRun, StageRun, StageStatus
from quantlab.pipeline.runner import PipelineRunner
from quantlab.knowledge.store import KnowledgeStore


# ──────────────────────────────────────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────────────────────────────────────

def print_json(data: dict | list, pretty: bool = True) -> None:
    """Print JSON to stdout."""
    import json
    if pretty:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(json.dumps(data, default=str))


def print_human(message: str, *, error: bool = False) -> None:
    """Print human-readable message."""
    if error:
        print(message, file=sys.stderr)
    else:
        print(message)


def print_error(message: str) -> None:
    """Print error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a simple aligned table."""
    if not rows:
        return

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Print header
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(header_line)
    print("  ".join("-" * w for w in col_widths))

    # Print rows
    for row in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(row, col_widths)))


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline Run Command
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_pipeline_run(args: argparse.Namespace) -> int:
    """Run a pipeline from registry or config file."""
    try:
        # Initialize registry
        config_dirs = [args.config] if args.config else ["pipelines"]
        registry = PipelineRegistry(config_dirs=config_dirs)

        # Load pipeline config
        if args.config:
            # Direct YAML file
            from quantlab.pipeline.config import PipelineConfig
            pipeline_config = PipelineConfig.from_yaml(args.config)
        else:
            # From registry
            pipeline_config = registry.get(args.name)

        # Dry-run mode: just build and show what would run
        if args.dry_run:
            print_human(f"Dry-run: Pipeline '{pipeline_config.name}'")
            print_human(f"Stages: {len(pipeline_config.stages)}")
            for i, stage in enumerate(pipeline_config.stages, 1):
                print_human(f"  {i}. {stage.name} (type: {stage.type})")
                if stage.config:
                    print_human(f"     config: {stage.config}")
            return 0

        # Build pipeline from config
        pipeline = registry.build_pipeline(args.name)

        # Prepare context with config
        context_dict = {
            "dry_run": args.dry_run,
            "sqx_install_path": args.sqx_path,
            "sqx_port": args.port,
            "campaign_name": args.name,
            "output_dir": args.output_dir,
            "knowledge_root": getattr(args, "knowledge_root", None),
            "research_config_path": getattr(args, "research_config", None),
            "poll_interval": getattr(args, "poll_interval", 30.0),
            "poll_timeout": getattr(args, "poll_timeout", 3600.0),
            "export_formats": getattr(args, "export_formats", ["csv"]),
            "export_databanks": getattr(args, "export_databanks", True),
        }
        # Filter out None values
        context_dict = {k: v for k, v in context_dict.items() if v is not None}

        ctx = PipelineContext(config=context_dict)

        # Create PipelineRun record for history
        run = PipelineRun(
            pipeline_name=pipeline_config.name,
            config_snapshot=pipeline_config.to_dict(),
            status=StageStatus.RUNNING,
        )

        # Initialize knowledge store if needed
        knowledge_store = None
        if context_dict.get("knowledge_root"):
            knowledge_store = KnowledgeStore(root=context_dict["knowledge_root"])
            knowledge_store.initialize()

        # Run pipeline
        runner = PipelineRunner()
        print_human(f"Running pipeline: {pipeline_config.name}")
        start_time = time.monotonic()

        try:
            result = await runner.run(pipeline, ctx)
            run.duration = time.monotonic() - start_time

            # Convert result to run record
            run.status = StageStatus.COMPLETED if result.is_successful else StageStatus.FAILED
            run.error = result.error
            run.started_at = min(
                (s.started_at for s in result.stages if s.started_at),
                default=run.started_at,
            )
            run.completed_at = max(
                (s.completed_at for s in result.stages if s.completed_at),
                default=None,
            )
            run.stages = [
                StageRun(
                    name=s.stage_name,
                    status=s.status,
                    started_at=s.started_at,
                    completed_at=s.completed_at,
                    duration=s.duration,
                    error=s.error,
                    output=s.output,
                )
                for s in result.stages
            ]

            # Collect artifacts from context
            artifacts = {}
            for key, value in ctx.artifacts.items():
                if isinstance(value, Path):
                    artifacts[key] = str(value)
                elif isinstance(value, str) and Path(value).exists():
                    artifacts[key] = value
            run.artifacts = artifacts

            if args.json:
                print_json(run.to_dict())
            else:
                if result.is_successful:
                    print_human(f"✓ Pipeline '{pipeline_config.name}' completed successfully in {run.duration:.1f}s")
                else:
                    print_human(f"✗ Pipeline '{pipeline_config.name}' failed: {result.error}", error=True)
                    return 1

        except Exception as e:
            run.duration = time.monotonic() - start_time
            run.status = StageStatus.FAILED
            run.error = f"{type(e).__name__}: {e}"
            run.completed_at = datetime.now()
            if args.json:
                print_json(run.to_dict())
            else:
                print_human(f"✗ Pipeline '{pipeline_config.name}' failed: {e}", error=True)
            return 1
        finally:
            # Persist run to Knowledge Lake
            if knowledge_store:
                knowledge_store.save_pipeline_run(run)

        return 0

    except KeyError as e:
        print_error(str(e))
        return 1
    except FileNotFoundError as e:
        print_error(f"Config file not found: {e}")
        return 1
    except yaml.YAMLError as e:
        print_error(f"Invalid YAML in pipeline config: {e}")
        return 1
    except Exception as e:
        print_error(f"Pipeline run failed: {e}")
        if args.json:
            import traceback
            print_json({"error": str(e), "traceback": traceback.format_exc()})
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline List Command
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_pipeline_list(args: argparse.Namespace) -> int:
    """List available pipelines from registry."""
    try:
        config_dirs = [args.config] if args.config else ["pipelines"]
        registry = PipelineRegistry(config_dirs=config_dirs)
        pipelines = registry.list()

        if not pipelines:
            print_human("No pipelines found.")
            if args.config:
                print_human(f"Checked: {args.config}")
            else:
                print_human("Checked: ./pipelines/")
            return 0

        if args.json:
            print_json([p.model_dump() for p in pipelines])
        else:
            rows = [
                [p.name, str(p.stage_count), p.description or "-", p.version]
                for p in pipelines
            ]
            print_table(["Name", "Stages", "Description", "Version"], rows)

        return 0

    except Exception as e:
        print_error(f"Failed to list pipelines: {e}")
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline History Command
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_pipeline_history(args: argparse.Namespace) -> int:
    """Show pipeline run history from Knowledge Lake."""
    try:
        knowledge_root = args.knowledge_root if args.knowledge_root else "knowledge"
        store = KnowledgeStore(root=knowledge_root)
        store.initialize()

        # Map status filter
        status_filter = None
        if args.status:
            status_map = {
                "running": StageStatus.RUNNING,
                "completed": StageStatus.COMPLETED,
                "failed": StageStatus.FAILED,
            }
            status_filter = status_map.get(args.status)

        runs = store.load_pipeline_runs(limit=args.limit, status=status_filter)

        if not runs:
            print_human("No pipeline runs found.")
            return 0

        if args.json:
            print_json([r.to_dict() for r in runs])
        else:
            rows = []
            for r in runs:
                status_icon = {
                    StageStatus.COMPLETED: "✓",
                    StageStatus.FAILED: "✗",
                    StageStatus.RUNNING: "⟳",
                    StageStatus.PENDING: "○",
                    StageStatus.SKIPPED: "⊘",
                }.get(r.status, "?")
                duration = f"{r.duration:.1f}s" if r.duration else "-"
                started = r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else "-"
                rows.append([
                    r.run_id[:8],
                    r.pipeline_name,
                    f"{status_icon} {r.status.value}",
                    started,
                    duration,
                    r.error[:40] + "..." if r.error and len(r.error) > 40 else (r.error or "-"),
                ])
            print_table(["Run ID", "Pipeline", "Status", "Started", "Duration", "Error"], rows)

        return 0

    except Exception as e:
        print_error(f"Failed to load history: {e}")
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Subparser Registration & Dispatch
# ──────────────────────────────────────────────────────────────────────────────

def add_pipeline_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add pipeline subcommands to main parser."""
    p_pipeline = subparsers.add_parser("pipeline", help="Pipeline execution and management")
    pipeline_sub = p_pipeline.add_subparsers(dest="pipeline_cmd", required=True)

    def _add_common_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--sqx-path", default="/opt/StrategyQuantX", help="Path to SQX installation")
        parser.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root")
        parser.add_argument("--port", type=int, default=8888, help="SQX -gui port")
        parser.add_argument("--output-dir", default="output", help="Output directory")
        parser.add_argument("--config", help="Path to pipeline YAML config file")
        parser.add_argument("--json", action="store_true", help="Output JSON")

    # pipeline run
    p_run = pipeline_sub.add_parser("run", help="Run a pipeline")
    _add_common_args(p_run)
    p_run.add_argument("name", nargs="?", default="default", help="Pipeline name (from registry)")
    p_run.add_argument("--dry-run", action="store_true", help="Show what would run without executing")
    p_run.add_argument("--research-config", help="Path to research config YAML")
    p_run.add_argument("--poll-interval", type=float, default=30.0, help="SQX polling interval (seconds)")
    p_run.add_argument("--poll-timeout", type=float, default=3600.0, help="SQX polling timeout")
    p_run.add_argument("--export-formats", nargs="+", default=["csv"], help="Export formats")
    p_run.add_argument("--no-export-databanks", action="store_false", dest="export_databanks", help="Skip databank export")
    p_run.set_defaults(func=cmd_pipeline_run)

    # pipeline list
    p_list = pipeline_sub.add_parser("list", help="List available pipelines")
    _add_common_args(p_list)
    p_list.set_defaults(func=cmd_pipeline_list)

    # pipeline history
    p_history = pipeline_sub.add_parser("history", help="Show pipeline run history")
    _add_common_args(p_history)
    p_history.add_argument("--limit", type=int, default=50, help="Max history entries")
    p_history.add_argument("--status", choices=["running", "completed", "failed"], help="Filter by status")
    p_history.set_defaults(func=cmd_pipeline_history)

    # pipeline validate - PR 6
    p_validate = pipeline_sub.add_parser("validate", help="Validate pipeline configuration")
    _add_common_args(p_validate)
    p_validate.add_argument("config", help="Path to pipeline YAML config file")
    p_validate.set_defaults(func=cmd_pipeline_validate)


async def cmd_pipeline_validate(args: argparse.Namespace) -> int:
    """Validate pipeline configuration file."""
    from quantlab.pipeline.config.models import MultiAgentPipelineConfig
    from quantlab.pipeline.config.loader import MultiAgentPipelineConfigLoader
    
    try:
        # Load and validate the configuration
        config = MultiAgentPipelineConfig.load(args.config)
        
        # Additional validation - run contract validation
        from quantlab.pipeline.runner import PipelineRunner
        from quantlab.pipeline.registry import PipelineRegistry
        
        # Create a runner to validate contracts
        registry = PipelineRegistry()
        runner = PipelineRunner(registry=registry)
        
        # Build pipeline from config to validate contracts
        pipeline = runner.build_from_config(config)
        
        # Validate contracts
        try:
            runner.validate_contracts(pipeline)
            print_human(f"✓ Configuration '{args.config}' is valid")
            print_human(f"  Pipeline: {config.pipeline.name if config.pipeline else 'unnamed'}")
            print_human(f"  Stages: {len(pipeline)}")
            if config.agents:
                print_human(f"  Agents: {len(config.agents)}")
            if hasattr(config, 'gates') and config.gates:
                print_human(f"  Gates: {len(config.gates)}")
            return 0
        except Exception as e:
            print_error(f"Contract validation failed: {e}")
            return 1
            
    except FileNotFoundError:
        print_error(f"Configuration file not found: {args.config}")
        return 1
    except Exception as e:
        print_error(f"Failed to validate configuration: {e}")
        return 1


def dispatch_pipeline(args: argparse.Namespace) -> int:
    """Dispatch pipeline subcommand using async runner."""
    import asyncio

    func = getattr(args, "func", None)
    if func is None:
        print("Error: No pipeline subcommand specified", file=sys.stderr)
        return 1

    return asyncio.run(func(args))