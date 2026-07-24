"""Campaign CLI command handlers.

Implements: campaign rollback, campaign status.
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
        knowledge_root = getattr(args, "knowledge_root", "knowledge/structured")
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


def add_campaign_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add campaign subcommands to main parser."""
    p_campaign = subparsers.add_parser("campaign", help="Campaign lifecycle management")
    campaign_sub = p_campaign.add_subparsers(dest="campaign_cmd", required=True)

    # campaign rollback
    p_rollback = campaign_sub.add_parser("rollback", help="Rollback a campaign (delete Knowledge Lake artifacts)")
    p_rollback.add_argument("campaign_id", help="Campaign ID to rollback")
    p_rollback.add_argument("--knowledge-root", default="knowledge/structured", help="Knowledge Lake root path")
    p_rollback.add_argument("--json", action="store_true", help="Output JSON")
    p_rollback.set_defaults(func=cmd_campaign_rollback)

    # campaign status
    p_status = campaign_sub.add_parser("status", help="Show campaign status")
    p_status.add_argument("campaign_id", help="Campaign ID")
    p_status.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root path")
    p_status.add_argument("--json", action="store_true", help="Output JSON")
    p_status.set_defaults(func=cmd_campaign_status)


def dispatch_campaign(args: argparse.Namespace) -> int:
    """Dispatch campaign subcommand using async runner."""
    import asyncio

    func = getattr(args, "func", None)
    if func is None:
        print_error("Campaign subcommand required. Use 'rollback' or 'status'.")
        return 1

    return asyncio.run(func(args))
