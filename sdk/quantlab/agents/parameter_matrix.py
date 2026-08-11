"""Parameter justification matrix generation (parameter-justification-matrix spec).

Generates a ``parameter_matrix`` entry list for builder / retester / optimizer
configurations, documenting WHY each parameter value was chosen. Sources are
the spec enum: ``default`` (matches the SQX template default), ``manual``
(user/agent override with a justification), ``optimized`` (chosen by the
walk-forward optimizer).

Classification rules:
- A field listed in ``rationale_overrides`` is a manual override: it needs a
  non-empty rationale (spec scenario "Manual override requires justification",
  "Matrix validation fails on missing rationale"). Blank rationale raises
  :class:`ParameterMatrixError` and blocks the run.
- Otherwise the value is compared against the SQX template default (builder)
  or the configuration class default (retester): equal → source ``default``
  with the rationale ``using SQX default``; different → the parameter deviates
  without a justification → :class:`ParameterMatrixError` (run blocked).
- Default-classified retest entries source their rationale from the shared
  educational dataset (parameter-educational-table) when a record matches by
  parameter name AND tab (REQ-205); a missing record keeps ``using SQX
  default`` and a missing dataset silently falls back — KB values are never
  invented, and a deviating value still raises.
- Optimizer runs mark every entry ``optimized`` with a rationale referencing
  the optimization objective (spec scenario "Optimizer run produces matrix").

``tab`` names mirror the ``BuildConfig`` dataclass sections (the in-repo SQX
tab classification); retest/optimize entries carry self-describing tabs.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Sequence

from quantlab.knowledge.kb.educational import (
    EducationalRecord,
    load_educational_dataset,
)
from quantlab.sqx.project_builder import (
    BuildConfig,
    get_tab_for_field,
    get_template_default,
)

DEFAULT_RATIONALE = "using SQX default"

# Retester/optimizer field inventories — these config classes are NOT
# dataclasses, so the fields are declared explicitly (mirrors the
# RetesterConfig / OptimizerConfig constructors).
RETESTER_FIELDS: tuple[str, ...] = (
    "databanks",
    "monte_carlo_runs",
    "mc_percentile",
    "walkforward_cycles",
    "min_trades",
    "confidence_level",
    "broker_profile",
    "cost_config",
)
RETESTER_DEFAULTS: dict[str, Any] = {
    "databanks": [],
    "monte_carlo_runs": 100,
    "mc_percentile": 95,
    "walkforward_cycles": 5,
    "min_trades": 30,
    "confidence_level": 0.95,
    "broker_profile": None,
    "cost_config": None,
}
OPTIMIZER_FIELDS: tuple[str, ...] = (
    "method",
    "objective",
    "walkforward_cycles",
    "population",
    "generations",
    "crossover",
    "mutation",
    "databanks",
)

RETEST_TAB = "Retest"
OPTIMIZER_TAB = "Optimization"


class ParameterMatrixError(RuntimeError):
    """A matrix entry lacks its justification — the run is blocked (REQ-1)."""


def _dataset_rationale(record: EducationalRecord) -> str:
    """Render a dataset-backed rationale referencing record fields (REQ-205).

    References the dataset record by parameter name and tab, then pulls the
    teaching fields (``what_it_does``, quant-trading role, small-account
    recommendation) — the spec scenario "Dataset record drives rationale".
    """
    parts = [
        f"KB {record.name} [{record.tab}]: {record.what_it_does}",
        record.quant_trading_role,
    ]
    if record.small_account_recommendation:
        parts.append(f"small account: {record.small_account_recommendation}")
    return " — ".join(part for part in parts if part)


def _match_dataset_record(
    records: Sequence[EducationalRecord], name: str, tab: str
) -> EducationalRecord | None:
    """Return the dataset record matching (name, tab), or ``None``.

    Matching is exact on both keys; a name with a different tab never
    matches (the entry SHALL reference the record by parameter name AND tab).
    """
    for record in records:
        if record.name == name and record.tab == tab:
            return record
    return None


def _resolve_dataset(
    dataset: Sequence[EducationalRecord | dict[str, Any]] | None,
) -> list[EducationalRecord]:
    """Normalize an injected dataset; lazy-load from the KB lake when ``None``.

    The dataset is a runtime load from the lake (never a static import).
    ``None`` triggers :func:`load_educational_dataset` which silently
    returns ``[]`` when the dataset is missing — callers keep their
    existing fallback behavior.
    """
    if dataset is None:
        return load_educational_dataset()
    return [
        rec
        if isinstance(rec, EducationalRecord)
        else EducationalRecord.model_validate(rec)
        for rec in dataset
    ]


def _entry(
    *,
    parameter: str,
    value: Any,
    rationale: str,
    source: str,
    confidence: float,
    tab: str,
    hypothesis_ref: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "tab": tab,
        "parameter": parameter,
        "value": value,
        "rationale": rationale,
        "source": source,
        "confidence": confidence,
    }
    if hypothesis_ref:
        entry["hypothesis_ref"] = hypothesis_ref
    return entry


def generate_parameter_matrix(
    build_config: BuildConfig | None,
    rationale_overrides: dict[str, str] | None = None,
    hypothesis_ref: str | None = None,
) -> list[dict[str, Any]]:
    """Generate matrix entries for a BuildConfig (spec REQ-1 scenarios).

    Args:
        build_config: The builder configuration; ``None`` yields an empty
            matrix.
        rationale_overrides: Manual justifications keyed by field name.
        hypothesis_ref: Cross-reference to the active research hypothesis,
            propagated to every entry when set.

    Returns:
        List of matrix entries (parameter/value/rationale/source/confidence,
        plus ``tab`` and optional ``hypothesis_ref``).

    Raises:
        ParameterMatrixError: When a manual override lacks a rationale, or a
            value deviates from the SQX template default without one (the run
            is blocked from advancing).
    """
    if build_config is None:
        return []
    overrides = rationale_overrides or {}
    entries: list[dict[str, Any]] = []
    for field in dataclasses.fields(build_config):
        value = getattr(build_config, field.name)
        if value is None:
            continue
        if field.name in overrides:
            rationale = (overrides[field.name] or "").strip()
            if not rationale:
                raise ParameterMatrixError(
                    f"parameter '{field.name}' has an empty rationale — "
                    "manual overrides must be justified (REQ-1)"
                )
            entries.append(
                _entry(
                    parameter=field.name,
                    value=value,
                    rationale=rationale,
                    source="manual",
                    confidence=0.7,
                    tab=get_tab_for_field(field.name),
                    hypothesis_ref=hypothesis_ref,
                )
            )
            continue
        default = get_template_default(field.name)
        if default is not None and value == default:
            entries.append(
                _entry(
                    parameter=field.name,
                    value=value,
                    rationale=DEFAULT_RATIONALE,
                    source="default",
                    confidence=0.9,
                    tab=get_tab_for_field(field.name),
                    hypothesis_ref=hypothesis_ref,
                )
            )
            continue
        raise ParameterMatrixError(
            f"parameter '{field.name}' ({value!r}) deviates from the SQX "
            f"template default ({default!r}) without a rationale — provide "
            f"rationale_overrides['{field.name}'] to justify it (REQ-1)"
        )
    return entries


def generate_run_matrix(
    config: Any,
    *,
    run_type: str,
    rationale_overrides: dict[str, str] | None = None,
    dataset: Sequence[EducationalRecord | dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate matrix entries for a retester or optimizer configuration.

    Args:
        config: The ``RetesterConfig`` or ``OptimizerConfig`` instance.
        run_type: ``"retest"`` or ``"optimize"``.
        rationale_overrides: Manual justifications for retest parameters that
            deviate from their configuration defaults.
        dataset: Optional shared educational dataset (records or dicts) for
            the REQ-205 rationale hook. When ``None`` it is lazy-loaded from
            the KB lake at runtime (see :func:`load_educational_dataset`);
            a missing dataset silently falls back to the existing sources.

    Returns:
        Matrix entries; retest entries classify against the config defaults
        (default-classified entries source their rationale from the
        educational dataset record matched by name+tab when one exists),
        optimizer entries are marked ``optimized`` referencing the objective.

    Raises:
        ParameterMatrixError: A retest parameter deviates from its default
            without a rationale — the dataset never justifies a deviation.
        ValueError: Unknown ``run_type``.
    """
    if run_type == "optimize":
        objective = getattr(config, "objective", "SharpeRatio")
        return [
            _entry(
                parameter=field,
                value=getattr(config, field),
                rationale=f"optimization objective: {objective}",
                source="optimized",
                confidence=0.95,
                tab=OPTIMIZER_TAB,
            )
            for field in OPTIMIZER_FIELDS
            if getattr(config, field) is not None
        ]
    if run_type == "retest":
        overrides = rationale_overrides or {}
        records = _resolve_dataset(dataset)
        entries: list[dict[str, Any]] = []
        for field in RETESTER_FIELDS:
            value = getattr(config, field)
            if value is None:
                continue
            if field in overrides:
                rationale = (overrides[field] or "").strip()
                if not rationale:
                    raise ParameterMatrixError(
                        f"parameter '{field}' has an empty rationale — manual "
                        "overrides must be justified (REQ-1)"
                    )
                entries.append(
                    _entry(
                        parameter=field,
                        value=value,
                        rationale=rationale,
                        source="manual",
                        confidence=0.7,
                        tab=RETEST_TAB,
                    )
                )
                continue
            default = RETESTER_DEFAULTS.get(field)
            if value == default:
                record = _match_dataset_record(records, field, RETEST_TAB)
                rationale = (
                    _dataset_rationale(record)
                    if record is not None
                    else DEFAULT_RATIONALE
                )
                entries.append(
                    _entry(
                        parameter=field,
                        value=value,
                        rationale=rationale,
                        source="default",
                        confidence=0.9,
                        tab=RETEST_TAB,
                    )
                )
                continue
            raise ParameterMatrixError(
                f"parameter '{field}' ({value!r}) deviates from the retest "
                f"default ({default!r}) without a rationale — provide "
                f"rationale_overrides['{field}'] to justify it (REQ-1)"
            )
        return entries
    raise ValueError(f"unknown run_type: {run_type!r} (expected 'retest' or 'optimize')")
