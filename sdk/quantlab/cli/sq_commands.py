"""SQX KB CLI commands — ``quantlab sqx kb`` (REQ-207) + ``sqx check-version`` (REQ-304).

Subcommands: ``list [--tab] [--status]``, ``get {tab}/{param}``,
``seed [--doc]`` (full flow + REQ-209 gate), ``validate`` (gate re-check),
``verify {tab}/{param} --evidence-ref``, ``status``, ``check-version``.

Exit contract: 0 on success; 1 with a "not found" message for unknown
parameters (REQ-207 scenario), and 1 on any operational failure or when the
REQ-209 gate fails (REQ-209 scenarios). ``check-version`` exits 0 in-sync,
1 drift, 0 unknown (fail-open).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quantlab.knowledge.kb.models import KB_TABS, SQX_VERSION
from quantlab.knowledge.kb.seeding_flow import (
    _default_evidence_base,
    run_seed_flow,
)
from quantlab.knowledge.kb.seeder import DEFAULT_DOC_PATH
from quantlab.knowledge.kb.educational import (
    build_educational_dataset,
    build_educational_table,
    parse_tpl_build,
)
from quantlab.knowledge.kb.store import KbParamNotFoundError, KbStore
from quantlab.knowledge.kb.validation import validate_seed

# Evidence-base derivation hook (D2). Tests monkeypatch this to point at a
# synthetic install tree; production derives the project root from the lake.
_DEFAULT_EVIDENCE_BASE_FACTORY = _default_evidence_base


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
    """Seed + verify + index + run the REQ-209 gate (REQ-203/REQ-209).

    ``seed`` is the FULL flow: parameters are seeded from the doc, bulk
    verified against the real install's ``.cfx`` evidence, leftover doc-only
    entries demoted to needs_review, the index rebuilt, and the REQ-209 gate
    run. Exit 0 only when every gate check passes (spec-faithful; no
    ``--no-gate`` escape hatch per design open question default).
    """
    try:
        store = _kb_store(args)
        evidence_base = _DEFAULT_EVIDENCE_BASE_FACTORY(args.knowledge_root)
        result = run_seed_flow(
            store,
            doc_path=args.doc,
            sqx_version=args.sqx_version,
            evidence_base=evidence_base,
        )
        if result.total == 0:
            print_error(f"Seed failed: document not found or unreadable: {args.doc}")
            return 1
        print_human(
            f"Seeded {result.total} parameter(s) into sqx-kb/{args.sqx_version}: "
            f"{result.verified} verified, {result.needs_review} needs_review"
        )
        _print_gate_report(result.report)
        return 0 if result.ok else 1
    except Exception as e:  # pragma: no cover - defensive
        print_error(f"KB seed failed: {e}")
        return 1


def _print_gate_report(report: object) -> None:
    """Print the REQ-209 gate report in a compact, operator-readable form."""
    checks = getattr(report, "checks", {})
    errors = getattr(report, "errors", [])
    counts = getattr(report, "counts", {})
    if counts:
        print_human(
            f"Gate counts: total {counts.get('total')}, "
            f"verified {counts.get('verified')}, "
            f"needs_review {counts.get('needs_review')}, "
            f"seeded {counts.get('seeded')}"
        )
    for name, ok in checks.items():
        print_human(f"  [{('PASS' if ok else 'FAIL')}] {name}")
    for err in errors:
        print_error(f"  {err}")


async def cmd_kb_validate(args: argparse.Namespace) -> int:
    """Run the REQ-209 gate against an existing seed (idempotent re-check)."""
    try:
        report = validate_seed(args.knowledge_root, sqx_version=args.sqx_version)
        _print_gate_report(report)
        if not report.checks.get("schema", False):
            print_error("KB validate failed: schema violations present")
            return 1
        return 0 if report.ok else 1
    except Exception as e:  # pragma: no cover - defensive
        print_error(f"KB validate failed: {e}")
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


# ── builder template path: real install templates dir, on the lake root's
# project. CLI default: repo `assets/SQX_*/.../tpl_build.xml`; tests
# monkeypatch this factory.
_DEFAULT_TPL_PATH_FACTORY = lambda knowledge_root: Path(  # noqa: E731
    knowledge_root
).parent / "assets" / "SQX_144_2953_linux_20260601" / "internal" / "web" / "BUILDER" / "templates" / "tpl_build.xml"


async def cmd_kb_table(args: argparse.Namespace) -> int:
    """Generate the educational table + shared dataset (parameter-educational-table).

    Reads the seeded KB for ``--sqx-version``, cross-references the real
    ``tpl_build.xml`` template, emits ``educational-table.md`` and
    ``educational-dataset.yaml`` under
    ``structured/sqx-kb/{ver}/educational/`` (conformance writer
    ``educational_generator``), and prints a summary. Exit 0 on success.
    """
    try:
        store = _kb_store(args)
        params = store.list(sqx_version=args.sqx_version)
        if args.tpl:
            tpl_path = Path(args.tpl)
        else:
            tpl_path = _DEFAULT_TPL_PATH_FACTORY(store.root)
        if not tpl_path.exists():
            print_error(f"Template not found: {tpl_path}")
            return 1
        tpl = parse_tpl_build(tpl_path)
        records = build_educational_dataset(params, tpl=tpl)
        table = build_educational_table(records)

        import yaml

        edu_dir = (
            store.root
            / "structured"
            / "sqx-kb"
            / args.sqx_version
            / "educational"
        )
        edu_dir.mkdir(parents=True, exist_ok=True)
        dataset_path = edu_dir / "educational-dataset.yaml"
        table_path = edu_dir / "educational-table.md"

        dataset_path.write_text(
            yaml.safe_dump(
                [r.model_dump() for r in records],
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        table_path.write_text(table + "\n", encoding="utf-8")
        print_human(
            f"Educational table generated: {len(records)} parameter(s) → "
            f"{table_path} + {dataset_path}"
        )
        return 0
    except Exception as e:  # pragma: no cover - defensive
        print_error(f"KB table failed: {e}")
        return 1


async def cmd_sqx_check_version(args: argparse.Namespace) -> int:
    """Print installed build vs pinned build and status (REQ-304).

    Exit contract: 0 in-sync, 1 drift, 0 unknown (fail-open — an
    undetectable build must not block automation). Drift detection also
    persists the migration checklist and invalidates the old KB version
    (REQ-305), mirroring the dispatch pre-flight hook (REQ-701).
    """
    try:
        from quantlab.cli.main import DEFAULT_SQX_PATH
        from quantlab.cli.runner import RealExecutor
        from quantlab.sqx.cli_wrapper import _find_sqcli
        from quantlab.versioning import PINNED_SQX_VERSION, VersionPreflight

        sqx_path = args.sqx_path or DEFAULT_SQX_PATH
        binary = _find_sqcli(sqx_path)
        preflight = VersionPreflight(
            executor=None if binary is None else RealExecutor(binary),
            knowledge_root=args.knowledge_root,
        )
        status = preflight.run()
        print_human(f"SQX version: {preflight.installed_build or 'unknown'}")
        print_human(f"Pinned: {PINNED_SQX_VERSION}")
        print_human(f"Status: {status}")
        if status == "in-sync":
            return 0
        if status == "drift":
            return 1
        return 0  # unknown — fail-open
    except Exception as e:  # pragma: no cover - defensive
        print_error(f"check-version failed: {e}")
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

    # ── sqx kb validate ─────────────────────────────────────────────────────
    p_validate = kb_sub.add_parser(
        "validate", help="Run the REQ-209 gate against the seeded KB"
    )
    _add_common(p_validate)
    p_validate.set_defaults(func=cmd_kb_validate)

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

    # ── sqx kb table ─────────────────────────────────────────────────────────
    p_table = kb_sub.add_parser(
        "table",
        help="Generate the educational table + shared dataset from the seeded KB",
    )
    _add_common(p_table)
    p_table.add_argument(
        "--tpl",
        default=None,
        help=(
            "Path to SQX tpl_build.xml (default: assets/SQX_144_2953_linux_20260601/"
            "internal/web/BUILDER/templates/tpl_build.xml)"
        ),
    )
    p_table.set_defaults(func=cmd_kb_table)

    # ── sqx check-version ────────────────────────────────────────────────────
    p_check = sqx_sub.add_parser(
        "check-version", help="Print installed SQX build vs pinned (REQ-304)"
    )
    p_check.add_argument(
        "--sqx-path",
        default=None,
        help="Path to SQX installation (default: %(default)s → CLI default)",
    )
    p_check.add_argument(
        "--knowledge-root",
        default="knowledge",
        help="Knowledge Lake root for the drift checklist (default: knowledge)",
    )
    p_check.set_defaults(func=cmd_sqx_check_version)
