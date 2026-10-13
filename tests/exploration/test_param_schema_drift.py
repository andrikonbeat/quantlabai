"""Drift tests for task parameter schemas vs catalog (REQ-25, S3).

These tests ensure that TASK_PARAM_SCHEMAS stays in sync with CATALOG_TYPES:
- Exactly one schema entry per catalog type
- Every TaskType member has a schema
- No duplicate keys in the literal
- No schema for types outside the catalog
"""

import ast
from collections import Counter
from pathlib import Path

import pytest
from quantlab.customproject.catalog import CATALOG_TYPES
from quantlab.exploration.params_schema import TASK_PARAM_SCHEMAS, TaskType


def test_tasktype_covers_all_catalog_types() -> None:
    """Every catalog type must have a TaskType enum member."""
    tasktype_values = {t.value for t in TaskType}
    missing = CATALOG_TYPES - tasktype_values
    assert not missing, f"TaskType missing catalog types: {sorted(missing)}"


def test_task_param_schemas_has_entry_per_catalog_type() -> None:
    """TASK_PARAM_SCHEMAS must have exactly one entry per catalog type."""
    schema_keys = {k.value for k in TASK_PARAM_SCHEMAS}
    missing = CATALOG_TYPES - schema_keys
    extra = schema_keys - CATALOG_TYPES
    assert not missing, f"TASK_PARAM_SCHEMAS missing catalog types: {sorted(missing)}"
    assert not extra, f"TASK_PARAM_SCHEMAS has types outside catalog: {sorted(extra)}"
    assert len(TASK_PARAM_SCHEMAS) == len(CATALOG_TYPES), (
        f"TASK_PARAM_SCHEMAS has {len(TASK_PARAM_SCHEMAS)} entries, "
        f"expected {len(CATALOG_TYPES)} (one per catalog type)"
    )


def test_task_param_schemas_no_duplicate_literal_keys() -> None:
    """The TASK_PARAM_SCHEMAS dict literal must not have duplicate keys.

    This catches the bug where 9 keys were repeated verbatim in the source,
    causing the later definition to silently shadow the earlier one at runtime.
    """
    from quantlab.exploration import params_schema

    source = Path(params_schema.__file__).read_text()

    tree = ast.parse(source)

    # Find the TASK_PARAM_SCHEMAS assignment (it's an AnnAssign, not Assign)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "TASK_PARAM_SCHEMAS"
            and isinstance(node.value, ast.Dict)
        ):
            keys: list[str] = []
            for key in node.value.keys:
                if isinstance(key, ast.Attribute):
                    keys.append(key.attr)  # TaskType.XXX
                elif isinstance(key, ast.Constant):
                    keys.append(key.value)

            counts = Counter(keys)
            duplicates = {k: v for k, v in counts.items() if v > 1}
            assert not duplicates, (
                f"TASK_PARAM_SCHEMAS literal has duplicate keys: {duplicates}. "
                "Each key must appear exactly once; merge parameter declarations."
            )
            return

    pytest.fail("Could not find TASK_PARAM_SCHEMAS dict literal in source")


def test_existing_type_parameter_count_preserved() -> None:
    """Pin a representative existing type's parameter count to catch silent drops.

    This test ensures that the deduplication of the 9 repeated keys does not
    lose any parameters from the 14 types that were already declared.
    """
    # Build is the most complex existing type - pin its parameter count
    build_schema = TASK_PARAM_SCHEMAS[TaskType.BUILD]
    # The original Build schema had 54 parameters (counted from source)
    assert len(build_schema) == 54, (
        f"Build schema parameter count changed: expected 54, got {len(build_schema)}. "
        "Deduplication must not drop parameters from existing types."
    )

    # Also verify a few other types to ensure their params weren't lost
    assert len(TASK_PARAM_SCHEMAS[TaskType.FILTERING]) == 1
    assert len(TASK_PARAM_SCHEMAS[TaskType.RETEST]) == 2
    assert len(TASK_PARAM_SCHEMAS[TaskType.GOTO_TASK]) == 2
    assert len(TASK_PARAM_SCHEMAS[TaskType.OPTIMIZE]) == 2
    assert len(TASK_PARAM_SCHEMAS[TaskType.AUTOMATIC_RETEST]) == 3
    assert len(TASK_PARAM_SCHEMAS[TaskType.AUTOMATIC_PORTFOLIO_BUILDER]) == 3
    assert len(TASK_PARAM_SCHEMAS[TaskType.CREATE_PORTFOLIO]) == 1
    assert len(TASK_PARAM_SCHEMAS[TaskType.CUSTOM_ANALYSIS]) == 1
    assert len(TASK_PARAM_SCHEMAS[TaskType.LOG_DATABANK_STATS]) == 1
    assert len(TASK_PARAM_SCHEMAS[TaskType.SAVE_TO_FILES]) == 1
    assert len(TASK_PARAM_SCHEMAS[TaskType.LOAD_FROM_FILES]) == 1
    assert len(TASK_PARAM_SCHEMAS[TaskType.UPDATE_DATA]) == 1
    assert len(TASK_PARAM_SCHEMAS[TaskType.WAIT_FOR]) == 1


def test_gap_types_declare_no_invented_parameters() -> None:
    """The two types with no readable parameter source stay empty (Gap 2).

    Their settings are compiled into TaskApplyMassConfig.jar and
    TaskNeuralNetworkTrainer.jar, and no file in the SQX 144/2953 install names
    their parameters, so declaring any would be invention. When a readable
    source appears, replace this test with the real schema.
    """
    assert TASK_PARAM_SCHEMAS[TaskType.APPLY_MASS_CONFIG] == {}
    assert TASK_PARAM_SCHEMAS[TaskType.NEURAL_NETWORK_TRAINER] == {}


def test_evidence_backed_types_declare_the_extracted_parameters() -> None:
    """Pin the parameter names extracted from the SQX 144/2953 install (Gap 2)."""
    assert set(TASK_PARAM_SCHEMAS[TaskType.CALL_EXTERNAL_SCRIPT]) == {
        "file",
        "params",
        "type",
        "waitfor",
        "hours",
        "minutes",
    }
    assert set(TASK_PARAM_SCHEMAS[TaskType.CLEAR_DATABANKS]) == {"databank"}
    assert set(TASK_PARAM_SCHEMAS[TaskType.DELETE_FILE]) == {"file"}
    assert set(TASK_PARAM_SCHEMAS[TaskType.NOTIFICATION]) == {"type", "email", "wait"}
    assert set(TASK_PARAM_SCHEMAS[TaskType.STOP_AND_START]) == {
        "startAnother",
        "projectName",
        "skipToFirstProject",
    }


def test_every_type_outside_the_documented_gaps_declares_parameters() -> None:
    """A schema entry with no parameters is only legitimate for a documented gap."""
    gaps = {TaskType.APPLY_MASS_CONFIG, TaskType.NEURAL_NETWORK_TRAINER}
    for task_type, schema in TASK_PARAM_SCHEMAS.items():
        if task_type in gaps:
            continue
        assert schema, f"{task_type.value} declares no parameters"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])