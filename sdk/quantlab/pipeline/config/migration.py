"""Pipeline configuration migration helpers for version upgrades."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


# Current config version
CURRENT_VERSION = "2.0.0"


def get_config_version(data: dict[str, Any]) -> str:
    """Extract version from config data, defaulting to 1.0.0."""
    return data.get("version", data.get("pipeline", {}).get("version", "1.0.0"))


def migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate v1.x config to v2.0 multi-agent format.
    
    v1 format:
        name: string
        description: string
        version: string
        stages: list of {name, type, config}
    
    v2 format:
        pipeline: {name, description, version, stages}
        agents: {}
        gates: []
        memory: {}
        risk: {}
    """
    if "pipeline" in data:
        # Already v2 format
        return data
    
    # Convert v1 to v2
    migrated = {
        "pipeline": {
            "name": data.get("name", "migrated-pipeline"),
            "description": data.get("description", ""),
            "version": data.get("version", "1.0.0"),
            "stages": data.get("stages", []),
        },
        "agents": {},
        "gates": [
            {"name": "HUMAN_REVIEW_OBJECTIVES", "timeout_hours": 24, "fallback": "proceed"},
            {"name": "HUMAN_APPROVE_ITERATION", "timeout_hours": 24, "fallback": "proceed"},
            {"name": "HUMAN_APPROVE_PORTFOLIO", "timeout_hours": 12, "fallback": "proceed"},
            {"name": "HUMAN_APPROVE_DEPLOY", "timeout_hours": 6, "fallback": "proceed"},
            {"name": "HUMAN_REVIEW_PERFORMANCE", "timeout_hours": 48, "fallback": "proceed"},
        ],
        "memory": {
            "enabled": True,
            "topic_prefix": "quantlab/agent",
            "retention_days": 365,
            "cross_agent_sharing": True,
        },
        "risk": {
            "max_portfolio_drawdown": 0.20,
            "max_strategy_correlation": 0.7,
            "max_single_strategy_weight": 0.4,
            "kelly_fraction_cap": 0.25,
            "var_confidence": 0.95,
        },
    }
    
    return migrated


def migrate_config(data: dict[str, Any], target_version: str = CURRENT_VERSION) -> dict[str, Any]:
    """Migrate config to target version.
    
    Args:
        data: Raw config dictionary.
        target_version: Target version string.
        
    Returns:
        Migrated config dictionary.
    """
    current = get_config_version(data)
    
    if current == target_version:
        return data
    
    # Parse versions for comparison
    def parse_version(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))
    
    current_parsed = parse_version(current)
    target_parsed = parse_version(target_version)
    
    if current_parsed >= target_parsed:
        # Already at or beyond target
        return data
    
    # Apply migrations in order
    if current_parsed < (2, 0, 0):
        data = migrate_v1_to_v2(data)
    
    # Future migrations would go here
    
    # Update version
    if "pipeline" in data:
        data["pipeline"]["version"] = target_version
    else:
        data["version"] = target_version
    
    return data


def load_and_migrate(path: Path | str) -> dict[str, Any]:
    """Load YAML config and migrate to current version.
    
    Args:
        path: Path to YAML file.
        
    Returns:
        Migrated config dictionary ready for validation.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    return migrate_config(data)


def save_with_version(
    config: dict[str, Any],
    path: Path | str,
    version: str = CURRENT_VERSION,
) -> None:
    """Save config with version field.
    
    Args:
        config: Config dictionary.
        path: Output path.
        version: Version to write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure version is set
    if "pipeline" in config:
        config["pipeline"]["version"] = version
    else:
        config["version"] = version
    
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)