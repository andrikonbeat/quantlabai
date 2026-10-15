"""SQX automation package.

Provides:
- spec: Strict spec parser/validator
- templates: Default task XML loader
- builder: Surgical XML edits on defaults
- sections: Cross-checks and shared settings parser/emitter
- project_io: Project CFX load/describe/edit/apply
- oracle: Live validation via taskmanager/validateProject
- paths: Install root/session/output directory resolution
- validator: High-level CLI and validation orchestration
"""

# Avoid circular imports by using lazy imports in __getattr__
# Core modules are available via direct import:
#   from quantlab.sqx.spec import ...
#   from quantlab.sqx.templates import ...
#   etc.

# Backward-compatible eager exports (original package surface).
from quantlab.sqx.campaign_monitor import CampaignMonitor, WatcherEvent
from quantlab.sqx.cli_wrapper import dispatch_campaign
from quantlab.sqx.project_builder import create_project, remove_project

__all__ = [
    "CampaignMonitor",
    "WatcherEvent",
    "dispatch_campaign",
    "create_project",
    "remove_project",
    # spec
    "validate_spec", "parse_spec", "SpecValidationError",
    # templates
    "load_defaults", "available_types", "available_columns", "snippet_names", "get_install_root",
    # builder
    "apply_curated_keys", "apply_spec_to_task", "build_cfx_from_spec",
    # sections
    "parse_cross_checks", "emit_cross_checks", "extract_cross_checks",
    "parse_money_management", "parse_trading_options", "parse_costs",
    "parse_fitness", "parse_what_to_build", "parse_stop", "parse_range",
    # project_io
    "load_project_cfx", "describe", "merge_edit", "apply_inplace", "spec_to_cfx",
    # oracle
    "validate_cfx", "validate",
    # paths
    "install_root", "sessions_root", "session_projects_dir", "output_dir",
    "discover_port", "discover_app_version",
    # validator
    "validate_spec", "ValidationResult", "generate_cfx_from_spec",
]

__version__ = "0.1.0"


def __getattr__(name: str):
    """Lazy import for submodules to avoid circular imports."""
    if name in ("validate_spec", "ValidationResult", "generate_cfx_from_spec"):
        from .validator import validate_spec_json, ValidationResult, generate_cfx_from_spec
        return {"validate_spec": validate_spec_json, "ValidationResult": ValidationResult, "generate_cfx_from_spec": generate_cfx_from_spec}[name]

    if name in ("parse_spec", "SpecValidationError"):
        from .spec import parse_spec, SpecValidationError
        return {"parse_spec": parse_spec, "SpecValidationError": SpecValidationError}[name]
    
    if name in ("load_defaults", "available_types", "available_columns", "snippet_names", "get_install_root"):
        from .templates import load_defaults, available_types, available_columns, snippet_names, get_install_root
        return {"load_defaults": load_defaults, "available_types": available_types, "available_columns": available_columns, "snippet_names": snippet_names, "get_install_root": get_install_root}[name]
    
    if name in ("apply_curated_keys", "apply_spec_to_task", "build_cfx_from_spec"):
        from .builder import apply_curated_keys, apply_spec_to_task, build_cfx_from_spec
        return {"apply_curated_keys": apply_curated_keys, "apply_spec_to_task": apply_spec_to_task, "build_cfx_from_spec": build_cfx_from_spec}[name]
    
    if name in ("parse_cross_checks", "emit_cross_checks", "extract_cross_checks",
                "parse_money_management", "parse_trading_options", "parse_costs",
                "parse_fitness", "parse_what_to_build", "parse_stop", "parse_range"):
        from .sections import parse_cross_checks, emit_cross_checks, extract_cross_checks, parse_money_management, parse_trading_options, parse_costs, parse_fitness, parse_what_to_build, parse_stop, parse_range
        return {"parse_cross_checks": parse_cross_checks, "emit_cross_checks": emit_cross_checks, "extract_cross_checks": extract_cross_checks, "parse_money_management": parse_money_management, "parse_trading_options": parse_trading_options, "parse_costs": parse_costs, "parse_fitness": parse_fitness, "parse_what_to_build": parse_what_to_build, "parse_stop": parse_stop, "parse_range": parse_range}[name]
    
    if name in ("load_project_cfx", "describe", "merge_edit", "apply_inplace", "spec_to_cfx"):
        from .project_io import load_project_cfx, describe, merge_edit, apply_inplace, spec_to_cfx
        return {"load_project_cfx": load_project_cfx, "describe": describe, "merge_edit": merge_edit, "apply_inplace": apply_inplace, "spec_to_cfx": spec_to_cfx}[name]
    
    if name in ("validate_cfx", "validate"):
        from .oracle import validate_cfx, validate
        return {"validate_cfx": validate_cfx, "validate": validate}[name]
    
    if name in ("install_root", "sessions_root", "session_projects_dir", "output_dir", "discover_port", "discover_app_version"):
        from .paths import install_root, sessions_root, session_projects_dir, output_dir, discover_port, discover_app_version
        return {"install_root": install_root, "sessions_root": sessions_root, "session_projects_dir": session_projects_dir, "output_dir": output_dir, "discover_port": discover_port, "discover_app_version": discover_app_version}[name]
    
    if name in ("validate_spec_json", "ValidationResult", "generate_cfx_from_spec"):
        from .validator import validate_spec as validate_spec_json, ValidationResult, generate_cfx_from_spec
        return {"validate_spec_json": validate_spec_json, "ValidationResult": ValidationResult, "generate_cfx_from_spec": generate_cfx_from_spec}[name]
    
    raise AttributeError(f"module 'quantlab.sqx' has no attribute '{name}'")


__version__ = "0.1.0"