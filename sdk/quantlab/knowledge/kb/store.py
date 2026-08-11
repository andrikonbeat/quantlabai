"""SQX Parameter KB store (REQ-202, REQ-208, REQ-502, D7).

``KbStore`` persists ``KbParameter`` entries as YAML under
``structured/sqx-kb/{sqx_version}/parameters/{tab}/{param}.yaml`` inside a
Knowledge Lake. Version isolation is enforced by the layout itself: each
SQX version owns a separate directory tree.

Query surface (REQ-502)::

    get_parameter(tab, param, sqx_version=None) -> KbParameter
    list_parameters(tab=None, status=None, sqx_version=None) -> list[KbParameter]

Lifecycle: ``seed`` (write from doc) → ``verify`` (promote with real-config
evidence_ref) → ``invalidate`` (drift hook marks an entire version
needs_review, REQ-208).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from quantlab.knowledge.kb.models import KbParameter, SQX_VERSION
from quantlab.knowledge.store import KnowledgeStore


class KbParamNotFoundError(KeyError):
    """Raised when a parameter does not exist for the requested version."""


def _format_param_path(tab: str, param: str) -> str:
    return f"{tab}/{param}"


def _safe_param_filename(param: str) -> str:
    """Make a parameter name safe as a single file name.

    Some SEED_SPEC names contain ``/`` (e.g. "Stop/Limit entry blocks",
    "Minimum / Maximum SL", "Opt. Profile / Sys. Param. Permutation").
    Naive ``f"{param}.yaml"`` would create NESTED directories instead of
    one file, breaking the documented ``parameters/{tab}/{param}.yaml``
    layout. Slashes are replaced so the golden tree stays flat
    (REQ-202 layout contract); the YAML still carries the real name.
    """
    return param.replace("/", "_")


class KbStore:
    """Filesystem store for KB parameters over a Knowledge Lake."""

    def __init__(
        self,
        root: str | Path = "knowledge",
        store: KnowledgeStore | None = None,
    ) -> None:
        """Point at a Knowledge Lake root, optionally reusing a KnowledgeStore."""
        if store is not None:
            self.store = store
        else:
            self.store = KnowledgeStore(root)

    @property
    def root(self) -> Path:
        return self.store.root

    def initialize(self) -> None:
        """Ensure the Knowledge Lake skeleton exists (idempotent)."""
        self.store.initialize()

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _version_dir(self, sqx_version: str) -> Path:
        return self.root / "structured" / "sqx-kb" / sqx_version / "parameters"

    def _param_path(self, tab: str, param: str, sqx_version: str) -> Path:
        return (
            self._version_dir(sqx_version)
            / tab
            / f"{_safe_param_filename(param)}.yaml"
        )

    def _resolve_version(self, sqx_version: str | None) -> str:
        return sqx_version or SQX_VERSION

    def _load_file(self, path: Path) -> KbParameter:
        raw = path.read_text(encoding="utf-8")
        return KbParameter.from_yaml(raw)

    def _save_file(self, param: KbParameter) -> None:
        path = self._param_path(param.tab, param.name, param.sqx_version)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(param.to_yaml(), encoding="utf-8")

    # ── Reads (REQ-502) ───────────────────────────────────────────────────────

    def get(
        self, tab: str, param: str, sqx_version: str | None = None
    ) -> KbParameter:
        """Load a single parameter, enforcing version isolation.

        Raises:
            KbParamNotFoundError: if no YAML exists for this tab/name/version.
        """
        version = self._resolve_version(sqx_version)
        path = self._param_path(tab, param, version)
        if not path.is_file():
            raise KbParamNotFoundError(
                f"Parameter not found: {_format_param_path(tab, param)} "
                f"(sqx_version={version})"
            )
        return self._load_file(path)

    def list(
        self,
        tab: str | None = None,
        status: str | None = None,
        sqx_version: str | None = None,
    ) -> list[KbParameter]:
        """List parameters, optionally filtered by tab and/or status."""
        version = self._resolve_version(sqx_version)
        version_dir = self._version_dir(version)
        if not version_dir.is_dir():
            return []

        results: list[KbParameter] = []
        for param_file in sorted(version_dir.rglob("*.yaml")):
            rel = param_file.relative_to(version_dir)
            file_tab = rel.parts[0]
            if tab is not None and file_tab != tab:
                continue
            try:
                param = self._load_file(param_file)
            except Exception:
                continue  # Skip corrupted entries; filesystem is source of truth
            if status is not None and param.status != status:
                continue
            results.append(param)
        return results

    def consult(
        self,
        name: str,
        *,
        tab: str | None = None,
        status: str | None = None,
        sqx_version: str | None = None,
    ) -> list[dict[str, object]]:
        """Look up parameters by exact-or-fuzzy name (REQ-502 consumption hook).

        Used by agents (REQ-204) to consult the KB before configuring the
        builder: an exact name match returns a single-entry list carrying the
        guidance metadata; otherwise case-insensitive substring matches across
        parameter names are returned. ``tab`` (category) and ``status`` act as
        filters on every lookup.

        Args:
            name: Parameter name or fragment to look up.
            tab: Optional category filter (one of the 8 builder tabs).
            status: Optional status filter (seeded|verified|needs_review).
            sqx_version: Optional version bucket; defaults to the pinned one.

        Returns:
            List of metadata dicts with the guidance fields agents need
            (``what_it_does``, ``how_it_works_in_sqx``, ``quant_trading_role``,
            ``small_account_recommendation``, ``status``, ``evidence_ref``).
            Empty list when nothing matches — never raises, so a missing entry
            cleanly blocks configuration (REQ-204).
        """
        candidates = self.list(tab=tab, status=status, sqx_version=sqx_version)
        query = name.strip().lower()

        exact: KbParameter | None = None
        fuzzy: list[KbParameter] = []
        for param in candidates:
            if param.name.lower() == query or param.sqx_name.lower() == query:
                exact = param
                break  # Exact match wins; single entry.
            if query in param.name.lower() or query in param.sqx_name.lower():
                fuzzy.append(param)

        hits = [exact] if exact is not None else fuzzy
        return [self._consult_metadata(param) for param in hits]

    @staticmethod
    def _consult_metadata(param: KbParameter) -> dict[str, object]:
        """Project a parameter to the agent-facing guidance metadata (REQ-204)."""
        rec = param.small_account_recommendation
        return {
            "name": param.name,
            "sqx_name": param.sqx_name,
            "tab": param.tab,
            "section": param.section,
            "type": param.type,
            "default": param.default,
            "what_it_does": param.what_it_does,
            "how_it_works_in_sqx": param.how_it_works_in_sqx,
            "quant_trading_role": param.quant_trading_role,
            "small_account_recommendation": (
                rec.model_dump() if rec is not None else None
            ),
            "status": param.status,
            "evidence_ref": param.evidence_ref,
        }

    # ── Writes / lifecycle ────────────────────────────────────────────────────

    def seed(
        self,
        parameters: Sequence[KbParameter],
        sqx_version: str | None = None,
    ) -> int:
        """Persist parameters as YAML (REQ-203 seed step).

        Each parameter is written under its own ``sqx_version`` bucket. When
        ``sqx_version`` is given it overrides the bucket for every entry
        (useful when seeding a specific version from a doc).
        """
        count = 0
        for param in parameters:
            entry = param
            if sqx_version is not None and param.sqx_version != sqx_version:
                entry = param.model_copy(update={"sqx_version": sqx_version})
            self._save_file(entry)
            count += 1
        return count

    def verify(
        self,
        tab: str,
        param: str,
        evidence_ref: str,
        sqx_version: str | None = None,
    ) -> KbParameter:
        """Promote a parameter to ``verified`` with real-config evidence (REQ-203).

        Raises:
            KbParamNotFoundError: if the parameter does not exist yet.
        """
        version = self._resolve_version(sqx_version)
        path = self._param_path(tab, param, version)
        if not path.is_file():
            raise KbParamNotFoundError(
                f"Parameter not found: {_format_param_path(tab, param)} "
                f"(sqx_version={version})"
            )
        entry = self._load_file(path)
        entry.status = "verified"
        entry.evidence_ref = evidence_ref
        self._save_file(entry)
        return entry

    def invalidate(self, sqx_version: str) -> int:
        """Mark every parameter of a version ``needs_review`` (REQ-208).

        Called by the version-drift hook: after 144.2953 → 145.x, no old
        entry may be served as verified until re-verified.
        """
        version_dir = self._version_dir(sqx_version)
        if not version_dir.is_dir():
            return 0
        count = 0
        for path in version_dir.rglob("*.yaml"):
            try:
                entry = self._load_file(path)
            except Exception:
                continue
            entry.status = "needs_review"
            self._save_file(entry)
            count += 1
        return count

    def status(self, sqx_version: str | None = None) -> dict[str, object]:
        """Summary counts by status for a version (or the pinned version)."""
        version = self._resolve_version(sqx_version)
        entries = self.list(sqx_version=version)
        summary: dict[str, object] = {
            "sqx_version": version,
            "total": len(entries),
            "seeded": sum(1 for p in entries if p.status == "seeded"),
            "verified": sum(1 for p in entries if p.status == "verified"),
            "needs_review": sum(1 for p in entries if p.status == "needs_review"),
        }
        by_tab: dict[str, dict[str, int]] = {}
        for entry in entries:
            tab_stats = by_tab.setdefault(
                entry.tab, {"total": 0, "seeded": 0, "verified": 0, "needs_review": 0}
            )
            tab_stats["total"] += 1
            tab_stats[entry.status] += 1  # type: ignore[index]
        summary["tabs"] = by_tab
        return summary


# ── REQ-502 query surface (module-level convenience wrappers) ────────────────


def get_parameter(
    tab: str, param: str, sqx_version: str | None = None, root: str | Path = "knowledge"
) -> KbParameter:
    """Load a single KB parameter from the default lake (REQ-502)."""
    return KbStore(root=root).get(tab, param, sqx_version=sqx_version)


def list_parameters(
    tab: str | None = None,
    status: str | None = None,
    sqx_version: str | None = None,
    root: str | Path = "knowledge",
) -> list[KbParameter]:
    """List KB parameters from the default lake (REQ-502)."""
    return KbStore(root=root).list(tab=tab, status=status, sqx_version=sqx_version)
