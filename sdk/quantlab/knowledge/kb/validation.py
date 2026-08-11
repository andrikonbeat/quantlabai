"""REQ-209 seed-validation gate (D3, D1).

``validate_seed`` is a PURE, read-only gate: it loads every seeded YAML
against the REQ-201 schema, checks the Knowledge Lake index carries full
``kb_parameters`` coverage for the pinned version (REQ-403), verifies
evidence consistency (REQ-209), and checks the status distribution matches
the frozen seeding band. ``needs_review`` within the quota is an accepted
terminal state and MUST NOT fail the gate (REQ-209 scenario 2).

The distribution band was frozen from the first real seed run (T-1.5):
total == 82; verified in [71, 77]; needs_review in [5, 11];
verified + needs_review == total. These constants are the single source of
truth for the gate; adjust them only when the seed composition changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.seeder import iter_seed_entries
from quantlab.knowledge.store import KnowledgeStore

# ── Frozen seeding band (T-1.5 empirical freeze) ─────────────────────────────
# First real seed of 144.2953 produced 74 verified + 8 needs_review = 82.
# Band keeps a ±3 drift window so doc/config edits don't flake the gate while
# still failing real regressions. needs_review is SUCCESS within the band.
SEED_TOTAL: int = len(list(iter_seed_entries()))  # 82 (77 SEED_SPEC + 5 GAP_SPEC)
VERIFIED_MIN: int = 71
VERIFIED_MAX: int = 77
NEEDS_REVIEW_MIN: int = 5
NEEDS_REVIEW_MAX: int = 11


@dataclass
class SeedValidationReport:
    """REQ-209 gate output: per-check status, errors, and counts."""

    checks: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True when every check passes."""
        return all(self.checks.values())


def _iter_param_files(lake_root: Path, sqx_version: str) -> list[Path]:
    """All seeded YAMLs for a version (glob, never skips corrupt files)."""
    version_dir = lake_root / "structured" / "sqx-kb" / sqx_version / "parameters"
    if not version_dir.is_dir():
        return []
    return sorted(version_dir.rglob("*.yaml"))


def _resolve_evidence(ref: str, lake_root: Path) -> Path | None:
    """Resolve an ``evidence_ref`` to a real file, stripping ``#anchor``.

    Absolute refs are used as-is. Relative refs use the project-root
    convention (the lake root's parent holds ``assets/`` for the pinned
    install) and fall back to the lake root itself.
    """
    path = ref.split("#", 1)[0]
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    for base in (lake_root.parent, lake_root):
        resolved = base / candidate
        if resolved.is_file():
            return resolved
    return None


def _check_schema(
    files: list[Path], errors: list[str]
) -> tuple[list[KbParameter], int]:
    """Load every YAML against REQ-201; errors name param + offending field."""
    params: list[KbParameter] = []
    for path in files:
        try:
            params.append(
                KbParameter.from_yaml(path.read_text(encoding="utf-8"))
            )
        except Exception as exc:  # noqa: BLE001 - report any schema failure
            errors.append(
                f"Schema violation: {path.parent.name}/{path.stem}: {exc}"
            )
    return params, len(files)


def _count_index_coverage(lake_root: Path, sqx_version: str) -> int:
    """Number of kb_parameters index entries for the version (REQ-403)."""
    index = KnowledgeStore(lake_root).read_index()
    coverage = index.get("kb_parameters", {})
    return sum(
        1
        for info in coverage.values()
        if isinstance(info, dict) and info.get("sqx_version") == sqx_version
    )


def _check_evidence(
    params: list[KbParameter], lake_root: Path, errors: list[str]
) -> bool:
    """Non-empty evidence_ref everywhere; verified refs must resolve.

    ``needs_review`` entries carry best-effort doc anchors — they are
    explicitly not confirmed (REQ-209 scenario 2) and their refs are NOT
    required to exist (the doc may be untracked in CI).
    """
    ok = True
    for param in params:
        if not param.evidence_ref:
            errors.append(
                f"Missing evidence_ref: {param.tab}/{param.name}"
            )
            ok = False
            continue
        if param.status == "verified" and not _resolve_evidence(
            param.evidence_ref, lake_root
        ):
            errors.append(
                f"Dangling evidence_ref: {param.tab}/{param.name} -> "
                f"{param.evidence_ref}"
            )
            ok = False
    return ok


def _check_distribution(
    counts: dict[str, int], errors: list[str]
) -> bool:
    """Frozen band: total==82; verified/needs_review within range; sum==total."""
    ok = True
    total, verified, needs_review, seeded = (
        counts["total"],
        counts["verified"],
        counts["needs_review"],
        counts["seeded"],
    )
    if total != SEED_TOTAL:
        errors.append(
            f"Distribution: total={total}, expected {SEED_TOTAL}"
        )
        ok = False
    if not (VERIFIED_MIN <= verified <= VERIFIED_MAX):
        errors.append(
            f"Distribution: verified={verified}, expected "
            f"[{VERIFIED_MIN}, {VERIFIED_MAX}]"
        )
        ok = False
    if not (NEEDS_REVIEW_MIN <= needs_review <= NEEDS_REVIEW_MAX):
        errors.append(
            f"Distribution: needs_review={needs_review}, expected "
            f"[{NEEDS_REVIEW_MIN}, {NEEDS_REVIEW_MAX}]"
        )
        ok = False
    if verified + needs_review != total:
        errors.append(
            f"Distribution: verified({verified}) + needs_review({needs_review}) "
            f"!= total({total}) — {seeded} leftover seeded entries not resolved"
        )
        ok = False
    return ok


def validate_seed(
    lake_root: str | Path, sqx_version: str = "144.2953"
) -> SeedValidationReport:
    """Validate a seeded KB slice against the REQ-209 gate (read-only).

    Args:
        lake_root: Knowledge Lake root (e.g. ``knowledge``).
        sqx_version: version bucket to validate (default: pinned 144.2953).

    Returns:
        SeedValidationReport with ``checks``, ``errors`` and ``counts``.
        ``report.ok`` is False when any check fails.
    """
    root = Path(lake_root).resolve()
    errors: list[str] = []
    checks: dict[str, bool] = {}

    files = _iter_param_files(root, sqx_version)
    params, total = _check_schema(files, errors)
    checks["schema"] = not any(e.startswith("Schema violation") for e in errors)

    counts = {
        "total": total,
        "verified": sum(1 for p in params if p.status == "verified"),
        "needs_review": sum(1 for p in params if p.status == "needs_review"),
        "seeded": sum(1 for p in params if p.status == "seeded"),
    }

    covered = _count_index_coverage(root, sqx_version)
    coverage_ok = covered == total
    if not coverage_ok:
        errors.append(
            f"Index coverage: kb_parameters for {sqx_version} covers "
            f"{covered}/{total} entries, expected {total}"
        )
    checks["index_coverage"] = coverage_ok

    checks["evidence"] = _check_evidence(params, root, errors)
    checks["distribution"] = _check_distribution(counts, errors)

    return SeedValidationReport(checks=checks, errors=errors, counts=counts)


__all__ = [
    "SEED_TOTAL",
    "VERIFIED_MIN",
    "VERIFIED_MAX",
    "NEEDS_REVIEW_MIN",
    "NEEDS_REVIEW_MAX",
    "SeedValidationReport",
    "validate_seed",
]