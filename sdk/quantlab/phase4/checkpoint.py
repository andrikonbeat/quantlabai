"""Checkpoint persistence — JSON save/load/resume for campaign state.

Provides ``CheckpointManager`` backed by the orchestrator's campaign types
(``CampaignPhase``, ``PhaseResult``) for durable campaign checkpoints.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quantlab.phase4.models import CampaignPhase, PhaseResult, PhaseStatus


class CampaignCheckpoint:
    """Serialisable snapshot of a partially-completed campaign.

    Args:
        project_name: The campaign project identifier.
        completed_phases: Phases that finished successfully, in order.
        phase_results: Full results for every executed phase.
        cfx_path: Path to the generated ``.cfx`` file, if translation
            has completed.
        export_paths: Mapping of export format to filesystem path.
    """

    def __init__(
        self,
        project_name: str,
        completed_phases: list[CampaignPhase],
        phase_results: list[PhaseResult],
        cfx_path: str | None = None,
        export_paths: dict[str, str] | None = None,
    ) -> None:
        self.project_name = project_name
        self.completed_phases = list(completed_phases)
        self.phase_results = list(phase_results)
        self.cfx_path = cfx_path
        self.export_paths = export_paths or {}
        self._created_at = datetime.now(timezone.utc).isoformat()


class CheckpointManager:
    """JSON-backed checkpoint store for campaign resilience.

    Checkpoints are stored as ``<root>/<project_name>.json`` and are
    human-readable for debugging failed campaigns.

    Args:
        root: Directory where checkpoint files are written.  Created
            automatically if it does not exist.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _file_path(self, project_name: str) -> Path:
        return self._root / f"{project_name}.json"

    def save(self, checkpoint: CampaignCheckpoint) -> Path:
        """Write *checkpoint* to disk as JSON.

        Args:
            checkpoint: The campaign state to persist.

        Returns:
            The filesystem path where the checkpoint was written.
        """
        path = self._file_path(checkpoint.project_name)
        payload = self._serialize(checkpoint)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load(self, project_name: str) -> CampaignCheckpoint | None:
        """Load a previously saved checkpoint, if one exists.

        Args:
            project_name: The campaign project identifier.

        Returns:
            The deserialised ``CampaignCheckpoint``, or ``None`` when no
            checkpoint is present for the project.
        """
        path = self._file_path(project_name)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self._deserialize(payload)

    def clear(self, project_name: str) -> None:
        """Remove the checkpoint file for *project_name*, if present."""
        path = self._file_path(project_name)
        if path.exists():
            path.unlink()

    def latest_phase(self, project_name: str) -> CampaignPhase | None:
        """Return the last successfully completed phase, or ``None``."""
        cp = self.load(project_name)
        if cp is None or not cp.completed_phases:
            return None
        return cp.completed_phases[-1]

    # ── Serialisation helpers ───────────────────────────────────────────

    def _serialize(self, checkpoint: CampaignCheckpoint) -> dict[str, Any]:
        return {
            "project_name": checkpoint.project_name,
            "created_at": checkpoint._created_at,
            "completed_phases": [p.value for p in checkpoint.completed_phases],
            "cfx_path": checkpoint.cfx_path,
            "export_paths": checkpoint.export_paths,
            "phase_results": [
                {
                    "phase": r.phase.value,
                    "status": r.status.value,
                    "duration": r.duration,
                    "detail": r.detail,
                    "error": r.error,
                }
                for r in checkpoint.phase_results
            ],
        }

    def _deserialize(self, data: dict[str, Any]) -> CampaignCheckpoint:
        return CampaignCheckpoint(
            project_name=data["project_name"],
            completed_phases=[CampaignPhase(p) for p in data["completed_phases"]],
            phase_results=[
                PhaseResult(
                    phase=CampaignPhase(r["phase"]),
                    status=PhaseStatus(r["status"]),
                    detail=r.get("detail", ""),
                    error=r.get("error"),
                )
                for r in data["phase_results"]
            ],
            cfx_path=data.get("cfx_path"),
            export_paths=data.get("export_paths", {}),
        )
