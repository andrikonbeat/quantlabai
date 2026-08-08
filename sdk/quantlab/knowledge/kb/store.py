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
        return self._version_dir(sqx_version) / tab / f"{param}.yaml"

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
        for param_file in sorted(version_dir.glob("*/*.yaml")):
            if tab is not None and param_file.parent.name != tab:
                continue
            try:
                param = self._load_file(param_file)
            except Exception:
                continue  # Skip corrupted entries; filesystem is source of truth
            if status is not None and param.status != status:
                continue
            results.append(param)
        return results

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
        for path in version_dir.glob("*/*.yaml"):
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
