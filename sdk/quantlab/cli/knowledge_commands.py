"""Knowledge Lake CLI commands — query, tag, link, export."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from quantlab.knowledge.store import KnowledgeStore
from quantlab.knowledge.query import QueryBuilder
from quantlab.knowledge.models import CampaignSummary


def print_json(data: dict | list, pretty: bool = True) -> None:
    """Print JSON to stdout."""
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

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(header_line)
    print("  ".join("-" * w for w in col_widths))

    for row in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(row, col_widths)))


# ──────────────────────────────────────────────────────────────────────────────
# Knowledge Query Command
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_knowledge_query(args: argparse.Namespace) -> int:
    """Query Knowledge Lake campaigns with filters."""
    try:
        knowledge_root = getattr(args, 'knowledge_root', None) or args.sqx_path
        store = KnowledgeStore(knowledge_root)
        store.initialize()
        index = store.read_index()

        builder = QueryBuilder(index, Path(knowledge_root))

        # Apply filters
        if args.sharpe:
            op, val = args.sharpe[0], float(args.sharpe[1:])
            if op == '>':
                builder.filter_by_sharpe(min_val=val)
            elif op == '<':
                builder.filter_by_sharpe(max_val=val)
        if args.profit_factor:
            op, val = args.profit_factor[0], float(args.profit_factor[1:])
            if op == '>':
                builder.filter_by_profit_factor(min_val=val)
        if args.win_rate:
            op, val = args.win_rate[0], float(args.win_rate[1:])
            if op == '>':
                builder.filter_by_win_rate(min_val=val)
        if args.max_drawdown:
            op, val = args.max_drawdown[0], float(args.max_drawdown[1:])
            if op == '<':
                builder.filter_by_max_drawdown(max_val=val)
        if args.tags:
            builder.filter_by_tags(args.tags)
        if args.date:
            parts = args.date.split('..')
            if len(parts) == 2:
                builder.filter_by_date(parts[0] if parts[0] else None, parts[1] if parts[1] else None)
        if args.text:
            builder.search_text(args.text)
        if args.sort:
            builder.sort_by(args.sort, not args.desc)
        if args.limit:
            builder.limit(args.limit)
        if args.offset:
            builder.offset(args.offset)

        result = builder.execute()

        if args.json:
            campaigns = []
            for c in result.campaigns:
                campaigns.append({
                    "campaign_id": c.campaign_id,
                    "name": c.name,
                    "sharpe": c.metrics.sharpe_ratio if c.metrics else None,
                    "profit_factor": c.metrics.profit_factor if c.metrics else None,
                    "win_rate": c.metrics.win_rate if c.metrics else None,
                    "max_drawdown": c.metrics.max_drawdown if c.metrics else None,
                    "tags": c.tags,
                    "created": c.created.isoformat() if c.created else None,
                })
            print_json(campaigns)
        else:
            print_human(f"Found {result.total_count} campaign(s) (showing {len(result.campaigns)})")
            rows = []
            for c in result.campaigns:
                sharpe = f"{c.metrics.sharpe_ratio:.2f}" if c.metrics and c.metrics.sharpe_ratio else "-"
                pf = f"{c.metrics.profit_factor:.2f}" if c.metrics and c.metrics.profit_factor else "-"
                wr = f"{c.metrics.win_rate:.2%}" if c.metrics and c.metrics.win_rate else "-"
                dd = f"{c.metrics.max_drawdown:.2f}%" if c.metrics and c.metrics.max_drawdown else "-"
                tags = ", ".join(c.tags) if c.tags else "-"
                created = c.created.strftime("%Y-%m-%d %H:%M") if c.created else "-"
                rows.append([c.campaign_id, sharpe, pf, wr, dd, tags, created])
            print_table(["Campaign ID", "Sharpe", "PF", "Win Rate", "Max DD", "Tags", "Created"], rows)

        return 0

    except Exception as e:
        print_error(f"Query failed: {e}")
        if args.json:
            print_json({"error": str(e)})
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Knowledge Tag Command
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_knowledge_tag(args: argparse.Namespace) -> int:
    """Add or remove tags from a campaign."""
    try:
        store = KnowledgeStore(args.sqx_path)
        store.initialize()

        if args.remove:
            # Remove tags - we need to get current tags first, then update
            current_tags = store.get_tags(args.campaign_id)
            tags_to_remove = set(args.tags)
            new_tags = [t for t in current_tags if t not in tags_to_remove]
            # Re-tag with remaining tags
            indexer = store._indexer if hasattr(store, '_indexer') else None
            if not indexer:
                from quantlab.knowledge.indexer import Indexer
                indexer = Indexer(store)
            # Clear all tags and re-add
            index = store.read_index()
            for dir_name in ["results", "campaigns"]:
                for rel_path, info in index.get("directories", {}).get(dir_name, {}).items():
                    if Path(rel_path).stem == args.campaign_id:
                        info["tags"] = new_tags
                        store._write_index(index)
                        print_human(f"Removed tags {args.tags} from campaign {args.campaign_id}")
                        print_human(f"Remaining tags: {new_tags}")
                        return 0
            print_error(f"Campaign not found: {args.campaign_id}")
            return 1
        else:
            # Add tags
            success = store.tag(args.campaign_id, args.tags)
            if success:
                print_human(f"Added tags to campaign {args.campaign_id}: {', '.join(args.tags)}")
                return 0
            else:
                print_error(f"Campaign not found: {args.campaign_id}")
                return 1

    except Exception as e:
        print_error(f"Tag operation failed: {e}")
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Knowledge Link Command
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_knowledge_link(args: argparse.Namespace) -> int:
    """Link campaigns as parent/child relationships."""
    try:
        store = KnowledgeStore(args.sqx_path)
        store.initialize()

        if args.list:
            # List links for a campaign
            links = store.get_links(args.campaign_id)
            if args.json:
                print_json(links)
            else:
                print_human(f"Links for campaign {args.campaign_id}:")
                if links["parents"]:
                    print_human("  Parents: " + ", ".join(links["parents"]))
                if links["children"]:
                    print_human("  Children: " + ", ".join(links["children"]))
                if not links["parents"] and not links["children"]:
                    print_human("  No links found")
            return 0
        elif args.parent and args.children:
            # Create parent-child links
            success = store.link(args.parent, args.children)
            if success:
                print_human(f"Linked parent '{args.parent}' to children: {', '.join(args.children)}")
                return 0
            else:
                print_error(f"Parent campaign not found: {args.parent}")
                return 1
        else:
            print_error("Either --list or both --parent and --children required")
            return 1

    except Exception as e:
        print_error(f"Link operation failed: {e}")
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Knowledge Export Command
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_knowledge_export(args: argparse.Namespace) -> int:
    """Export query results to CSV or JSON."""
    try:
        store = KnowledgeStore(args.sqx_path)
        store.initialize()
        index = store.read_index()

        builder = QueryBuilder(index, Path(args.sqx_path))

        # Apply same filters as query command
        if args.sharpe:
            op, val = args.sharpe[0], float(args.sharpe[1:])
            if op == '>':
                builder.filter_by_sharpe(min_val=val)
            elif op == '<':
                builder.filter_by_sharpe(max_val=val)
        if args.profit_factor:
            op, val = args.profit_factor[0], float(args.profit_factor[1:])
            if op == '>':
                builder.filter_by_profit_factor(min_val=val)
        if args.win_rate:
            op, val = args.win_rate[0], float(args.win_rate[1:])
            if op == '>':
                builder.filter_by_win_rate(min_val=val)
        if args.max_drawdown:
            op, val = args.max_drawdown[0], float(args.max_drawdown[1:])
            if op == '<':
                builder.filter_by_max_drawdown(max_val=val)
        if args.tags:
            builder.filter_by_tags(args.tags)
        if args.date:
            parts = args.date.split('..')
            if len(parts) == 2:
                builder.filter_by_date(parts[0] if parts[0] else None, parts[1] if parts[1] else None)
        if args.text:
            builder.search_text(args.text)
        if args.sort:
            builder.sort_by(args.sort, not args.desc)
        if args.limit:
            builder.limit(args.limit)
        if args.offset:
            builder.offset(args.offset)

        result = builder.execute()

        # Prepare data for export
        export_data = []
        for c in result.campaigns:
            export_data.append({
                "campaign_id": c.campaign_id,
                "name": c.name,
                "sharpe_ratio": c.metrics.sharpe_ratio if c.metrics else None,
                "profit_factor": c.metrics.profit_factor if c.metrics else None,
                "win_rate": c.metrics.win_rate if c.metrics else None,
                "max_drawdown": c.metrics.max_drawdown if c.metrics else None,
                "total_trades": c.metrics.total_trades if c.metrics else None,
                "net_profit": c.metrics.net_profit if c.metrics else None,
                "tags": ", ".join(c.tags) if c.tags else "",
                "created": c.created.isoformat() if c.created else "",
                "path": str(c.path) if c.path else "",
            })

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if args.format == "csv":
            if export_data:
                with open(output_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=export_data[0].keys())
                    writer.writeheader()
                    writer.writerows(export_data)
            else:
                # Empty CSV with headers
                with open(output_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["campaign_id", "name", "sharpe_ratio", "profit_factor", "win_rate", "max_drawdown", "total_trades", "net_profit", "tags", "created", "path"])
                    writer.writeheader()
            print_human(f"Exported {len(export_data)} campaigns to {output_path} (CSV)")
        else:  # json
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)
            print_human(f"Exported {len(export_data)} campaigns to {output_path} (JSON)")

        return 0

    except Exception as e:
        print_error(f"Export failed: {e}")
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Subparser Registration
# ──────────────────────────────────────────────────────────────────────────────

def add_knowledge_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add knowledge subcommands to main parser."""
    p_knowledge = subparsers.add_parser("knowledge", help="Knowledge Lake query and management")
    knowledge_sub = p_knowledge.add_subparsers(dest="knowledge_cmd", required=True)

    def _add_common_args(parser: argparse.ArgumentParser) -> None:
        """Add common arguments shared by all subcommands."""
        parser.add_argument(
            "--sqx-path",
            default="/opt/StrategyQuantX",
            help="Path to SQX installation (default: /opt/StrategyQuantX)",
        )
        parser.add_argument(
            "--knowledge-root",
            default="knowledge",
            help="Path to Knowledge Lake root (default: knowledge)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8888,
            help="SQX -gui port (default: 8888)",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output JSON instead of human-readable text",
        )

    # ── knowledge query ─────────────────────────────────────────────────────
    p_kw_query = knowledge_sub.add_parser("query", help="Query Knowledge Lake campaigns")
    _add_common_args(p_kw_query)
    p_kw_query.add_argument("--sharpe", help="Sharpe ratio filter (e.g., '>1.5', '<2.0')")
    p_kw_query.add_argument("--pf", dest="profit_factor", help="Profit factor filter (e.g., '>1.2')")
    p_kw_query.add_argument("--win-rate", help="Win rate filter (e.g., '>0.5')")
    p_kw_query.add_argument("--dd", dest="max_drawdown", help="Max drawdown filter (e.g., '<10')")
    p_kw_query.add_argument("--tags", nargs="+", help="Tag filters (AND logic)")
    p_kw_query.add_argument("--date", help="Date range filter (e.g., '2024-01-01..2024-12-31')")
    p_kw_query.add_argument("--text", help="Full-text search")
    p_kw_query.add_argument("--sort", choices=["created", "sharpe", "pf", "win_rate", "dd"], default="created")
    p_kw_query.add_argument("--desc", action="store_true", default=True, help="Sort descending")
    p_kw_query.add_argument("--limit", type=int, default=50)
    p_kw_query.add_argument("--offset", type=int, default=0)
    p_kw_query.set_defaults(func=cmd_knowledge_query)

    # ── knowledge tag ───────────────────────────────────────────────────────
    p_kw_tag = knowledge_sub.add_parser("tag", help="Add or remove tags from a campaign")
    _add_common_args(p_kw_tag)
    p_kw_tag.add_argument("campaign_id", help="Campaign ID")
    p_kw_tag.add_argument("tags", nargs="+", help="Tags to add/remove")
    p_kw_tag.add_argument("--remove", action="store_true", help="Remove tags instead of adding")
    p_kw_tag.set_defaults(func=cmd_knowledge_tag)

    # ── knowledge link ──────────────────────────────────────────────────────
    p_kw_link = knowledge_sub.add_parser("link", help="Link campaigns as parent/child")
    _add_common_args(p_kw_link)
    p_kw_link.add_argument("--list", action="store_true", help="List links for a campaign")
    p_kw_link.add_argument("--parent", help="Parent campaign ID")
    p_kw_link.add_argument("--children", nargs="+", help="Child campaign IDs")
    p_kw_link.add_argument("campaign_id", nargs="?", help="Campaign ID (for --list)")
    p_kw_link.set_defaults(func=cmd_knowledge_link)

    # ── knowledge export ────────────────────────────────────────────────────
    p_kw_export = knowledge_sub.add_parser("export", help="Export query results to CSV/JSON")
    _add_common_args(p_kw_export)
    p_kw_export.add_argument("--sharpe", help="Sharpe ratio filter (e.g., '>1.5')")
    p_kw_export.add_argument("--pf", dest="profit_factor", help="Profit factor filter (e.g., '>1.2')")
    p_kw_export.add_argument("--win-rate", help="Win rate filter (e.g., '>0.5')")
    p_kw_export.add_argument("--dd", dest="max_drawdown", help="Max drawdown filter (e.g., '<10')")
    p_kw_export.add_argument("--tags", nargs="+", help="Tag filters (AND logic)")
    p_kw_export.add_argument("--date", help="Date range filter (e.g., '2024-01-01..2024-12-31')")
    p_kw_export.add_argument("--text", help="Full-text search")
    p_kw_export.add_argument("--sort", choices=["created", "sharpe", "pf", "win_rate", "dd"], default="created")
    p_kw_export.add_argument("--desc", action="store_true", default=True, help="Sort descending")
    p_kw_export.add_argument("--limit", type=int, default=50)
    p_kw_export.add_argument("--offset", type=int, default=0)
    p_kw_export.add_argument("--format", choices=["csv", "json"], default="csv", help="Export format")
    p_kw_export.add_argument("--output", "-o", required=True, help="Output file path")
    p_kw_export.set_defaults(func=cmd_knowledge_export)