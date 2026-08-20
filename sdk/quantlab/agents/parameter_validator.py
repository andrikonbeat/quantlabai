"""ParameterValidator — blocks invalid hypothesis parameters before building."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quantlab.dsl.models import HypothesisConfig
from quantlab.knowledge.sqX_doc_provider import SQXDocProvider


@dataclass
class ValidationResult:
    """Outcome of a parameter validation pass."""

    valid: bool
    errors: list[str] = field(default_factory=list)


class ParameterValidator:
    """Validates hypothesis parameters against SQXDocProvider constraints.

    Delegates constraint lookups to ``SQXDocProvider`` and returns a
    ``ValidationResult``. The caller is responsible for rejecting invalid
    hypotheses.
    """

    def __init__(self, doc_provider: SQXDocProvider | None = None) -> None:
        self._provider = doc_provider or SQXDocProvider()

    def validate_hypothesis(
        self, hypothesis: HypothesisConfig, sqx_version: str = "latest"
    ) -> ValidationResult:
        """Validate all parameters in a hypothesis.

        Args:
            hypothesis: The hypothesis config to validate.
            sqx_version: SQX version to validate against.

        Returns:
            ``ValidationResult`` with ``valid`` flag and accumulated errors.
        """
        errors: list[str] = []
        params = hypothesis.parameters or {}

        # Group parameters by inferred indicator prefix
        indicator_params: dict[str, dict[str, Any]] = {}
        for key, value in params.items():
            if "_" in key:
                indicator, _, param_name = key.partition("_")
                indicator = indicator.lower()
                indicator_params.setdefault(indicator, {})[param_name] = value
            else:
                # Bare params without an indicator prefix (e.g. "oversold")
                # are not indicator-level parameters; skip them here.
                continue

        for indicator, param_dict in indicator_params.items():
            # Check indicator existence
            if not self._provider.has_indicator(indicator, sqx_version):
                errors.append(f"Unknown indicator: {indicator}")
                continue

            for param_name, value in param_dict.items():
                # Range check
                valid_range = self._provider.get_valid_range(indicator, param_name, sqx_version)
                if valid_range is not None and isinstance(value, (int, float)):
                    min_val, max_val = valid_range
                    if not (min_val <= value <= max_val):
                        errors.append(
                            f"{indicator}.{param_name}={value} out of range "
                            f"[{min_val}, {max_val}]"
                        )

                # Enum check
                enum_values = self._provider.get_enum_values(indicator, param_name, sqx_version)
                if enum_values is not None and value not in enum_values:
                    errors.append(
                        f"{indicator}.{param_name}={value} not in enum "
                        f"{enum_values}"
                    )

                # Type check
                expected_type = self._provider.get_type(indicator, param_name, sqx_version)
                if expected_type == "int" and not isinstance(value, int):
                    errors.append(
                        f"{indicator}.{param_name} type mismatch: expected int, "
                        f"got {type(value).__name__}"
                    )
                elif expected_type == "float" and not isinstance(value, (int, float)):
                    errors.append(
                        f"{indicator}.{param_name} type mismatch: expected float, "
                        f"got {type(value).__name__}"
                    )
                elif expected_type == "bool" and not isinstance(value, bool):
                    errors.append(
                        f"{indicator}.{param_name} type mismatch: expected bool, "
                        f"got {type(value).__name__}"
                    )

        return ValidationResult(valid=len(errors) == 0, errors=errors)


__all__ = ["ParameterValidator", "ValidationResult"]
