"""SQX version pinning + fail-open drift detection (REQ-302..305, D8/D9).

``PINNED_SQX_VERSION`` is the single source of truth for the SQX build this
codebase targets (REQ-302) — version-aware code resolves through this
constant instead of hardcoded literals.

``VersionPreflight`` compares the installed build (REQ-301) against the pin
and is warn-only / fail-open (REQ-303/701): drift NEVER blocks or
mock-dispatches. On drift, ``DriftWorkflow`` persists a migration checklist
under ``structured/sqx-version/{old}→{new}/checklist.yaml`` and invalidates
the departed version's KB parameters (REQ-305/208). Changelog polling,
auto-migration, and blocking are out of scope.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:  # pragma: no cover - type-check only
    from quantlab.cli.runner import Executor
    from quantlab.pipeline.license import LicenseInfo

logger = logging.getLogger(__name__)

# Single source of truth for the SQX build this slice targets (D8/REQ-302).
# Changing this value propagates to every consumer.
PINNED_SQX_VERSION = "144.2953"

# SDK root used for repo-relative impact-scan paths.
_SDK_ROOT = Path(__file__).resolve().parents[1]


def _build_major(version: str) -> str:
    """The integer build prefix ("144.2953" → "144")."""
    return version.split(".", 1)[0]


class VersionPreflight:
    """Compare the installed SQX build against PINNED_SQX_VERSION (REQ-303).

    Fail-open by design: a mismatch logs a prominent warning and (optionally)
    runs the drift workflow — it never raises and never blocks dispatch.
    When the installed build cannot be resolved (mock path, missing sqcli,
    missing Build token) the check reports ``unknown`` and is skipped.

    The comparison uses the build prefix: the real ``sqcli -license`` Build
    line carries no point version ("Build 144"), so an exact string match
    would raise false drift on every real dispatch (design open question).
    """

    def __init__(
        self,
        executor: Executor | None = None,
        *,
        info: LicenseInfo | None = None,
        knowledge_root: str | Path = "knowledge",
        force_mock: bool = False,
    ) -> None:
        self._executor = executor
        self._info = info
        self._force_mock = force_mock
        self.knowledge_root = Path(knowledge_root)
        #: Installed build resolved by the last :meth:`run` (None = unknown).
        self.installed_build: str | None = None

    def detect_installed(self) -> str | None:
        """Resolve the installed build via the license check (REQ-301).

        Reuses a pre-parsed ``LicenseInfo`` when provided; otherwise runs a
        fresh license check through the executor. Mock paths return ``None``
        without invoking anything (REQ-303 mock skip).
        """
        if self._force_mock:
            return None
        if self._info is not None:
            return self._info.build_number
        if self._executor is not None:
            from quantlab.pipeline.license import LicenseManager

            return LicenseManager(self._executor).check().build_number
        return None

    def run(self, *, trigger_workflow: bool = True) -> str:
        """Compare installed vs pinned; returns ``in-sync`` | ``drift`` | ``unknown``.

        On drift, persists the migration checklist and invalidates the old
        KB version when ``trigger_workflow`` (REQ-305). Never raises —
        workflow failures are logged and swallowed (fail-open).
        """
        installed = self.detect_installed()
        self.installed_build = installed
        if installed is None:
            logger.warning(
                "SQX version pre-flight skipped: no build number available "
                "(mock path, missing sqcli, or no Build token)"
            )
            return "unknown"
        if _build_major(installed) == _build_major(PINNED_SQX_VERSION):
            logger.info(
                "SQX version pre-flight passed: installed %s = pinned %s",
                installed,
                PINNED_SQX_VERSION,
            )
            return "in-sync"

        logger.warning(
            "SQX VERSION DRIFT: installed %s vs pinned %s — proceeding "
            "(fail-open). Migration checklist: "
            "structured/sqx-version/%s→%s/ (KB params for %s invalidated)",
            installed,
            PINNED_SQX_VERSION,
            PINNED_SQX_VERSION,
            installed,
            PINNED_SQX_VERSION,
        )
        if trigger_workflow:
            try:
                DriftWorkflow(self.knowledge_root).run(
                    PINNED_SQX_VERSION, installed
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("SQX drift workflow failed (continuing): %s", exc)
        return "drift"


class DriftWorkflow:
    """Persist a migration checklist + invalidate old KB params (REQ-305).

    The checklist lives at ``structured/sqx-version/{from_version}→{to_version}/
    checklist.yaml`` with keys ``{from, to, detected_at, affected_files,
    kb_invalidated, status}``. The impact scan (D9) is a pragmatic literal
    scan of the source tree (markers resolved through the pinned constant)
    plus the departed version's KB parameters — no external codegraph CLI
    dependency. Re-runs update the file in place (REQ-305 additive).
    """

    def __init__(self, root: str | Path = "knowledge") -> None:
        self.root = Path(root)

    def checklist_path(self, from_version: str, to_version: str) -> Path:
        return (
            self.root
            / "structured"
            / "sqx-version"
            / f"{from_version}→{to_version}"
            / "checklist.yaml"
        )

    def impact_scan(self, from_version: str) -> list[str]:
        """Version-dependent files affected by the transition.

        Source files still carrying the pinned literal — or its asset-dir
        spelling (``SQX_144_2953_...``) — are flagged relative to the SDK
        root; KB parameters of the departed version are flagged relative to
        the lake root. Both markers derive from ``PINNED_SQX_VERSION`` so
        the scan tracks the pin automatically (REQ-302).
        """
        affected: list[str] = []
        asset_tag = f"SQX_{PINNED_SQX_VERSION.replace('.', '_')}"
        for path in sorted((_SDK_ROOT / "quantlab").rglob("*.py")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if PINNED_SQX_VERSION in text or asset_tag in text:
                affected.append(str(path.relative_to(_SDK_ROOT)))
        kb_dir = self.root / "structured" / "sqx-kb" / from_version / "parameters"
        if kb_dir.is_dir():
            for path in sorted(kb_dir.rglob("*.yaml")):
                affected.append(str(path.relative_to(self.root)))
        return sorted(set(affected))

    def run(self, from_version: str, to_version: str) -> dict[str, object]:
        """Write the checklist and invalidate the old KB version (REQ-305).

        Returns the checklist document; re-runs overwrite the same path.
        """
        checklist: dict[str, object] = {
            "from": from_version,
            "to": to_version,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "affected_files": self.impact_scan(from_version),
            "kb_invalidated": 0,
            "status": "drift",
        }
        path = self.checklist_path(from_version, to_version)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from quantlab.knowledge.kb.store import KbStore

            checklist["kb_invalidated"] = KbStore(root=self.root).invalidate(
                from_version
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("KB invalidation failed (continuing): %s", exc)
        path.write_text(yaml.safe_dump(checklist, sort_keys=False), encoding="utf-8")
        return checklist
