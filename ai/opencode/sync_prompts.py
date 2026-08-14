#!/usr/bin/env python3
"""Deterministic, idempotent sync of repo-canonical QuantLab prompts to live.

REQ-806: the repo directory ``ai/opencode/agents/`` is the single source of
truth for the campaign prompt and all phase prompts. The live copies under
``~/.config/opencode/prompts/quantlab/`` are generated from it by this
script; hand-editing live prompts is not permitted.

Managed allowlist (sorted, deterministic): ``campaign.md`` + ``phase-*.md``.
Non-managed live files (``deploy.md``, ``guardian.md``, ``monitor.md``,
``orchestrator.md``, ...) are NEVER written or deleted by this script.

Usage::

    python3 ai/opencode/sync_prompts.py             # copy repo -> live
    python3 ai/opencode/sync_prompts.py --dry-run   # report, write nothing
    python3 ai/opencode/sync_prompts.py --check     # exit 1 on any drift

Idempotent: identical bytes are never rewritten; a second run is a no-op.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent / "agents"
LIVE_DIR = Path.home() / ".config" / "opencode" / "prompts" / "quantlab"

# Sorted allowlist: campaign.md + phase-*.md. Anything else under the agents
# dir (or the live dir) is non-managed and must stay untouched.
MANAGED_NAMES = ("campaign.md",)


def managed_prompt_names(repo_dir: Path = REPO_DIR) -> list[str]:
    """Sorted allowlist of managed prompt filenames present in the repo.

    Always includes ``campaign.md`` plus every ``phase-*.md`` file found.
    Sorted for determinism regardless of filesystem order.
    """
    names = {MANAGED_NAMES[0]}
    names.update(p.name for p in repo_dir.glob("phase-*.md") if p.is_file())
    return sorted(names)


def read_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def sync(repo_dir: Path = REPO_DIR, live_dir: Path = LIVE_DIR, *, dry_run: bool = False) -> list[str]:
    """Copy managed prompts from repo to live, byte-for-byte.

    Returns the sorted list of managed names that were (or, with
    ``dry_run=True``, would be) written. Idempotent: a name whose live bytes
    already equal the repo bytes is skipped and not listed. Never touches
    non-managed files.
    """
    live_dir.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for name in managed_prompt_names(repo_dir):
        src = repo_dir / name
        dst = live_dir / name
        if not src.is_file():
            continue  # allowlist entry absent in repo: nothing to sync
        if read_bytes(dst) == src.read_bytes():
            continue  # identical bytes -> no-op
        changed.append(name)
        if not dry_run:
            shutil.copyfile(src, dst)
    return changed


def check(repo_dir: Path = REPO_DIR, live_dir: Path = LIVE_DIR) -> list[str]:
    """Return sorted managed names whose live copy differs from the repo.

    Empty list means parity holds byte-for-byte.
    """
    drifted: list[str] = []
    for name in managed_prompt_names(repo_dir):
        src = repo_dir / name
        dst = live_dir / name
        if not src.is_file():
            continue
        if read_bytes(dst) != src.read_bytes():
            drifted.append(name)
    return drifted


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync_prompts",
        description=__doc__.split("Usage::", 1)[0],
    )
    parser.add_argument(
        "--repo", type=Path, default=REPO_DIR, help="repo agents dir (default: %(default)s)"
    )
    parser.add_argument(
        "--live", type=Path, default=LIVE_DIR, help="live prompts dir (default: %(default)s)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    mode.add_argument("--check", action="store_true", help="exit 1 if any managed file drifted")
    args = parser.parse_args(argv)

    if args.check:
        drifted = check(args.repo, args.live)
        if drifted:
            print(f"DRIFT ({len(drifted)}): " + ", ".join(drifted))
            return 1
        print("parity ok")
        return 0

    changed = sync(args.repo, args.live, dry_run=args.dry_run)
    if changed:
        verb = "would update" if args.dry_run else "updated"
        print(f"{verb} ({len(changed)}): " + ", ".join(changed))
    else:
        print("already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(_main())