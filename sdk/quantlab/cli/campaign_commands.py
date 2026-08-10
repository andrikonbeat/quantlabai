"""Campaign CLI command handlers.

Implements: campaign rollback, campaign status, and the full-campaign-flow
entry point (``campaign run-flow``, REQ-37).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


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


# ──────────────────────────────────────────────────────────────────────────────
# Campaign Rollback Command (Task 6.5)
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_campaign_rollback(args: argparse.Namespace) -> int:
    """Rollback a campaign by deleting Knowledge Lake artifacts.

    Instantiates a ``ResearchDirector`` and calls ``rollback_campaign()``
    to remove Knowledge Lake artifacts for the given campaign.
    """
    from quantlab.agents.research_director import ResearchDirector

    try:
        knowledge_root = getattr(args, "knowledge_root", "knowledge")
        director = ResearchDirector(knowledge_root=knowledge_root)

        # The rollback needs the campaign record in memory; if the director
        # was created fresh, we inject a mock record so rollback can proceed.
        # Knowledge Lake artifact deletion is the primary action.
        campaign_id = args.campaign_id

        # Check if Knowledge Lake directory exists
        campaign_dir = Path(knowledge_root) / campaign_id
        if not campaign_dir.exists():
            print_human(f"No Knowledge Lake artifacts found for campaign '{campaign_id}'")
            return 0

        # Attempt rollback.  If the campaign is not in the in-memory registry,
        # we still try Knowledge Lake deletion directly.
        try:
            director.rollback_campaign(campaign_id)
        except ValueError:
            # Campaign not in memory — delete artifacts directly
            import shutil
            shutil.rmtree(campaign_dir)
            print_human(f"Deleted Knowledge Lake artifacts for campaign '{campaign_id}'")

        if args.json:
            print_json({"campaign_id": campaign_id, "status": "rolled_back"})
        else:
            print_human(f"✓ Campaign '{campaign_id}' rolled back successfully")

        return 0

    except Exception as e:
        print_error(f"Campaign rollback failed: {e}")
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Campaign Status Command
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_campaign_status(args: argparse.Namespace) -> int:
    """Show campaign status from Knowledge Lake."""
    from quantlab.knowledge.store import KnowledgeStore

    try:
        knowledge_root = getattr(args, "knowledge_root", "knowledge")
        store = KnowledgeStore(root=knowledge_root)
        store.initialize()

        campaign_id = args.campaign_id

        # Try to load campaign record from Knowledge Lake
        try:
            record = store.load_campaign(campaign_id)
        except Exception:
            # Fall back to checking directory existence
            campaign_dir = Path(knowledge_root) / "structured" / campaign_id
            if campaign_dir.exists():
                artifacts = list(campaign_dir.iterdir())
                if args.json:
                    print_json({
                        "campaign_id": campaign_id,
                        "status": "exists",
                        "artifact_count": len(artifacts),
                        "artifacts": [str(a.name) for a in artifacts],
                    })
                else:
                    print_human(f"Campaign: {campaign_id}")
                    print_human(f"Status: exists ({len(artifacts)} artifacts)")
                return 0
            else:
                print_human(f"Campaign '{campaign_id}' not found")
                return 1

        if args.json:
            print_json(record.to_dict() if hasattr(record, "to_dict") else str(record))
        else:
            print_human(f"Campaign: {campaign_id}")
            state = getattr(record, "state", "unknown")
            print_human(f"Status: {state}")
            if hasattr(record, "error") and record.error:
                print_human(f"Error: {record.error}", error=True)

        return 0

    except Exception as e:
        print_error(f"Campaign status check failed: {e}")
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Full Campaign Flow Command (Phase 4, REQ-37)
# ──────────────────────────────────────────────────────────────────────────────


# Stop-on-non-approved actions (ADR-7): mirror DispatchStage._APPROVED_ACTIONS.
# ``GateDecision.is_approved()`` is True for APPROVE and FALLBACK only; every
# other action (REJECT, HOLD, ABORT, ESCALATE-without-fallback, missing) stops
# the flow. Values are the ``action`` strings written into
# ``gate_decision_{gate_id}`` artifacts by GateInterceptorStage.
_GATE_APPROVED_ACTIONS = frozenset({"approve", "approved", "fallback"})

# Default base directory for the decision-file channel (REQ-38).
_DEFAULT_GATE_EVENT_DIR = "/tmp/sqx-gates"


def _load_run_flow_config(args: argparse.Namespace) -> Any:
    """Load the ``ResearchConfig`` for the full-campaign flow.

    Reads a YAML/JSON config file when ``--config`` is given; otherwise builds
    a minimal config from ``--campaign`` / ``--market`` / ``--timeframe``.
    """
    from quantlab.dsl.models import IterationConfig, ResearchConfig

    config_path = getattr(args, "config", None)
    if config_path:
        import json
        from pathlib import Path

        raw = Path(config_path).read_text(encoding="utf-8")
        if config_path.endswith(".json"):
            data = json.loads(raw)
        else:
            import yaml

            data = yaml.safe_load(raw) or {}
        return ResearchConfig.model_validate(data)

    return ResearchConfig(
        campaign=getattr(args, "campaign", None) or "full-flow",
        market=getattr(args, "market", "EURUSD"),
        timeframe=getattr(args, "timeframe", "H1"),
        iteration_config=IterationConfig(max_iterations=1),
    )


async def cmd_campaign_run_flow(args: argparse.Namespace) -> int:
    """Run the full 14-phase orchestrated campaign flow (REQ-37).

    Builds the orchestrated pipeline (research → hypothesis → config →
    review → dispatch → monitor → retest → optimize → portfolio → compile →
    deploy → demo → archive → live-ops), asserts the flow-integrity invariant
    BEFORE any phase executes (a dropped phase aborts the run), then executes
    every stage in order, stopping on the first failure. Human gate stages
    are recorded as checkpoints (they resolve out-of-band); they never
    auto-approve (REQ-11).
    """
    from quantlab.agents.research_director import ResearchDirector
    from quantlab.campaign.flow import (
        PHASES,
        FlowIntegrityError,
        assert_flow_segments,
    )
    from quantlab.pipeline.base import PipelineContext

    knowledge_root = getattr(args, "knowledge_root", "knowledge")
    try:
        config = _load_run_flow_config(args)
    except Exception as e:
        print_error(f"Invalid campaign config: {e}")
        return 1

    try:
        director = ResearchDirector(knowledge_root=knowledge_root)
        pipeline = director.build_pipeline(config, orchestrated=True)
    except Exception as e:
        print_error(f"Failed to build the campaign flow: {e}")
        return 1

    # REQ-37: segment-preserving preflight BEFORE execution begins. The
    # conditional retester/optimizer stages are only required when their DSL
    # blocks are configured (ADR-1); everything else must be present and in
    # segment order (presence + post-deploy boundary + loop tail).
    stage_names = [s.name for s in pipeline.stages]
    optional_phases: tuple[str, ...] = ()
    if config.retest is None:
        optional_phases += ("retester",)
    if config.optimize is None:
        optional_phases += ("optimizer",)
    try:
        assert_flow_segments(stage_names, optional_phases=optional_phases)
    except FlowIntegrityError as exc:
        # REQ-37: abort BEFORE execution begins when the invariant fails.
        print_error(str(exc))
        return 1

    campaign_id = getattr(args, "campaign_id", None) or config.campaign
    gate_event_dir = getattr(args, "gate_event_dir", None) or _DEFAULT_GATE_EVENT_DIR
    gate_timeout = getattr(args, "gate_timeout", None)
    decisions_file = getattr(args, "gate_decisions_file", None)

    ctx = PipelineContext(config={
        "campaign_id": campaign_id,
        # The archive stage (WU-4) wires its internal HUMAN_APPROVE_ARCHIVE
        # gate_fn from these keys — same channel as the pipeline gates.
        "gate_event_dir": gate_event_dir,
        "gate_decisions_file": decisions_file,
        "gate_timeout": gate_timeout,
    })

    # Run-Flow Gate Execution (REQ) + Headless Gate Decisions (REQ): register
    # a callback per HUMAN_* gate — the interactive decision-file channel
    # (pending.json → poll → decision.json) by default, or the headless
    # decisions-file channel with --gate-decisions-file (read-only, no prompt).
    from quantlab.gates.callbacks import (
        DecisionsFileGateCallback,
        QuestionToolGateCallback,
    )

    def _gate_context_dict(gate_ctx: Any) -> dict[str, Any]:
        """Bridge the pipeline ``GateContext`` dataclass to the callback dict.

        Gate callbacks in ``quantlab.gates.callbacks`` follow the orchestrator
        protocol (``ctx: dict``); ``GateInterceptorStage`` hands them its own
        ``GateContext`` dataclass. ResearchDirector bridges the same way.
        """
        if isinstance(gate_ctx, dict):
            return gate_ctx
        return dict(gate_ctx.__dict__) if hasattr(gate_ctx, "__dict__") else dict(gate_ctx)

    def _make_callback(gate_id: str) -> Any:
        if decisions_file:
            raw = DecisionsFileGateCallback(decisions_file)
        else:
            raw = QuestionToolGateCallback(
                gate_event_dir=gate_event_dir,
                campaign_id=campaign_id,
                timeout=gate_timeout,
            )

        async def _wrapped(gate_ctx: Any, _raw: Any = raw) -> Any:
            return await _raw(_gate_context_dict(gate_ctx))

        return _wrapped

    for stage in pipeline.stages:
        gate_id = getattr(stage, "gate_id", "")
        if gate_id.startswith("HUMAN_"):
            stage.set_callback(_make_callback(gate_id))

    completed: list[str] = []
    failed: str | None = None
    for stage in pipeline.stages:
        name = getattr(stage, "name", "?")
        gate_id = getattr(stage, "gate_id", "")
        try:
            output = await stage.execute(ctx)
        except Exception as e:
            failed = name
            print_error(f"Stage '{name}' failed: {e}")
            break
        if gate_id.startswith("HUMAN_"):
            # Stop-on-non-approved (REQ Run-Flow Gate Execution): REJECT,
            # HOLD, ABORT, or a missing decision stops the flow with a
            # non-zero exit — the system never auto-approves (REQ-11) and a
            # blocked run never returns a false success.
            decision = ctx.artifacts.get(f"gate_decision_{gate_id}")
            action = (
                decision.get("action") if isinstance(decision, dict) else None
            )
            if (action or "").lower() not in _GATE_APPROVED_ACTIONS:
                failed = name
                outcome = action or "missing"
                print_error(
                    f"Gate '{gate_id}' not approved (decision: {outcome}) — "
                    "stopping the flow."
                )
                break
            completed.append(name)
            continue
        # A blocked dispatch must surface as a visible failure, never a false
        # success (REQ Run-Flow Gate Execution scenario 3).
        if isinstance(output, dict) and output.get("dispatch_blocked"):
            failed = name
            print_error(
                "Dispatch blocked: the HUMAN_APPROVE_CONFIG gate did not "
                "approve — no dispatch was attempted."
            )
            break
        completed.append(name)

    if failed is not None:
        if args.json:
            print_json({
                "campaign": config.campaign,
                "completed": completed,
                "failed": failed,
            })
        return 1

    if args.json:
        print_json({
            "campaign": config.campaign,
            "phases": list(PHASES),
            "stages": completed,
            "status": "completed",
        })
    else:
        print_human(f"Campaign '{config.campaign}' completed the full flow")
        print_human("✓ " + " → ".join(completed))
    return 0


def add_campaign_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add campaign subcommands to main parser."""
    p_campaign = subparsers.add_parser("campaign", help="Campaign lifecycle management")
    campaign_sub = p_campaign.add_subparsers(dest="campaign_cmd", required=True)

    # campaign rollback
    p_rollback = campaign_sub.add_parser("rollback", help="Rollback a campaign (delete Knowledge Lake artifacts)")
    p_rollback.add_argument("campaign_id", help="Campaign ID to rollback")
    p_rollback.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root path")
    p_rollback.add_argument("--json", action="store_true", help="Output JSON")
    p_rollback.set_defaults(func=cmd_campaign_rollback)

    # campaign status
    p_status = campaign_sub.add_parser("status", help="Show campaign status")
    p_status.add_argument("campaign_id", help="Campaign ID")
    p_status.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root path")
    p_status.add_argument("--json", action="store_true", help="Output JSON")
    p_status.set_defaults(func=cmd_campaign_status)

    # campaign run-flow (full 14-phase orchestrated flow, REQ-37)
    p_run = campaign_sub.add_parser(
        "run-flow",
        help="Run the full 14-phase orchestrated campaign flow (research → live-ops)",
    )
    p_run.add_argument("--config", default=None, help="Path to ResearchConfig YAML/JSON file")
    p_run.add_argument("--campaign", default=None, help="Campaign name (when --config is absent)")
    p_run.add_argument("--market", default="EURUSD", help="Market symbol (when --config is absent)")
    p_run.add_argument("--timeframe", default="H1", help="Timeframe (when --config is absent)")
    p_run.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root path")
    p_run.add_argument("--json", action="store_true", help="Output JSON")
    p_run.add_argument(
        "--gate-decisions-file",
        default=None,
        help="Path to a JSON decisions file for headless gate approval "
             "(maps gate_id to {action, reason, decided_by}); gates without "
             "a decision fail closed and stop the flow",
    )
    p_run.add_argument(
        "--gate-event-dir",
        default=_DEFAULT_GATE_EVENT_DIR,
        help="Base directory for the decision-file channel "
             "(pending.json / decision.json); default /tmp/sqx-gates",
    )
    p_run.add_argument(
        "--gate-timeout",
        default=None,
        type=float,
        help="Seconds to wait for an interactive gate decision before "
             "failing closed (default: wait indefinitely)",
    )
    p_run.set_defaults(func=cmd_campaign_run_flow)


def dispatch_campaign(args: argparse.Namespace) -> int:
    """Dispatch campaign subcommand using async runner."""
    import asyncio

    func = getattr(args, "func", None)
    if func is None:
        print_error(
            "Campaign subcommand required. Use 'rollback', 'status', or 'run-flow'."
        )
        return 1

    return asyncio.run(func(args))
