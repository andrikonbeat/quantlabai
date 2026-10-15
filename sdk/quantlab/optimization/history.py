"""Optimization history buffer with Knowledge Lake persistence.

Manages the history of evaluated points (X, y) and provides
persistence to the Knowledge Lake for session continuity.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class OptimizationStep:
    """A single step in the optimization history.

    Attributes:
        step_id: Unique identifier for this step.
        parameters: Parameter values evaluated.
        objective_value: Objective function value (higher is better).
        metadata: Additional metadata (timestamp, campaign, etc.).
        timestamp: ISO timestamp of evaluation.
    """

    step_id: str
    parameters: dict[str, Any]
    objective_value: float
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step_id": self.step_id,
            "parameters": self.parameters,
            "objective_value": self.objective_value,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizationStep:
        """Create from dictionary."""
        return cls(
            step_id=data["step_id"],
            parameters=data["parameters"],
            objective_value=data["objective_value"],
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
        )


class HistoryBuffer:
    """In-memory buffer for optimization history with Knowledge Lake persistence.

    Maintains a list of OptimizationStep objects and provides
    methods for querying, serialization, and persistence.
    """

    def __init__(
        self,
        campaign_id: str,
        knowledge_lake_path: str | Path | None = None,
        max_size: int | None = None,
    ) -> None:
        """Initialize history buffer.

        Args:
            campaign_id: Unique campaign identifier.
            knowledge_lake_path: Path to Knowledge Lake root.
                If None, uses default location.
            max_size: Maximum number of steps to keep in memory.
                Older steps are persisted but evicted from memory.
        """
        self.campaign_id = campaign_id
        self.max_size = max_size
        self._steps: list[OptimizationStep] = []
        self._best_value: float | None = None
        self._best_params: dict[str, Any] | None = None

        # Set up Knowledge Lake path
        if knowledge_lake_path is None:
            # Default to project knowledge directory
            knowledge_lake_path = Path.cwd() / "knowledge"
        self.knowledge_lake_path = Path(knowledge_lake_path)
        self.history_dir = self.knowledge_lake_path / "structured" / campaign_id / "optimization"
        self.history_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.history_dir / "history.jsonl"
        self.best_file = self.history_dir / "best.json"

    def add(
        self,
        parameters: dict[str, Any],
        objective_value: float,
        metadata: dict[str, Any] | None = None,
        step_id: str | None = None,
    ) -> OptimizationStep:
        """Add a new optimization step.

        Args:
            parameters: Parameter values evaluated.
            objective_value: Objective value (higher is better).
            metadata: Optional additional metadata.
            step_id: Optional custom step ID (auto-generated if None).

        Returns:
            The created OptimizationStep.
        """
        step = OptimizationStep(
            step_id=step_id or str(uuid.uuid4())[:8],
            parameters=parameters,
            objective_value=objective_value,
            metadata=metadata or {},
        )

        self._steps.append(step)

        # Update best
        if self._best_value is None or objective_value > self._best_value:
            self._best_value = objective_value
            self._best_params = parameters.copy()

        # Enforce max size
        if self.max_size is not None and len(self._steps) > self.max_size:
            # Persist evicted steps before removing
            self._persist_steps(self._steps[:-self.max_size])
            self._steps = self._steps[-self.max_size:]

        return step

    def _persist_steps(self, steps: list[OptimizationStep]) -> None:
        """Persist steps to JSONL file (append mode)."""
        with self.history_file.open("a") as f:
            for step in steps:
                f.write(json.dumps(step.to_dict()) + "\n")

    def persist(self) -> None:
        """Persist all in-memory steps to disk."""
        self._persist_steps(self._steps)
        self._persist_best()

    def _persist_best(self) -> None:
        """Persist best parameters and value."""
        if self._best_params is not None:
            data = {
                "campaign_id": self.campaign_id,
                "best_value": self._best_value,
                "best_parameters": self._best_params,
                "num_evaluations": len(self._steps),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            self.best_file.write_text(json.dumps(data, indent=2))

    def load(self) -> int:
        """Load history from disk.

        Returns:
            Number of steps loaded.
        """
        if not self.history_file.exists():
            return 0

        count = 0
        with self.history_file.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    step = OptimizationStep.from_dict(json.loads(line))
                    self._steps.append(step)
                    count += 1

                    # Update best
                    if self._best_value is None or step.objective_value > self._best_value:
                        self._best_value = step.objective_value
                        self._best_params = step.parameters.copy()
                except json.JSONDecodeError:
                    continue

        # Also load best file if exists
        if self.best_file.exists():
            try:
                data = json.loads(self.best_file.read_text())
                self._best_value = data.get("best_value")
                self._best_params = data.get("best_parameters")
            except (json.JSONDecodeError, KeyError):
                pass

        return count

    def get_best(self) -> tuple[float | None, dict[str, Any] | None]:
        """Get best observed value and parameters.

        Returns:
            Tuple of (best_value, best_parameters) or (None, None) if empty.
        """
        return self._best_value, self._best_params

    def get_arrays(self) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """Get history as numpy arrays for surrogate fitting.

        Returns:
            Tuple of (X, y, param_names) where:
            - X: Array of shape (n_steps, n_params)
            - y: Array of shape (n_steps,)
            - param_names: List of parameter names in column order
        """
        if not self._steps:
            return np.empty((0, 0)), np.empty(0), []

        # Get parameter names from first step (assumes consistent params)
        param_names = list(self._steps[0].parameters.keys())
        n_steps = len(self._steps)
        n_params = len(param_names)

        X = np.zeros((n_steps, n_params))
        y = np.zeros(n_steps)

        for i, step in enumerate(self._steps):
            for j, name in enumerate(param_names):
                X[i, j] = step.parameters.get(name, 0.0)
            y[i] = step.objective_value

        return X, y, param_names

    def get_recent(self, n: int) -> list[OptimizationStep]:
        """Get the n most recent steps."""
        return self._steps[-n:] if n > 0 else []

    def __len__(self) -> int:
        return len(self._steps)

    def __iter__(self):
        return iter(self._steps)

    def __getitem__(self, idx: int) -> OptimizationStep:
        return self._steps[idx]

    def to_dataframe(self) -> Any:
        """Convert history to pandas DataFrame (requires pandas)."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required for to_dataframe(). Install with: pip install pandas")

        rows = []
        for step in self._steps:
            row = {
                "step_id": step.step_id,
                "objective_value": step.objective_value,
                "timestamp": step.timestamp,
            }
            row.update(step.parameters)
            row.update({f"meta_{k}": v for k, v in step.metadata.items()})
            rows.append(row)

        return pd.DataFrame(rows)


