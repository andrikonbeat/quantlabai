"""CandidatePool — stores evolution candidates with JSON filesystem persistence."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from quantlab.evolution.models import CandidateStatus, EvolutionCandidate


class CandidatePool:
    """Persistent pool of evolution candidates.

    Stores candidates as individual JSON files in a configurable directory.
    Supports add, promote, and query operations.
    """

    def __init__(self, pool_directory: str = ".evolution_pool") -> None:
        """Initialize the candidate pool.

        Args:
            pool_directory: Directory path for candidate persistence.
        """
        self._pool_dir = Path(pool_directory)
        self._pool_dir.mkdir(parents=True, exist_ok=True)

    def _candidate_path(self, candidate_id: str) -> Path:
        return self._pool_dir / f"{candidate_id}.json"

    def add(self, candidate: EvolutionCandidate) -> None:
        """Add a candidate to the pool.

        Args:
            candidate: The candidate to add.
        """
        path = self._candidate_path(candidate.candidate_id)
        with open(path, "w") as f:
            json.dump(candidate.model_dump(), f, default=str, indent=2)

    def get(self, candidate_id: str) -> Optional[EvolutionCandidate]:
        """Retrieve a candidate by ID.

        Args:
            candidate_id: Unique candidate identifier.

        Returns:
            The candidate if found, None otherwise.
        """
        path = self._candidate_path(candidate_id)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return EvolutionCandidate(**data)

    def load_all(self) -> List[EvolutionCandidate]:
        """Load all candidates from the pool.

        Returns:
            List of all candidates.
        """
        candidates: List[EvolutionCandidate] = []
        for path in self._pool_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                candidates.append(EvolutionCandidate(**data))
            except (json.JSONDecodeError, KeyError):
                continue
        return candidates

    def get_by_status(self, status: CandidateStatus) -> List[EvolutionCandidate]:
        """Get all candidates with a specific status.

        Args:
            status: Status filter.

        Returns:
            Matching candidates.
        """
        return [c for c in self.load_all() if c.status == status]

    def get_ready_for_promotion(
        self, threshold: float = 0.7
    ) -> List[EvolutionCandidate]:
        """Get candidates that passed validation and meet the threshold.

        Args:
            threshold: Minimum fitness score for promotion.

        Returns:
            Candidates ready for promotion.
        """
        return [
            c for c in self.load_all()
            if c.status == CandidateStatus.PASSED and c.fitness_score >= threshold
        ]

    def update_status(
        self, candidate_id: str, status: CandidateStatus,
        fitness_score: Optional[float] = None
    ) -> bool:
        """Update a candidate's status.

        Args:
            candidate_id: Candidate to update.
            status: New status.
            fitness_score: Optional updated fitness score.

        Returns:
            True if updated, False if candidate not found.
        """
        candidate = self.get(candidate_id)
        if candidate is None:
            return False

        updated = candidate.model_copy(update={
            "status": status,
            "fitness_score": fitness_score if fitness_score is not None else candidate.fitness_score,
        })
        self.add(updated)
        return True

    def promote(self, candidate_id: str) -> bool:
        """Mark a candidate as promoted.

        Args:
            candidate_id: Candidate to promote.

        Returns:
            True if promoted, False if not found.
        """
        candidate = self.get(candidate_id)
        if candidate is None:
            return False
        updated = candidate.model_copy(update={
            "status": CandidateStatus.PROMOTED,
            "promoted_at": datetime.now(),
        })
        self.add(updated)
        return True

    def cleanup_expired(self, ttl_days: int = 30) -> int:
        """Remove candidates that have expired.

        Args:
            ttl_days: Time-to-live in days.

        Returns:
            Number of removed candidates.
        """
        now = datetime.now()
        removed = 0
        for candidate in self.load_all():
            age = (now - candidate.created_at).days
            if age > ttl_days:
                path = self._candidate_path(candidate.candidate_id)
                path.unlink(missing_ok=True)
                removed += 1
        return removed
