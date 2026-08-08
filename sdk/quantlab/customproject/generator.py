"""CustomProject → CFX archive generator (REQ-23).

``generate_cfx_archive(project)`` is the single entry point of the
custom-project generator. It renders every DSL task through the 21-task
catalog, builds an ordered ``CfxProject`` (task XML files keyed by their
``taskXMLFile`` name, plus the project databank registry) and returns a
``CfxArchive`` ready for ``CfxWriter``.
"""

from __future__ import annotations

import os

from quantlab.cfx.models import BuildTask, CfxArchive, CfxProject, TaskMeta
from quantlab.customproject.catalog import render_task
from quantlab.customproject.models import CustomProject, DatabankSpec


def is_custom_project_enabled(env: dict[str, str] | None = None) -> bool:
    """Rollback gate (AD-3): ``QUANTLAB_CUSTOM_PROJECT=0`` keeps the legacy
    single-task generator path (``sqx.project_builder``) untouched."""
    env = os.environ if env is None else env
    return env.get("QUANTLAB_CUSTOM_PROJECT", "1") != "0"


def _resolve_databanks(project: CustomProject) -> list[DatabankSpec]:
    """Use the declared registry, or derive one from the tasks' databanks.

    Derivation preserves first-seen order and skips ``None`` values; duplicates
    are deduplicated (a databank appears once in the registry).
    """
    if project.databanks:
        return list(project.databanks)

    seen: list[DatabankSpec] = []
    names: set[str] = set()
    for task in project.tasks:
        for name in (task.source_databank, task.target_databank):
            if name and name not in names:
                names.add(name)
                seen.append(DatabankSpec(name=name))
    return seen


def generate_cfx_archive(project: CustomProject) -> CfxArchive:
    """Generate a CfxArchive from a CustomProject DSL model.

    Raises:
        TaskNotSupportedError: A task type is outside the 21-task catalog.
        ValueError: Two tasks resolve to the same ``taskXMLFile`` name.
    """
    tasks: dict[str, BuildTask] = {}
    task_meta: dict[str, TaskMeta] = {}
    counters: dict[str, int] = {}

    for task in project.tasks:
        rendered = render_task(task)

        if task.taskXMLFile:
            filename = task.taskXMLFile
        else:
            counters[task.type] = counters.get(task.type, 0) + 1
            filename = f"{task.type}-Task{counters[task.type]}.xml"

        if filename in tasks:
            raise ValueError(
                f"Duplicate taskXMLFile {filename!r} in project {project.name!r}"
            )

        tasks[filename] = rendered
        task_meta[filename] = TaskMeta(
            task_type=task.type,
            name=task.name,
            active=task.active,
        )

    databanks = _resolve_databanks(project)

    config = CfxProject(
        name=project.name,
        tasks=tasks,
        schema_version=project.schema_version,
        databanks=databanks,
        task_meta=task_meta,
    )
    if project.phase_type or project.checkpoint_metadata:
        config.metadata = {}
        if project.phase_type:
            config.metadata["phase_type"] = project.phase_type
        if project.checkpoint_metadata:
            config.metadata["checkpoint_metadata"] = project.checkpoint_metadata
    return CfxArchive(config=config, task_files=tasks)
