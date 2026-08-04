"""21-task catalog (REQ-25): task type → renderer + required params.

The catalog is the single registry of supported task types. Types outside it
raise ``TaskNotSupportedError`` naming the offending type. Walk-Forward is NOT
a standalone catalog task — it renders inside Retest/Optimize CrossChecks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from quantlab.cfx.models import BuildTask
from quantlab.customproject.models import CustomProjectTask
from quantlab.customproject.renderers import RENDERERS


class TaskNotSupportedError(ValueError):
    """Raised when a task type is outside the 21-task catalog (REQ-25)."""

    def __init__(self, task_type: str) -> None:
        super().__init__(
            f"Unsupported task type {task_type!r}: not in the verified "
            "21-task catalog (Build, Retest, Optimize, AutomaticRetest, "
            "AutomaticPortfolioBuilder, Filtering, GoToTask, LoadFromFiles, "
            "SaveToFiles, ClearDatabanks, CreatePortfolio, CustomAnalysis, "
            "DeleteFile, CallExternalScript, LogDatabankStats, "
            "NeuralNetworkTrainer, Notification, StopAndStart, UpdateData, "
            "WaitFor, ApplyMassConfig)"
        )


# The verified 21-task catalog (REQ-25), Walk-Forward expressed inside
# Retest/Optimize CrossChecks rather than as a standalone task.
CATALOG_TYPES = frozenset(
    {
        "Build",
        "Retest",
        "Optimize",
        "AutomaticRetest",
        "AutomaticPortfolioBuilder",
        "Filtering",
        "GoToTask",
        "LoadFromFiles",
        "SaveToFiles",
        "ClearDatabanks",
        "CreatePortfolio",
        "CustomAnalysis",
        "DeleteFile",
        "CallExternalScript",
        "LogDatabankStats",
        "NeuralNetworkTrainer",
        "Notification",
        "StopAndStart",
        "UpdateData",
        "WaitFor",
        "ApplyMassConfig",
    }
)


@dataclass(frozen=True)
class CatalogEntry:
    """A catalog entry: task type → renderer."""

    task_type: str
    renderer: Callable[[CustomProjectTask], BuildTask]


def _build_catalog() -> dict[str, CatalogEntry]:
    missing = CATALOG_TYPES - frozenset(RENDERERS)
    if missing:
        raise RuntimeError(f"catalog types missing renderers: {sorted(missing)}")
    return {
        t: CatalogEntry(task_type=t, renderer=RENDERERS[t]) for t in CATALOG_TYPES
    }


CATALOG: dict[str, CatalogEntry] = _build_catalog()


def render_task(task: CustomProjectTask) -> BuildTask:
    """Render a DSL task via its catalog renderer.

    Raises:
        TaskNotSupportedError: The task type is outside the 21-task catalog.
    """
    entry = CATALOG.get(task.type)
    if entry is None:
        raise TaskNotSupportedError(task.type)
    return entry.renderer(task)
