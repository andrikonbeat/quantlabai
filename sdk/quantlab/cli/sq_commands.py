"""SQX KB CLI commands — ``quantlab sqx kb`` (REQ-207).

Subcommands: ``list [--tab] [--status]``, ``get {tab}/{param}``,
``seed [--doc]``, ``verify {tab}/{param} --evidence-ref``, ``status``.

Exit contract: 0 on success; 1 with a "not found" message for unknown
parameters (REQ-207 scenario), and 1 on any operational failure.
"""

from __future__ import annotations

import argparse
import sys

from quantlab.knowledge.kb.models import KB_TABS, SQX_VERSION
from quantlab.knowledge.kb.seeder import DEFAULT_DOC_PATH, seed_from_doc
from quantlab.knowledge.kb.store import KbParamNotFoundError, KbStore


def print_human(message: str, *, error: bool = False) -> None:
    if error:
        print(message, file=sys.stderr)
    else:
        print(message)


def print_error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a simple aligned table."""
    if not rows:
        return
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    print("  ".join(h.ljust(w) for h, w in zip(headers, col_widths)))
    print("  ".join("-" * w for w in col_widths))
    for row in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(row, col_widths)))


def _kb_store(args: argparse.Namespace) -> KbStore:
    store = KbStore(root=args.knowledge_root)
    store.initialize()
    return store


def _split_target(target: str) -> tuple[str, str] | None:
    """Split ``tab/param``; None when the target has no tab separator."""
    if "/" not in target:
        return None
    tab, _, param = target.partition("/")
    return tab.strip(), param.strip()


# ──────────────────────────────────────────────────────────────────────────────
# Handlers
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_kb_list(args: argparse.Namespace) -> int:
    """List KB parameters with optional tab/status filters."""
    try:
        store = _kb_store(args)
        params = store.list(tab=args.tab, status=args.status, sqx_version=args.sqx_version)
        scope = f"sqx-kb/{args.sqx_version}"
        if args.tab:
            scope += f" tab={args.tab}"
        if args.status:
            scope += f" status={args.status}"
        print_human(f"{len(params)} parameter(s) in {scope}")
        rows = [
            [p.name, p.tab, p.status, p.evidence_ref or ""]
            for p in params
        ]
        print_table(["Parameter", "Tab", "Status", "Evidence"], rows)
        return 0
    except Exception as e:  # pragma: no cover - defensive
        print_error(f"KB list failed: {e}")
        return 1


async def cmd_kb_get(args: argparse.Namespace) -> int:
    """Print a single parameter's full YAML (REQ-207 get scenario)."""
    target = _split_target(args.target)
    if target is None:
        print_error(f"Parameter not found: {args.target}")
        return 1
    tab, param = target
    try:
        store = _kb_store(args)
        entry = store.get(tab, param, sqx_version=args.sqx_version)
        print(entry.to_yaml().rstrip())
        return 0
    except KbParamNotFoundError as e:
        print_error(str(e))
        return 1
    except Exception as e:  # pragma: no cover - defensive
        print_error(f"KB get failed: {e}")
        return 1


async def cmd_kb_seed(args: argparse.Namespace) -> int:
    """Seed the KB from doc_dev/SQX Builder Config.md (REQ-203)."""
    try:
        store = _kb_store(args)
        result = seed_from_doc(store, doc_path=args.doc, sqx_version=args.sqx_version)
        if result.total == 0:
            print_error(f"Seed failed: document not found or unreadable: {args.doc}")
            return 1
        print_human(
            f"Seeded {result.seeded} parameter(s) "
            f"({result.needs_review} needs_review) from {args.doc} "
            f"into sqx-kb/{args.sqx_version}"
        )
        return 0
    except Exception as e:  # pragma: no cover - defensive
        print_error(f"KB seed failed: {e}")
        return 1


