"""CustomProject DSL + multi-task CFX generator (REQ-22..25, PR-1).

Lazy attribute exports (PEP 562) keep import order safe: the heavy
generator/validator/catalog modules are only loaded on demand, which avoids
a partial-init cycle when ``quantlab.cfx.models`` is imported first.
"""

from __future__ import annotations

import importlib

from quantlab.customproject.models import (
    CustomProject,
    CustomProjectTask,
    DatabankSpec,
    Filters,
    GoToTask,
)

__all__ = [
    "CustomProject",
    "CustomProjectTask",
    "DatabankSpec",
    "Filters",
    "GoToTask",
    "CATALOG",
    "CATALOG_TYPES",
    "TaskNotSupportedError",
    "generate_cfx_archive",
    "is_custom_project_enabled",
    "ValidationError",
    "validate_golden",
    "resolve_sqcli",
]

_SUBMODULE_EXPORTS = {
    "CATALOG": "catalog",
    "CATALOG_TYPES": "catalog",
    "TaskNotSupportedError": "catalog",
    "generate_cfx_archive": "generator",
    "is_custom_project_enabled": "generator",
    "ValidationError": "validator",
    "validate_golden": "validator",
    "resolve_sqcli": "validator",
}


def __getattr__(name: str):
    module_name = _SUBMODULE_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f"{__name__}.{module_name}")
    return getattr(module, name)
