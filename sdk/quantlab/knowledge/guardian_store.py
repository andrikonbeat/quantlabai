"""Guardian feedback persistence — append-only JSONL metric records.

Design decision: JSONL, not a SQLite table. It matches the ``metrics.jsonl``
spec, it is append-safe (a crash mid-write cannot corrupt earlier records),
and it needs no schema migration.

Layout follows the Knowledge Lake convention declared in
:mod:`quantlab.knowledge.store`::

    knowledge/
    └── guardian-feedback/
        └── {campaign_id}/
            └── metrics.jsonl

Every ``GuardianMetricRecord`` is one line, so a campaign's guardian history
is diff-friendly, Git-versioned, and readable without the SDK.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from quantlab.guardian.models import PortfolioState

logger = logging.getLogger(__name__)

#: Knowledge Lake directory holding guardian feedback (see ``KNOWLEDGE_DIRS``).
GUARDIAN_FEEDBACK_DIR: Final[str] = "guardian-feedback"

#: Per-campaign append-only metrics file inside ``guardian-feedback/``.
METRICS_FILENAME: Final[str] = "metrics.jsonl"

#: Where a metric record originates from.
GuardianMetricSource = Literal["evaluation", "live_stream", "manual"]

#: Characters rejected in a campaign id — a campaign id becomes a path segment.
_FORBIDDEN_PATH_CHARS: Final[frozenset[str]] = frozenset('/\\:*?"<>|')


class GuardianMetricRecord(BaseModel):
    """One guardian observation persisted for a campaign.

    Attributes:
        record_id: Unique identifier for the record.
        campaign_id: Campaign the observation belongs to; also the storage
            path segment under ``guardian-feedback/``.
        timestamp: Observation time.
        guardian_name: Emitting guardian, e.g. ``"risk"``.
        score: Guardian score in ``[0.0, 1.0]``, or ``None`` when the guardian
            produced no score.
        portfolio_state: Portfolio state after the observation.
        risk_metrics: Optional guardian-specific metrics payload.
        correlation_id: Optional link to a related envelope or pipeline phase.
        source: Where the observation came from.
    """

    model_config = ConfigDict(frozen=True)

    record_id: UUID = Field(default_factory=uuid4)
    campaign_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    guardian_name: str
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    portfolio_state: PortfolioState
    risk_metrics: dict[str, Any] | None = None
    correlation_id: str | None = None
    source: GuardianMetricSource = "evaluation"


class GuardianFeedbackStore:
    """Append-only JSONL store for :class:`GuardianMetricRecord`.

    Usage::

        store = GuardianFeedbackStore("knowledge")
        store.write(record)
        records = store.query("camp_001")
    """

    def __init__(self, root: str | Path = "knowledge") -> None:
        """Initialize the store.

        Args:
            root: Knowledge Lake root. Records live under
                ``<root>/guardian-feedback/{campaign_id}/metrics.jsonl``.
        """
        self.root = Path(root)

    # ── Paths ───────────────────────────────────────────────────────────────────

    def path_for(self, campaign_id: str) -> Path:
        """Return the metrics file path for a campaign.

        Args:
            campaign_id: Campaign identifier (a single path segment).

        Returns:
            ``<root>/guardian-feedback/{campaign_id}/metrics.jsonl``.

        Raises:
            ValueError: If ``campaign_id`` is empty or contains path
                separators, so a campaign id can never escape the store root.
        """
        if not campaign_id or not campaign_id.strip():
            raise ValueError("campaign_id must be a non-empty string")
        if _FORBIDDEN_PATH_CHARS & set(campaign_id) or ".." in campaign_id:
            raise ValueError(
                f"campaign_id must be a single safe path segment, got {campaign_id!r}"
            )
        return self.root / GUARDIAN_FEEDBACK_DIR / campaign_id / METRICS_FILENAME

    # ── Write ───────────────────────────────────────────────────────────────────

    def write(self, record: GuardianMetricRecord) -> None:
        """Append a metric record to the campaign's JSONL file.

        Creates ``guardian-feedback/{campaign_id}/`` on first write. The record
        is serialised in one ``write()`` call so concurrent appends cannot
        interleave a partial line.

        Args:
            record: The record to persist.

        Raises:
            ValueError: If ``record.campaign_id`` is not a safe path segment.
        """
        path = self.path_for(record.campaign_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")

    # ── Query ───────────────────────────────────────────────────────────────────

    def query(
        self,
        campaign_id: str,
        guardian_name: str | None = None,
        source: GuardianMetricSource | None = None,
    ) -> list[GuardianMetricRecord]:
        """Read the records for a campaign in write order.

        A malformed line is logged and skipped: one bad append must not make
        a campaign's guardian history unreadable.

        Args:
            campaign_id: Campaign identifier to read.
            guardian_name: Optional guardian filter.
            source: Optional source filter.

        Returns:
            Matching records, oldest first. Empty when the campaign is unknown.
        """
        path = self.path_for(campaign_id)
        if not path.exists():
            return []

        records: list[GuardianMetricRecord] = []
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                record = GuardianMetricRecord.model_validate_json(line)
            except Exception:
                logger.warning(
                    "Skipping malformed guardian metric at %s:%d", path, line_number
                )
                continue
            if guardian_name is not None and record.guardian_name != guardian_name:
                continue
            if source is not None and record.source != source:
                continue
            records.append(record)
        return records