async def cmd_kb_verify(args: argparse.Namespace) -> int:
    """Verify a parameter against real config evidence (REQ-203)."""
    target = _split_target(args.target)
    if target is None:
        print_error(f"Parameter not found: {args.target}")
        return 1
    tab, param = target
    try:
        store = _kb_store(args)
        entry = store.verify(
            tab, param, evidence_ref=args.evidence_ref, sqx_version=args.sqx_version
        )
        print_human(f"Verified {entry.name} ({entry.tab}) — evidence: {entry.evidence_ref}")
        return 0
    except KbParamNotFoundError as e:
        print_error(str(e))
        return 1
    except Exception as e:  # pragma: no cover - defensive
        print_error(f"KB verify failed: {e}")
        return 1


async def cmd_kb_status(args: argparse.Namespace) -> int:
    """Show KB status counts by status and tab."""
    try:
        store = _kb_store(args)
        summary = store.status(sqx_version=args.sqx_version)
        print_human(
            f"sqx-kb/{summary['sqx_version']}: {summary['total']} parameter(s) — "
            f"seeded {summary['seeded']}, verified {summary['verified']}, "
            f"needs_review {summary['needs_review']}"
        )
        for tab, stats in summary["tabs"].items():  # type: ignore[union-attr]
            print_human(
                f"  {tab}: {stats['total']} (seeded {stats['seeded']}, "
                f"verified {stats['verified']}, needs_review {stats['needs_review']})"
            )
        return 0
    except Exception as e:  # pragma: no cover - defensive
        print_error(f"KB status failed: {e}")
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# Subparser registration
# ──────────────────────────────────────────────────────────────────────────────


def add_sqx_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add the ``sqx`` command group (``sqx kb ...``) to the main parser."""
    p_sqx = subparsers.add_parser("sqx", help="SQX parameter knowledge base (KB)")
    sqx_sub = p_sqx.add_subparsers(dest="sqx_cmd", required=True)

    p_kb = sqx_sub.add_parser("kb", help="SQX parameter knowledge base")
    kb_sub = p_kb.add_subparsers(dest="kb_cmd", required=True)

    def _add_common(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--knowledge-root",
            default="knowledge",
            help="Path to Knowledge Lake root (default: knowledge)",
        )
        parser.add_argument(
            "--sqx-version",
            default=SQX_VERSION,
            help=f"SQX version bucket (default: {SQX_VERSION})",
        )

    # ── sqx kb list ──────────────────────────────────────────────────────────
    p_list = kb_sub.add_parser("list", help="List KB parameters")
    _add_common(p_list)
    p_list.add_argument("--tab", choices=KB_TABS, help="Filter by tab")
    p_list.add_argument(
        "--status",
        choices=["seeded", "verified", "needs_review"],
        help="Filter by status",
    )
    p_list.set_defaults(func=cmd_kb_list)

    # ── sqx kb get ───────────────────────────────────────────────────────────
    p_get = kb_sub.add_parser("get", help="Print one parameter's full YAML")
    _add_common(p_get)
    p_get.add_argument(
        "target",
        help="Parameter path, e.g. 'Trading options/Maximum Trades Per Day'",
    )
    p_get.set_defaults(func=cmd_kb_get)

    # ── sqx kb seed ──────────────────────────────────────────────────────────
    p_seed = kb_sub.add_parser("seed", help="Seed KB from the SQX Builder Config doc")
    _add_common(p_seed)
    p_seed.add_argument(
        "--doc",
        default=DEFAULT_DOC_PATH,
        help="Path to the SQX Builder Config doc (default: doc_dev/SQX Builder Config.md)",
    )
    p_seed.set_defaults(func=cmd_kb_seed)

    # ── sqx kb verify ────────────────────────────────────────────────────────
    p_verify = kb_sub.add_parser(
        "verify", help="Verify a parameter against real config evidence"
    )
    _add_common(p_verify)
    p_verify.add_argument(
        "target",
        help="Parameter path, e.g. 'Trading options/Stop Loss'",
    )
    p_verify.add_argument(
        "--evidence-ref",
        required=True,
        help="Evidence reference (e.g. path to the real .cfx config)",
    )
    p_verify.set_defaults(func=cmd_kb_verify)

    # ── sqx kb status ────────────────────────────────────────────────────────
    p_status = kb_sub.add_parser("status", help="Show KB status counts")
    _add_common(p_status)
    p_status.set_defaults(func=cmd_kb_status)
