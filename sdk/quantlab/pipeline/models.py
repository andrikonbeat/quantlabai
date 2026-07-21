"""Pipeline result and history models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    stage_name: str
    status: StageStatus = StageStatus.PENDING
    duration: float = 0.0
    error: str | None = None
    output: Any = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None


@dataclass
class PipelineResult:
    pipeline_name: str
    stages: list[StageResult] = field(default_factory=list)
    total_duration: float = 0.0
    error: str | None = None

    @property
    def is_successful(self) -> bool:
        return (
            self.error is None
            and all(s.status == StageStatus.COMPLETED for s in self.stages)
        )


# ─── History Models ────────────────────────────────────────────────────────────


@dataclass
class StageRun:
    """Record of a single stage execution in a pipeline run."""

    name: str
    status: StageStatus = StageStatus.PENDING
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    duration: float = 0.0
    error: str | None = None
    output: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "error": self.error,
            "output": self.output,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageRun":
        return cls(
            name=data["name"],
            status=StageStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            duration=data.get("duration", 0.0),
            error=data.get("error"),
            output=data.get("output"),
        )


@dataclass
class PipelineRun:
    """Complete record of a pipeline execution, persisted to Knowledge Lake."""

    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    pipeline_name: str = ""
    status: StageStatus = StageStatus.PENDING
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    duration: float = 0.0
    error: str | None = None
    stages: list[StageRun] = field(default_factory=list)
    config_snapshot: dict[str, Any] | None = None  # Full pipeline config at run time
    artifacts: dict[str, str] = field(default_factory=dict)  # Key paths to artifacts

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "error": self.error,
            "stages": [s.to_dict() for s in self.stages],
            "config_snapshot": self.config_snapshot,
            "artifacts": self.artifacts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineRun":
        return cls(
            run_id=data["run_id"],
            pipeline_name=data["pipeline_name"],
            status=StageStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            duration=data.get("duration", 0.0),
            error=data.get("error"),
            stages=[StageRun.from_dict(s) for s in data.get("stages", [])],
            config_snapshot=data.get("config_snapshot"),
            artifacts=data.get("artifacts", {}),
        )

    @classmethod
    def from_pipeline_result(
        cls,
        result: "PipelineResult",
        pipeline_name: str,
        config_snapshot: dict[str, Any] | None = None,
        artifacts: dict[str, str] | None = None,
    ) -> "PipelineRun":
        """Create a PipelineRun from a PipelineResult."""
        run = cls(pipeline_name=pipeline_name, config_snapshot=config_snapshot, artifacts=artifacts or {})
        run.status = StageStatus.COMPLETED if result.is_successful else StageStatus.FAILED
        run.started_at = (
            min((s.started_at for s in result.stages if s.started_at), default=datetime.now())
        )
        run.completed_at = (
            max((s.completed_at for s in result.stages if s.completed_at), default=None)
        )
        run.duration = result.total_duration
        run.error = result.error
        run.stages = [
            StageRun(
                name=s.stage_name,
                status=s.status,
                started_at=s.started_at,
                completed_at=s.completed_at,
                duration=s.duration,
                error=s.error,
                output=s.output,
            )
            for s in result.stages
        ]
        return run