"""CustomProject DSL models (REQ-22).

Pure dataclasses — no dependency on the ``cfx`` package, so the DSL layer can
be imported and tested standalone. The mapping to CFX models happens in
``renderers.py`` / ``generator.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quantlab.versioning import PINNED_SQX_VERSION


@dataclass
class DatabankSpec:
    """A project-level databank registry entry (``<Databanks><Databank>``).

    Attributes:
        name: Databank name (unique within a project).
        view: SQX databank view, default matches the verified 144/2953 goldens.
        sync_type: SQX sync strategy, default matches the verified goldens.
        position: Optional numeric position emitted as ``position="N"``.
    """

    name: str
    view: str = "Default - Main data"
    sync_type: str = "Auto-sync never"
    position: int | None = None


@dataclass
class Filters:
    """Filters applied by a Filtering task (``<Conditions>`` section)."""

    conditions: list[str] = field(default_factory=list)


@dataclass
class GoToTask:
    """GoToTask control-flow: jump back to an earlier task when a condition holds.

    Attributes:
        target: ``name`` of the earlier task to jump to (forms the loop).
        condition: Optional expression referencing prior task output
            (e.g. ``retest_failed``).
    """

    target: str
    condition: str = ""


@dataclass
class CustomProjectTask:
    """A single task in the ordered CustomProject task list (REQ-22).

    Attributes:
        type: One of the 21 catalog task types (``catalog.CATALOG_TYPES``).
        name: Human-readable task name (emitted as ``<Task name=...>``).
        active: Whether the task is active in the project.
        source_databank: Databank this task reads from.
        target_databank: Databank this task writes to.
        filters: Optional filters (Filtering task).
        goto: Optional GoToTask control-flow spec (GoToTask task).
        taskXMLFile: Optional explicit XML file name override for the task.
        params: Extra per-task rendering parameters (e.g. ``walkforward_cycles``).
    """

    type: str
    name: str
    active: bool = True
    source_databank: str | None = None
    target_databank: str | None = None
    filters: Filters | None = None
    goto: GoToTask | None = None
    taskXMLFile: str | None = None
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class CustomProject:
    """The CustomProject DSL model (REQ-22).

    Attributes:
        name: Project name (emitted as ``<Project name=...>``).
        tasks: Ordered task list — order is preserved exactly in the output.
        databanks: Project-level databank registry. When empty, the generator
            derives one from the tasks' source/target databanks.
        schema_version: CFX schema version — the pinned SQX build
            (``PINNED_SQX_VERSION``, verified golden).
    """

    name: str
    tasks: list[CustomProjectTask] = field(default_factory=list)
    databanks: list[DatabankSpec] = field(default_factory=list)
    schema_version: str = PINNED_SQX_VERSION
    phase_type: str | None = None
    checkpoint_metadata: dict | None = None
