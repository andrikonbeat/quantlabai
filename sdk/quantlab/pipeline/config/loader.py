"""Pipeline configuration loader with environment variable overrides."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from quantlab.pipeline.config.models import (
    MultiAgentPipelineConfig,
    StageConfig,
)

# Environment variable prefix for overrides
ENV_PREFIX = "QUANTLAB_PIPELINE_"


def _env_key_to_path(key: str) -> list[str]:
    """Convert environment variable key to nested path.

    QUANTLAB_PIPELINE_AGENTS_RESEARCH_MODEL -> ["agents", "research", "model"]
    """
    suffix = key[len(ENV_PREFIX):]
    parts = suffix.lower().split("_")
    return parts


def _set_nested(obj: dict[str, Any], path: list[str], value: Any) -> None:
    """Set value in nested dictionary using path list."""
    current = obj
    for part in path[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[path[-1]] = value


def _parse_env_value(value: str) -> Any:
    """Parse environment variable string to appropriate Python type."""
    # Boolean
    if value.lower() in ("true", "yes", "1", "on"):
        return True
    if value.lower() in ("false", "no", "0", "off"):
        return False

    # Integer
    if re.match(r"^-?\d+$", value):
        return int(value)

    # Float
    if re.match(r"^-?\d*\.\d+$", value):
        return float(value)

    # List (comma-separated)
    if "," in value:
        return [v.strip() for v in value.split(",")]

    # String (default)
    return value


def load_env_overrides() -> dict[str, Any]:
    """Load all QUANTLAB_PIPELINE_* environment variables as nested config.

    Returns:
        Nested dictionary of configuration overrides from environment.
    """
    overrides: dict[str, Any] = {}

    for key, value in os.environ.items():
        if key.startswith("QUANTLAB_PIPELINE_"):
            path = _env_key_to_path(key)
            parsed = _parse_env_value(value)
            _set_nested(overrides, path, parsed)

    return overrides


def merge_configs(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Deep merge override config into base config.

    Args:
        base: Base configuration dictionary.
        overrides: Override configuration dictionary.

    Returns:
        Merged configuration (modifies base in place and returns it).
    """
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            merge_configs(base[key], value)
        else:
            base[key] = value
    return base


def load_multi_agent_pipeline_config(
    path: str,
    apply_env_overrides: bool = True,
) -> Any:
    """Load multi-agent pipeline configuration from YAML with env overrides.

    Args:
        path: Path to YAML configuration file.
        apply_env_overrides: Whether to apply QUANTLAB_PIPELINE_* env vars.

    Returns:
        Validated MultiAgentPipelineConfig instance.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValidationError: If configuration fails schema validation.
    """
    from quantlab.pipeline.config.models import MultiAgentPipelineConfig

    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Pipeline config not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Apply environment variable overrides
    if apply_env_overrides:
        env_overrides = load_env_overrides()

        if env_overrides:
            for key, value in env_overrides.items():
                if key in data and isinstance(data[key], dict) and isinstance(value, dict):
                    merge_configs(data[key], value)
                else:
                    data[key] = value

    return MultiAgentPipelineConfig(**data)


def save_multi_agent_pipeline_config(
    config: Any,
    path: str,
) -> None:
    """Save multi-agent pipeline configuration to YAML.

    Args:
        config: Configuration to save.
        path: Output file path.
    """
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with path_obj.open("w", encoding="utf-8") as f:
        yaml.dump(
            config.model_dump(exclude_none=True, mode="json"),
            f,
            default_flow_style=False,
            sort_keys=False,
        )


# Backward compatibility
def load_pipeline_config(path: str) -> dict:
    """Load legacy pipeline configuration from YAML.

    Args:
        path: Path to YAML configuration file.

    Returns:
        Dictionary with legacy compatible structure.
    """
    path_obj = Path(path)
    with path_obj.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Apply env overrides
    env_overrides = load_env_overrides()

    if env_overrides:
        merge_configs(data, env_overrides)

    return data