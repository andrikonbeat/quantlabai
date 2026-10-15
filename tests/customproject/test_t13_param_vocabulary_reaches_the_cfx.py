"""T13: a mapped parameter value must reach the .cfx, not vanish in the serializer.

T2 declared ``TASK_PARAM_SCHEMAS`` with plausible snake_case names; T3-1..T3-5
wrote serializers that read the keys harvested from the real SQX 144/2953
install (``odd/notes/sqx-task-xml-dialect.md``). The two vocabularies never met.
Because ``ParamMapper.map`` runs ``coerce_params``, the schema decides which keys
reach ``CustomProjectTask.params``, while the serializer reads the harvested
keys: a key the serializer does not read is dropped silently and the serializer
falls back to its own default, so the mapped value never reaches the .cfx.

This module probes that contract through the public interface instead of reading
renderer source text. For every parameter a type declares, or the mapper can
emit for it, it generates the CFX twice with two different values for that one
parameter and requires the task XML to differ. Rendering is a pure function of
``params`` plus the task models, so a difference can only be caused by the probed
parameter; a parameter the serializer never reads cannot change the output, and
that missing difference is exactly the silent drop.

The two halves of "the value reaches the .cfx" are covered as a composition:
these tests prove mapper -> params -> serializer reads it, and the T3-1..T3-5
tests prove serializer -> exact XML dialect.

Evidence for the reconciled vocabulary: ``odd/notes/sqx-task-xml-dialect.md``.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from typing import Any

import pytest
from quantlab.cfx.writer import CfxWriter
from quantlab.customproject.generator import generate_cfx_archive
from quantlab.customproject.models import CustomProject, CustomProjectTask, DatabankSpec
from quantlab.exploration.param_mapper import MAPPING_RULES, TASK_DEFAULTS
from quantlab.exploration.params_schema import (
    TASK_PARAM_SCHEMAS,
    ParamSpec,
    ParamType,
    TaskType,
    coerce_params,
)

STANDARD_DATABANKS = [
    DatabankSpec(name="Results"),
    DatabankSpec(name="Last generation"),
    DatabankSpec(name="Initial population"),
    DatabankSpec(name="Strategies to improve"),
]

# Types that still carry the multi-vocabulary defect. The mapper emits
# exploration-semantic keys (``stop_loss_pips``, ``symbol``, ``risk_per_trade_usd``,
# ...) and T2 declared flat snake_case keys for them, but no renderer reads either
# set: the serializers read the harvested SQX vocabulary and take the nested
# Build/Optimize structures from ``options`` / ``moneyManagementParams``.
# Reconciling them requires the className evidence for Build's
# ``<Options><BuildTradingOptions><Params>`` and
# ``<RiskMoneyManagement><MoneyManagement><Method><Params>`` blocks.
# Tracked as T13-2 in odd/tasks/gap-remediation.md (L19b, L20).
# ``strict=True`` so removing a marker without fixing the type fails the suite.
_MULTI_VOCABULARY_TYPES = frozenset(
    {
        "Build",
        "Filtering",
        "Retest",
        "Optimize",
        "AutomaticRetest",
        "AutomaticPortfolioBuilder",
        "GoToTask",
    }
)

# Types whose schema is deliberately empty because no parameter source could be
# read (T2 scope decision, odd/tasks/gap-remediation.md L13): ApplyMassConfig
# keeps its settings inside TaskApplyMassConfig.jar and NeuralNetworkTrainer
# ships no task.xml settings. There is nothing to probe and nothing is invented.
_UNDECLARED_GAP_TYPES = frozenset({"ApplyMassConfig", "NeuralNetworkTrainer"})

# Parameters the serializer reads only in combination with another one. The probe
# isolates a single key, so without the companion a conditional read would look
# exactly like a dropped value. Each entry is the documented usage: these two
# attributes are read only once <SaveSourceCode> itself is set.
_COMPANION_KEYS: dict[str, dict[str, dict[str, Any]]] = {
    "SaveToFiles": {
        "saveSourceCodeType": {"saveSourceCode": "PROBECODE"},
        "saveSourceCodeFormat": {"saveSourceCode": "PROBECODE"},
    },
}

_XFAIL_REASON = (
    "T13-2: this type's mapped vocabulary has no reader in its serializer yet; "
    "see odd/tasks/gap-remediation.md L19b"
)

# The seven single-parameter types whose vocabulary T13 reconciled: their schema
# now declares exactly the keys their serializer reads, so an unset caller value
# must leave the task XML untouched instead of adding an element.
_RECONCILED_TYPES = frozenset(
    {
        "CreatePortfolio",
        "CustomAnalysis",
        "LoadFromFiles",
        "LogDatabankStats",
        "SaveToFiles",
        "UpdateData",
        "WaitFor",
    }
)

# Defaults the harvest documents, so ``coerce_params`` must materialise them.
_DOCUMENTED_DEFAULT_ELEMENTS: dict[str, str] = {
    "CreatePortfolio": "<MaxStrategies>100</MaxStrategies>",
    "LogDatabankStats": "<Databank>Results</Databank>",
    "UpdateData": "<Type>project</Type>",
    "WaitFor": "<Action>user</Action>",
}

# Elements that must be absent while the caller has set nothing: one per
# undocumented (``default=None``) parameter of that type.
_SILENT_WHEN_UNSET: dict[str, tuple[str, ...]] = {
    "CustomAnalysis": ("<PerStrategy1>", "<FullDatabank1>", "<Filter>"),
    "LoadFromFiles": ("<SourceDirectory>", "<UnrecognizedInstrumentAction>"),
    "SaveToFiles": ("<DestDirectorySqx>", "<SaveSourceCode"),
    "WaitFor": ("<File>",),
}


def _task_xml(type_name: str, params: dict[str, Any]) -> str:
    """Generate the CFX for a single task and return its task XML text."""
    project = CustomProject(
        name="probe",
        tasks=[
            CustomProjectTask(
                type=type_name,
                name=type_name,
                params=dict(params),
                source_databank="Results",
                target_databank="Last generation",
            )
        ],
        databanks=STANDARD_DATABANKS,
    )
    with zipfile.ZipFile(BytesIO(CfxWriter.to_bytes(generate_cfx_archive(project))), "r") as zf:
        names = sorted(n for n in zf.namelist() if n.endswith(".xml") and n != "config.xml")
        assert len(names) == 1, f"expected one task XML for {type_name}, got {names}"
        return zf.read(names[0]).decode()


def _mapper_emit_keys(type_name: str) -> set[str]:
    """Every parameter name ``ParamMapper.map`` can emit for ``type_name``."""
    emitted = set(TASK_DEFAULTS.get(type_name, {}))
    for _source_field, target_types, target_param, _transform, _condition in MAPPING_RULES:
        if type_name in target_types:
            emitted.add(target_param)
    return emitted


def _probe_values(spec: ParamSpec | None) -> tuple[Any, Any]:
    """Two values that must produce different XML for the probed parameter."""
    if spec is None:
        # Undeclared mapper keys pass through coerce_params unvalidated.
        return "PROBEALPHA", "PROBEBETA"
    if spec.param_type is ParamType.INTEGER:
        return 111111, 222222
    if spec.param_type is ParamType.FLOAT:
        return 111.25, 222.75
    if spec.param_type is ParamType.BOOLEAN:
        return False, True
    if spec.param_type is ParamType.LIST:
        return ["PROBEALPHA"], ["PROBEBETA"]
    if spec.param_type is ParamType.ENUM:
        allowed = list(spec.constraint.allowed_values or []) if spec.constraint else []
        assert len(allowed) >= 2, f"{spec.name} needs two allowed values to probe"
        return allowed[0], allowed[1]
    return "PROBEALPHA", "PROBEBETA"


def _catalog_types() -> list[str]:
    return sorted(t.value for t in TASK_PARAM_SCHEMAS)


def _parametrize(type_name: str) -> Any:
    if type_name in _MULTI_VOCABULARY_TYPES:
        return pytest.param(type_name, marks=pytest.mark.xfail(strict=True, reason=_XFAIL_REASON))
    return pytest.param(type_name)


class TestGeneratedTaskXmlIsDeterministic:
    """Guard the probe oracle: identical params must render identical XML."""

    @pytest.mark.parametrize("type_name", ["WaitFor", "Build", "Optimize"])
    def test_same_params_render_the_same_task_xml(self, type_name: str) -> None:
        params = coerce_params(TaskType(type_name), {})
        assert _task_xml(type_name, params) == _task_xml(type_name, params)


@pytest.mark.parametrize("type_name", [_parametrize(t) for t in _catalog_types()])
def test_declared_and_mapped_params_change_the_task_xml(type_name: str) -> None:
    """A parameter the serializer ignores is a parameter whose value is lost."""
    schema = TASK_PARAM_SCHEMAS[TaskType(type_name)]
    probed = list(schema) + sorted(k for k in _mapper_emit_keys(type_name) if k not in schema)
    if not probed:
        assert type_name in _UNDECLARED_GAP_TYPES, f"{type_name} declares no parameters"
        pytest.skip(f"{type_name} has no readable parameter source (documented T2 gap)")

    dropped: list[str] = []
    companions = _COMPANION_KEYS.get(type_name, {})
    for key in probed:
        low, high = _probe_values(schema.get(key))
        companion = companions.get(key, {})
        xml_low = _task_xml(
            type_name, coerce_params(TaskType(type_name), {**companion, key: low})
        )
        xml_high = _task_xml(
            type_name, coerce_params(TaskType(type_name), {**companion, key: high})
        )
        if xml_low == xml_high:
            dropped.append(key)

    assert not dropped, (
        f"{type_name} maps parameters that its serializer never reads, so the value "
        f"cannot reach the .cfx: {sorted(dropped)}"
    )


@pytest.mark.parametrize(
    ("type_name", "invented"),
    [
        ("CreatePortfolio", "portfolio_name"),
        ("CustomAnalysis", "analysis_type"),
        ("LoadFromFiles", "load_path"),
        ("LogDatabankStats", "log_details"),
        ("SaveToFiles", "save_path"),
        ("UpdateData", "update_mode"),
        ("WaitFor", "wait_seconds"),
    ],
)
def test_invented_keys_are_gone_from_schema_and_mapper(type_name: str, invented: str) -> None:
    """The T2 keys no renderer ever read must not survive as live parameters."""
    task_type = TaskType(type_name)
    assert invented not in TASK_PARAM_SCHEMAS[task_type]
    assert invented not in TASK_DEFAULTS.get(type_name, {})
    mapped = coerce_params(task_type, dict(TASK_DEFAULTS.get(type_name, {})))
    assert invented not in mapped


def test_log_databank_stats_structured_payload_reaches_the_xml() -> None:
    """``logStats`` is a list of mappings, so it is passed through undeclared.

    ``ParamType.LIST`` normalises every item with ``str()``, which would turn the
    mapping into text and make the serializer skip it, so declaring ``logStats``
    would destroy the value instead of validating it. It stays undeclared -
    ``coerce_params`` passes undeclared keys through untouched - and this pins
    that the structured payload still reaches the .cfx.
    """
    assert "logStats" not in TASK_PARAM_SCHEMAS[TaskType.LOG_DATABANK_STATS]
    params = coerce_params(
        TaskType.LOG_DATABANK_STATS,
        {"logStats": [{"type": "PROBEALPHA", "column": "PROBECOL", "conditions": "PROBECOND"}]},
    )
    xml = _task_xml("LogDatabankStats", params)
    assert 'type="PROBEALPHA"' in xml
    assert "<Column>PROBECOL</Column>" in xml
    assert "<Conditions>PROBECOND</Conditions>" in xml


class TestEvidenceBackedDefaults:
    """Only defaults the harvest documents may be materialised by coerce_params.

    ``coerce_params`` returns every declared key, so a declared default is
    written into the .cfx. A default the harvest does not document must therefore
    be ``None``: the serializer skips ``None`` instead of writing a guess.
    """

    def test_documented_defaults_are_materialised(self) -> None:
        assert coerce_params(TaskType.CREATE_PORTFOLIO, {})["maxStrategies"] == 100
        assert coerce_params(TaskType.LOG_DATABANK_STATS, {})["databank"] == "Results"
        assert coerce_params(TaskType.UPDATE_DATA, {})["type"] == "project"
        assert coerce_params(TaskType.WAIT_FOR, {})["action"] == "user"

    def test_undocumented_defaults_stay_absent_from_the_payload(self) -> None:
        assert coerce_params(TaskType.WAIT_FOR, {})["file"] is None
        assert coerce_params(TaskType.LOAD_FROM_FILES, {})["sourceDirectory"] is None
        save_to_files = coerce_params(TaskType.SAVE_TO_FILES, {})
        assert save_to_files["destDirectorySqx"] is None
        assert save_to_files["saveSourceCodeFormat"] is None


class TestUnsetParametersLeaveTheXmlUnchanged:
    """Reconciling the vocabulary must not add an element nobody set.

    Before T13 each of these types declared one invented key, so ``coerce_params``
    returned one key and no serializer read it. It now returns the harvested
    vocabulary, where every undocumented default is ``None``. The renderers read
    these keys with ``params.get(key)`` and guard on ``is not None``, so a key the
    caller never set must be skipped rather than written as a literal ``None`` (or
    crash in ``escape``). Without this pin, a guard lost inside one of the seven
    renderers silently changes every .cfx that does not set that parameter.
    """

    @pytest.mark.parametrize("type_name", sorted(_RECONCILED_TYPES))
    def test_a_type_with_no_caller_value_renders_no_literal_none(self, type_name: str) -> None:
        xml = _task_xml(type_name, coerce_params(TaskType(type_name), {}))
        assert ">None<" not in xml
        assert '="None"' not in xml

    @pytest.mark.parametrize(
        ("type_name", "element"), sorted(_DOCUMENTED_DEFAULT_ELEMENTS.items())
    )
    def test_a_documented_default_still_renders(self, type_name: str, element: str) -> None:
        xml = _task_xml(type_name, coerce_params(TaskType(type_name), {}))
        assert element in xml

    @pytest.mark.parametrize(
        ("type_name", "elements"), sorted(_SILENT_WHEN_UNSET.items())
    )
    def test_an_unset_parameter_renders_no_element(
        self, type_name: str, elements: tuple[str, ...]
    ) -> None:
        xml = _task_xml(type_name, coerce_params(TaskType(type_name), {}))
        for element in elements:
            assert element not in xml


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
