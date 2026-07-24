"""Checkpoint persistence — JSON save/load/resume for campaign state.

Provides ``CheckpointManager`` for durable campaign checkpoints and
``CampaignCheckpoint`` as the serialisable state container.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from quantlab.pipeline.models import StageStatus


class CampaignPhase(str, Enum):
    """Execution phases for an sqcli campaign lifecycle.

    Matches the 7-phase flow: translate → daemon_start → load_config →
    run → poll → export → store.
    """

    TRANSLATE = "translate"
    DAEMON_START = "daemon_start"
    LOAD_CONFIG = "load_config"
    RUN = "run"
    POLL = "poll"
    EXPORT = "export"
    STORE = "store"


# ── Data types ────────────────────────────────────────────────────────────────


class PhaseResult:
    """Outcome of a single campaign phase.

    Args:
        phase: The phase that executed.
        status: ``StageStatus.COMPLETED`` on success, ``StageStatus.FAILED``
            on error.
        duration: Wall-clock seconds the phase took.
        error: Error detail when the phase failed, else ``None``.
    """

    def __init__(
        self,
        phase: CampaignPhase,
        status: StageStatus,
        duration: float,
        error: str | None = None,
    ) -> None:
        self.phase = phase
        self.status = status
        self.duration = duration
        self.error = error


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
                    status=StageStatus(r["status"]),
                    duration=r["duration"],
                    error=r.get("error"),
                )
                for r in data["phase_results"]
            ],
            cfx_path=data.get("cfx_path"),
            export_paths=data.get("export_paths", {}),
        )