def load_history(campaign_id: str, knowledge_lake_path: str | Path | None = None) -> HistoryBuffer:
    """Load history buffer from Knowledge Lake.

    Args:
        campaign_id: Campaign identifier.
        knowledge_lake_path: Path to Knowledge Lake root.

    Returns:
        Loaded HistoryBuffer instance.
    """
    buffer = HistoryBuffer(campaign_id, knowledge_lake_path)
    buffer.load()
    return buffer


def create_history_from_exploration(
    campaign_id: str,
    exploration_decision,
    knowledge_lake_path: str | Path | None = None,
) -> HistoryBuffer:
    """Create history buffer initialized from an ExplorationDecision.

    Seeds the history with the exploration decision's implied parameters
    as a starting point (with objective value = 0 as placeholder).

    Args:
        campaign_id: Campaign identifier.
        exploration_decision: ExplorationDecision artifact.
        knowledge_lake_path: Path to Knowledge Lake root.

    Returns:
        Initialized HistoryBuffer.
    """
    from quantlab.optimization.space import ParameterSpace

    buffer = HistoryBuffer(campaign_id, knowledge_lake_path)

    # Create parameter space from exploration decision
    space = ParameterSpace.from_exploration_decision(exploration_decision)

    # Seed with default parameters (objective = 0 as neutral starting point)
    defaults = space.defaults()
    if defaults:
        buffer.add(
            parameters=defaults,
            objective_value=0.0,
            metadata={"source": "exploration_decision", "seeded": True},
        )

    return buffer