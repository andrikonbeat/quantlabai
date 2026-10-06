"""CFX patcher — validate-then-apply mutation engine for CFX archives.

Provides a high-level API for applying typed patch instructions to a CfxArchive
with atomic semantics: all instructions are validated before any mutation occurs.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any

from quantlab.cfx.errors import CfxParseError
from quantlab.cfx.models import (
    AddAdvancedRankingConditionInstruction,
    AddRankingConditionInstruction,
    AddTimeframeInstruction,
    AdvancedRankingCondition,
    AutomaticPortfolioBuilderConfig,
    ColumnValue,
    CrossChecksConfig,
    CrossChecksGeneric,
    DatabanksConfig,
    DataRangeParts,
    DisableBlockInstruction,
    EnableBlockInstruction,
    EnableCrosscheckInstruction,
    OptimizationConfig,
    OptimizationParametersConfig,
    PatchInstruction,
    PortfolioSettingsConfig,
    RankingsConfig,
    RetesterDataConfig,
    SetAdvancedRankingsInstruction,
    SetAutomaticPortfolioBuilderInstruction,
    SetCrossChecksInstruction,
    SetDatabanksInstruction,
    SetDataRangePartsInstruction,
    SetDateRangeInstruction,
    SetGeneticInstruction,
    SetMarketInstruction,
    SetOptimizationInstruction,
    SetOptimizationParametersInstruction,
    SetPortfolioSettingsInstruction,
    SetRankingsInstruction,
    SetRetesterDataInstruction,
    SettingsSection,
    SetWalkForwardInstruction,
    WalkForwardConfig,
)

if TYPE_CHECKING:
    from quantlab.cfx.models import BuildTask, CfxArchive


class ValidationError(CfxParseError):
    """Raised when a patch instruction fails validation."""


# Attribute emission order for advanced ranking filters. The order reproduces a
# real SQX 144/2953 Retester CFX export. Every attribute is always emitted, but
# the justification is not simply "SQX does the same": SQX writes the full set
# on <Column-Value> and only ``use`` on <Condition>, leaving the rest to reader
# defaults. Writing them explicitly is equivalent while each carries that
# default, and tests/phase4/test_project_builder_golden_rankings.py asserts
# exactly that against the real export.
_CONDITION_ATTRS: tuple[tuple[str, str], ...] = (
    ("result_type", "resultType"),
    ("sample_type", "sampleType"),
    ("direction", "direction"),
    ("pct_ratio", "pctRatio"),
    ("confidence_level", "confidenceLevel"),
    ("market", "market"),
    ("pl_type", "plType"),
    ("subresult", "subresult"),
    ("class_", "class"),
    ("name", "name"),
)

_COLUMN_VALUE_ATTRS: tuple[tuple[str, str], ...] = (
    ("column", "column"),
    ("column_type", "columnType"),
    ("format", "format"),
    ("result_type", "resultType"),
    ("direction", "direction"),
    ("sample_type", "sampleType"),
    ("pl_type", "plType"),
    ("confidence_level", "confidenceLevel"),
    ("market", "market"),
    ("subresult", "subresult"),
    ("pct_ratio", "pctRatio"),
    ("class_", "class"),
    ("name", "name"),
)


def _render_attributes(source: Any, spec: tuple[tuple[str, str], ...]) -> str:
    """Render ``spec`` fields of ``source`` as space-separated XML attributes.

    ``None`` values are skipped so optional attributes stay absent. Booleans
    render lowercase to match SQX's ``true``/``false`` convention.
    """
    rendered: list[str] = []
    for field_name, xml_name in spec:
        value = getattr(source, field_name)
        if value is None:
            continue
        if isinstance(value, bool):
            value = str(value).lower()
        rendered.append(f'{xml_name}="{value}"')
    return " ".join(rendered)


def build_conditions_xml(
    conditions: list[AdvancedRankingCondition], indent: str = "  "
) -> str:
    """Render ``conditions`` as the inner ``<Conditions>`` block of a Rankings section.

    Every attribute is emitted, defaults included. SQX itself is not
    consistent here: a real 144/2953 Retester CFX writes the full set on
    ``<Column-Value>`` but only ``use`` on ``<Condition>``, leaving the rest
    to the reader's defaults. Writing them explicitly is equivalent while
    each extra attribute carries that same default, and
    ``tests/phase4/test_project_builder_golden_rankings.py`` asserts exactly
    that against the real export. Only the genuinely optional ``class`` and
    ``name`` attributes are omitted.

    Public because two entry points need this exact dialect: the patcher
    (instruction-driven edits) and the custom-project renderers (task-driven
    builds). Re-verifying it twice would be a worse trade than one renderer.
    """
    lines = [f"{indent}<Conditions>"]
    for cond in conditions:
        use_attr = f'use="{str(cond.use).lower()}"'
        attrs = " ".join(
            part
            for part in (use_attr, _render_attributes(cond, _CONDITION_ATTRS))
            if part
        )
        lines.append(f"{indent}  <Condition {attrs}>")
        for cv in cond.column_values:
            cv_attrs = _render_attributes(cv, _COLUMN_VALUE_ATTRS)
            lines.append(f"{indent}    <Column-Value {cv_attrs} />")
        lines.append(f"{indent}  </Condition>")
    lines.append(f"{indent}</Conditions>")
    return "\n".join(lines)


def build_advanced_rankings_xml(conditions: list[AdvancedRankingCondition]) -> str:
    """Build a complete ``<Rankings>`` element carrying nested ``<Conditions>``."""
    return "\n".join(["<Rankings>", build_conditions_xml(conditions), "</Rankings>"])


# Attribute names for the generic CrossChecks children, in both dialects the
# reader accepts: the attribute form ``<WalkForward enabled= cycles=/>`` that
# ``to_xml()`` synthesises, and the nested-child form
# ``<WalkForward><Use/><Cycles/></WalkForward>`` that older SQX blocks use.
_GENERIC_CROSS_CHECKS_ATTRS: dict[str, tuple[tuple[str, str], ...]] = {
    "MonteCarlo": (
        ("enabled", "mc_enabled"),
        ("runs", "mc_runs"),
        ("percentile", "mc_percentile"),
    ),
    "WalkForward": (("enabled", "wf_enabled"), ("cycles", "wf_cycles")),
}

# Nested-child spelling of the same fields.
_GENERIC_CROSS_CHECKS_CHILDREN: dict[str, tuple[tuple[str, str], ...]] = {
    "MonteCarlo": (("Use", "mc_enabled"),),
    "WalkForward": (("Use", "wf_enabled"), ("Cycles", "wf_cycles")),
}


def _sync_generic_cross_checks_xml(generic: CrossChecksGeneric) -> None:
    """Write the typed ``generic`` fields back into the kept source markup.

    ``CrossChecksConfig.from_xml`` parks the recognised children verbatim in
    ``CrossChecksGeneric.raw_xml`` so ``to_xml()`` can re-emit them without
    rewriting the dialect. That fidelity cuts the other way too: a typed-field
    mutation never reaches the output, because ``to_xml()`` prefers the stored
    markup over the fields. Mutating ``mc_enabled`` / ``wf_enabled`` /
    ``wf_cycles`` therefore has to be mirrored into that markup or the write is
    lost.

    The existing element form is preserved — attributes stay attributes, nested
    children stay nested children — because changing the form would rewrite the
    dialect. A child that is absent is appended in the synthesised attribute
    form, which is what a caller enabling a cross-check for the first time
    needs. Values other than the three patched fields (``runs``, ``percentile``)
    are left untouched.
    """
    if not generic.raw_xml:
        # No stored markup: to_xml() synthesises from the typed fields already.
        return
    wrapper = f"<CrossChecks>{generic.raw_xml}</CrossChecks>"
    try:
        root = ET.fromstring(wrapper)
    except ET.ParseError:
        # Unparseable stored markup is emitted verbatim; leave it untouched
        # rather than risk rewriting it into something else.
        return

    for tag, attrs in _GENERIC_CROSS_CHECKS_ATTRS.items():
        child = root.find(tag)
        if child is None:
            continue
        if child.attrib:
            for attr, field in attrs:
                child.set(attr, _cross_check_value(getattr(generic, field)))
            continue
        # Nested-child dialect: patch the matching sub-elements by name.
        for name, field in _GENERIC_CROSS_CHECKS_CHILDREN[tag]:
            sub = child.find(name)
            if sub is not None:
                sub.text = _cross_check_value(getattr(generic, field))

    for tag, attrs in _GENERIC_CROSS_CHECKS_ATTRS.items():
        if root.find(tag) is None:
            ET.SubElement(
                root,
                tag,
                {
                    attr: _cross_check_value(getattr(generic, field))
                    for attr, field in attrs
                },
            )

    # Drop the wrapper: only the inner children are stored. Tails are cleared
    # first so the indentation whitespace of the original markup does not
    # accumulate into blank lines between the re-serialised children.
    parts = []
    for child in root:
        child.tail = None
        parts.append(ET.tostring(child, encoding="unicode").strip())
    generic.raw_xml = "\n".join(parts)


def _cross_check_value(value: object) -> str:
    """Render a typed CrossChecks field the way the markup spells it."""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


class CfxPatcher:
    """Mutates a CfxArchive via validated instruction sequences.

    Semantics:
    - Holds an internal reference to the same CfxArchive object (not a copy).
    - apply() validates ALL instructions first, then mutates in sequence.
    - On validation failure: raises ValidationError, NO mutations applied.
    - Returns self for method chaining.

    Example:
        patcher = CfxPatcher(archive)
        patcher.apply([
            SetMarketInstruction(symbol="EURUSD"),
            AddTimeframeInstruction(timeframe="H1"),
        ])
    """

    def __init__(self, archive: CfxArchive) -> None:
        self._archive = archive
        # We work on the first task (config or first project task)
        self._task = self._get_primary_task(archive)

    @property
    def archive(self) -> CfxArchive:
        return self._archive

    @property
    def task(self) -> BuildTask:
        return self._task

    @staticmethod
    def _get_primary_task(archive: CfxArchive) -> BuildTask:
        """Get the primary BuildTask to mutate (first task in config/project)."""
        config = archive.config
        if hasattr(config, "task"):
            # CfxConfig has a single task
            return config.task
        elif hasattr(config, "tasks") and config.tasks:
            # CfxProject has multiple tasks - use the first one
            return next(iter(config.tasks.values()))
        # Fallback: empty task
        from quantlab.cfx.models import BuildTask

        return BuildTask()

    # ── Validation ────────────────────────────────────────────────────

    def validate_all(self, instructions: list[PatchInstruction]) -> None:
        """Validate all instructions before any mutation.

        Raises ValidationError on the FIRST invalid instruction.
        No mutations are applied if validation fails.
        """
        for instruction in instructions:
            self._validate_instruction(instruction)

    def _validate_instruction(self, instruction: PatchInstruction) -> None:
        """Validate a single instruction against the current archive state."""
        validator_map = {
            "set_market": self._validate_set_market,
            "add_timeframe": self._validate_add_timeframe,
            "enable_block": self._validate_enable_block,
            "disable_block": self._validate_disable_block,
            "set_genetic": self._validate_set_genetic,
            "set_date_range": self._validate_set_date_range,
            "add_ranking_condition": self._validate_add_ranking_condition,
            "enable_crosscheck": self._validate_enable_crosscheck,
            # Phase 4 validators
            "set_automatic_portfolio_builder": self._validate_set_automatic_portfolio_builder,
            "set_portfolio_settings": self._validate_set_portfolio_settings,
            "set_optimization": self._validate_set_optimization,
            "set_optimization_parameters": self._validate_set_optimization_parameters,
            "set_walkforward": self._validate_set_walkforward,
            "set_databanks": self._validate_set_databanks,
            "set_rankings": self._validate_set_rankings,
            "set_crosschecks": self._validate_set_crosschecks,
            "set_retester_data": self._validate_set_retester_data,
            "set_advanced_rankings": self._validate_set_advanced_rankings,
            "add_advanced_ranking_condition": self._validate_add_advanced_ranking_condition,
            "set_data_range_parts": self._validate_set_data_range_parts,
        }

        validator = validator_map.get(instruction.instruction_type)
        if validator is None:
            raise ValidationError(
                f"Unknown instruction type: {instruction.instruction_type}"
            )

        validator(instruction)  # type: ignore[operator]

    def _validate_set_market(self, instruction: SetMarketInstruction) -> None:
        if not instruction.symbol or not instruction.symbol.strip():
            raise ValidationError("SetMarketInstruction: symbol must not be empty")

    def _validate_add_timeframe(self, instruction: AddTimeframeInstruction) -> None:
        supported = {"M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN"}
        if instruction.timeframe not in supported:
            raise ValidationError(
                f"AddTimeframeInstruction: unsupported timeframe '{instruction.timeframe}'. "
                f"Supported: {', '.join(sorted(supported))}"
            )

    def _validate_enable_block(self, instruction: EnableBlockInstruction) -> None:
        if not instruction.block_key or not instruction.block_key.strip():
            raise ValidationError("EnableBlockInstruction: block_key must not be empty")
        if instruction.weight < 0:
            raise ValidationError("EnableBlockInstruction: weight must be non-negative")

    def _validate_disable_block(self, instruction: DisableBlockInstruction) -> None:
        if not instruction.block_key or not instruction.block_key.strip():
            raise ValidationError(
                "DisableBlockInstruction: block_key must not be empty"
            )

    def _validate_set_genetic(self, instruction: SetGeneticInstruction) -> None:
        if instruction.generations <= 0:
            raise ValidationError("SetGeneticInstruction: generations must be positive")
        if instruction.population <= 0:
            raise ValidationError("SetGeneticInstruction: population must be positive")

    def _validate_set_date_range(self, instruction: SetDateRangeInstruction) -> None:
        # Basic format validation - accept YYYY.MM.DD or epoch ms
        for field_name, value in [
            ("start", instruction.start),
            ("end", instruction.end),
        ]:
            if not value or not value.strip():
                raise ValidationError(
                    f"SetDateRangeInstruction: {field_name} must not be empty"
                )

    def _validate_add_ranking_condition(
        self, instruction: AddRankingConditionInstruction
    ) -> None:
        valid_operators = {">", ">=", "<", "<=", "==", "!="}
        if instruction.operator not in valid_operators:
            raise ValidationError(
                f"AddRankingConditionInstruction: invalid operator '{instruction.operator}'. "
                f"Valid: {', '.join(sorted(valid_operators))}"
            )
        if not instruction.metric or not instruction.metric.strip():
            raise ValidationError(
                "AddRankingConditionInstruction: metric must not be empty"
            )

    def _validate_enable_crosscheck(
        self, instruction: EnableCrosscheckInstruction
    ) -> None:
        if instruction.wf_cycles <= 0:
            raise ValidationError(
                "EnableCrosscheckInstruction: wf_cycles must be positive"
            )

    # ── Phase 4 Validators ────────────────────────────────────────────

    def _validate_set_automatic_portfolio_builder(
        self, instruction: SetAutomaticPortfolioBuilderInstruction
    ) -> None:
        if instruction.generations <= 0:
            raise ValidationError(
                "SetAutomaticPortfolioBuilderInstruction: generations must be positive"
            )
        if instruction.population <= 0:
            raise ValidationError(
                "SetAutomaticPortfolioBuilderInstruction: population must be positive"
            )
        if instruction.min_strategies <= 0:
            raise ValidationError(
                "SetAutomaticPortfolioBuilderInstruction: min_strategies must be positive"
            )
        if (
            instruction.max_strategies is not None
            and instruction.max_strategies < instruction.min_strategies
        ):
            raise ValidationError(
                "SetAutomaticPortfolioBuilderInstruction: max_strategies must be >= min_strategies"
            )
        if not instruction.fitness or not instruction.fitness.strip():
            raise ValidationError(
                "SetAutomaticPortfolioBuilderInstruction: fitness must not be empty"
            )

    def _validate_set_portfolio_settings(
        self, instruction: SetPortfolioSettingsInstruction
    ) -> None:
        if instruction.weight_constraints is not None:
            for sid, constraint in instruction.weight_constraints.items():  # noqa: PERF102
                if not sid or not sid.strip():
                    raise ValidationError(
                        "SetPortfolioSettingsInstruction: strategy_id must not be empty"
                    )

    def _validate_set_optimization(
        self, instruction: SetOptimizationInstruction
    ) -> None:
        valid_methods = {"Genetic", "BruteForce", "Grid"}
        if instruction.method not in valid_methods:
            raise ValidationError(
                f"SetOptimizationInstruction: invalid method '{instruction.method}'. "
                f"Valid: {', '.join(sorted(valid_methods))}"
            )
        if (
            not instruction.objective_function
            or not instruction.objective_function.strip()
        ):
            raise ValidationError(
                "SetOptimizationInstruction: objective_function must not be empty"
            )
        if instruction.walkforward_cycles <= 0:
            raise ValidationError(
                "SetOptimizationInstruction: walkforward_cycles must be positive"
            )
        if not (0 < instruction.walkforward_oot_ratio < 1):
            raise ValidationError(
                "SetOptimizationInstruction: walkforward_oot_ratio must be in (0, 1)"
            )

    def _validate_set_optimization_parameters(
        self, instruction: SetOptimizationParametersInstruction
    ) -> None:
        if not instruction.parameters:
            raise ValidationError(
                "SetOptimizationParametersInstruction: parameters must not be empty"
            )
        for param_name, param_range in instruction.parameters.items():
            if not param_name or not param_name.strip():
                raise ValidationError(
                    "SetOptimizationParametersInstruction: parameter name must not be empty"
                )
            required_keys = {"min", "max", "step"}
            if not all(k in param_range for k in required_keys):
                raise ValidationError(
                    f"SetOptimizationParametersInstruction: parameter '{param_name}' must have min, max, step"
                )
            if param_range["step"] <= 0:
                raise ValidationError(
                    f"SetOptimizationParametersInstruction: parameter '{param_name}' step must be positive"
                )
            if param_range["max"] < param_range["min"]:
                raise ValidationError(
                    f"SetOptimizationParametersInstruction: parameter '{param_name}' max must be >= min"
                )

    def _validate_set_walkforward(self, instruction: SetWalkForwardInstruction) -> None:
        if instruction.cycles <= 0:
            raise ValidationError("SetWalkForwardInstruction: cycles must be positive")
        if not (0 < instruction.oot_ratio < 1):
            raise ValidationError(
                "SetWalkForwardInstruction: oot_ratio must be in (0, 1)"
            )

    def _validate_set_databanks(self, instruction: SetDatabanksInstruction) -> None:
        if not instruction.databanks:
            raise ValidationError(
                "SetDatabanksInstruction: databanks must not be empty"
            )
        import re

        pattern = re.compile(r"^[A-Z]{6}_[A-Z]\d+$")
        for db in instruction.databanks:
            if not pattern.match(db):
                raise ValidationError(
                    f"SetDatabanksInstruction: invalid databank name '{db}'. "
                    f"Must match ^[A-Z]{{6}}_[A-Z]\\d+$ (e.g., EURUSD_H1)"
                )

    def _validate_set_rankings(self, instruction: SetRankingsInstruction) -> None:
        if not instruction.metrics:
            raise ValidationError("SetRankingsInstruction: metrics must not be empty")
        if instruction.min_trades <= 0:
            raise ValidationError("SetRankingsInstruction: min_trades must be positive")

    def _validate_set_crosschecks(self, instruction: SetCrossChecksInstruction) -> None:
        if instruction.mc_enabled and instruction.mc_runs <= 0:
            raise ValidationError(
                "SetCrossChecksInstruction: mc_runs must be positive when mc_enabled"
            )
        if instruction.mc_enabled and not (1 <= instruction.mc_percentile <= 99):
            raise ValidationError(
                "SetCrossChecksInstruction: mc_percentile must be in [1, 99]"
            )
        if instruction.wf_enabled and instruction.wf_cycles <= 0:
            raise ValidationError(
                "SetCrossChecksInstruction: wf_cycles must be positive when wf_enabled"
            )
        if not (0.5 < instruction.confidence_level < 0.99):
            raise ValidationError(
                "SetCrossChecksInstruction: confidence_level must be in (0.5, 0.99)"
            )

    def _validate_set_retester_data(
        self, instruction: SetRetesterDataInstruction
    ) -> None:
        if not instruction.databanks:
            raise ValidationError(
                "SetRetesterDataInstruction: databanks must not be empty"
            )
        import re

        pattern = re.compile(r"^[A-Z]{6}_[A-Z]\d+$")
        for db in instruction.databanks:
            if not pattern.match(db):
                raise ValidationError(
                    f"SetRetesterDataInstruction: invalid databank name '{db}'"
                )
        if instruction.monte_carlo_runs <= 0:
            raise ValidationError(
                "SetRetesterDataInstruction: monte_carlo_runs must be positive"
            )
        if instruction.walkforward_cycles <= 0:
            raise ValidationError(
                "SetRetesterDataInstruction: walkforward_cycles must be positive"
            )
        if not (0.5 < instruction.confidence_level < 0.99):
            raise ValidationError(
                "SetRetesterDataInstruction: confidence_level must be in (0.5, 0.99)"
            )
        if instruction.min_trades <= 0:
            raise ValidationError(
                "SetRetesterDataInstruction: min_trades must be positive"
            )
        if not (1 <= instruction.mc_percentile <= 99):
            raise ValidationError(
                "SetRetesterDataInstruction: mc_percentile must be in [1, 99]"
            )

    def _validate_set_advanced_rankings(
        self, instruction: SetAdvancedRankingsInstruction
    ) -> None:
        if not instruction.conditions:
            raise ValidationError(
                "SetAdvancedRankingsInstruction: conditions must not be empty"
            )

    def _validate_add_advanced_ranking_condition(
        self, instruction: AddAdvancedRankingConditionInstruction
    ) -> None:
        if not instruction.condition.column_values:
            raise ValidationError(
                "AddAdvancedRankingConditionInstruction: condition must have at least one ColumnValue"
            )

    def _validate_set_data_range_parts(
        self, instruction: SetDataRangePartsInstruction
    ) -> None:
        # A ratio of 0 or >= 1 is not a split; accepting it would let a caller
        # silently emit a degenerate range-parts block into the CFX.
        for field_name in ("validation_ratio", "test_ratio"):
            ratio = getattr(instruction.parts, field_name)
            if ratio is not None and not (0 < ratio < 1):
                raise ValidationError(
                    f"SetDataRangePartsInstruction: {field_name} must be in (0, 1) exclusive"
                )

    # ── Application ───────────────────────────────────────────────────

    def apply(self, instructions: list[PatchInstruction]) -> CfxPatcher:
        """Validate all instructions, then apply them in order.

        Args:
            instructions: List of PatchInstruction models to apply.

        Returns:
            self (for chaining)

        Raises:
            ValidationError: If any instruction fails validation. No mutations applied.
        """
        # Phase 1: Validate ALL instructions
        self.validate_all(instructions)

        # Phase 2: Apply all mutations (validated, so should not fail)
        for instruction in instructions:
            self._apply_instruction(instruction)

        return self

    def _apply_instruction(self, instruction: PatchInstruction) -> None:
        """Apply a single validated instruction."""
        applier_map = {
            "set_market": self._apply_set_market,
            "add_timeframe": self._apply_add_timeframe,
            "enable_block": self._apply_enable_block,
            "disable_block": self._apply_disable_block,
            "set_genetic": self._apply_set_genetic,
            "set_date_range": self._apply_set_date_range,
            "add_ranking_condition": self._apply_add_ranking_condition,
            "enable_crosscheck": self._apply_enable_crosscheck,
            # Phase 4
            "set_automatic_portfolio_builder": self._apply_set_automatic_portfolio_builder,
            "set_portfolio_settings": self._apply_set_portfolio_settings,
            "set_optimization": self._apply_set_optimization,
            "set_optimization_parameters": self._apply_set_optimization_parameters,
            "set_walkforward": self._apply_set_walkforward,
            "set_databanks": self._apply_set_databanks,
            "set_rankings": self._apply_set_rankings,
            "set_crosschecks": self._apply_set_crosschecks,
            "set_retester_data": self._apply_set_retester_data,
            "set_advanced_rankings": self._apply_set_advanced_rankings,
            "add_advanced_ranking_condition": self._apply_add_advanced_ranking_condition,
            "set_data_range_parts": self._apply_set_data_range_parts,
        }

        applier = applier_map.get(instruction.instruction_type)
        if applier is None:
            raise ValidationError(
                f"Unknown instruction type: {instruction.instruction_type}"
            )

        applier(instruction)  # type: ignore[operator]

    def _apply_set_market(self, instruction: SetMarketInstruction) -> None:
        """Set market symbol in Data section and Resources/Symbols."""
        symbol = instruction.symbol.strip()

        # Create Data section if it doesn't exist
        if self._task.data is None:
            self._task.data = SettingsSection(
                name="Data",
                settings={},
            )

        # Update Data section → Symbol setting
        self._task.data.settings["Symbol@symbol"] = symbol
        self._task.data.settings["Symbol@name"] = symbol

        # Update Resources/Symbols section (raw XML) - would need XML parsing
        # For now, update SettingsSection if it exists
        if self._task.resources:
            # Resources is a complex section with raw_xml - we'd need to parse/modify
            pass

    def _apply_add_timeframe(self, instruction: AddTimeframeInstruction) -> None:
        """Add timeframe to Data/Timeframes and WhatToBuild/Timeframes."""
        tf = instruction.timeframe

        # Data section → Timeframes
        if self._task.data:
            # Find existing timeframe keys and add new one
            existing_keys = [
                k for k in self._task.data.settings.keys() if k.startswith("Timeframe")  # noqa: SIM118
            ]
            next_idx = len(existing_keys) + 1
            self._task.data.settings[f"Timeframe{next_idx}@value"] = tf

        # WhatToBuild section → Timeframes
        if self._task.what_to_build:
            existing_keys = [
                k
                for k in self._task.what_to_build.settings.keys()  # noqa: SIM118
                if k.startswith("Timeframe")
            ]
            next_idx = len(existing_keys) + 1
            self._task.what_to_build.settings[f"Timeframe{next_idx}@value"] = tf

    def _apply_enable_block(self, instruction: EnableBlockInstruction) -> None:
        """Enable a building block with weight."""
        # This would modify the Blocks complex section (raw_xml)
        # For now, track in a separate structure or update SettingsSection
        if self._task.blocks:
            # Would need to parse/modify raw_xml
            pass

    def _apply_disable_block(self, instruction: DisableBlockInstruction) -> None:
        """Disable a building block."""
        if self._task.blocks:
            # Would need to parse/modify raw_xml
            pass

    def _apply_set_genetic(self, instruction: SetGeneticInstruction) -> None:
        """Configure genetic optimisation parameters."""
        if self._task.what_to_build:
            self._task.what_to_build.settings["UseGenetic@value"] = str(
                instruction.enabled
            ).lower()
            self._task.what_to_build.settings["Generations@value"] = str(
                instruction.generations
            )
            self._task.what_to_build.settings["Population@value"] = str(
                instruction.population
            )

    def _apply_set_date_range(self, instruction: SetDateRangeInstruction) -> None:
        """Set date range with domain-specific format mapping.

        Data, Setups → YYYY.MM.DD (string)
        Resources, Symbols, Sessions → epoch milliseconds (int)
        """
        start = instruction.start.strip()
        end = instruction.end.strip()

        # Parse dates to determine format
        # If format contains dots (YYYY.MM.DD), use as-is for Data/Setups
        # Otherwise assume epoch ms or convert

        # Data section → FromDate/ToDate (YYYY.MM.DD)
        if self._task.data:
            self._task.data.settings["FromDate@value"] = self._format_date_for_section(
                start, "Data"
            )
            self._task.data.settings["ToDate@value"] = self._format_date_for_section(
                end, "Data"
            )

        # Resources/Symbols/Sessions → epoch ms (handled via raw_xml for complex sections)
        # For SettingsSection, we store the epoch format
        if self._task.resources:
            # Would need raw_xml parsing
            pass

    def _format_date_for_section(self, date_str: str, section_type: str) -> str:
        """Format date according to section domain.

        Data, Setups: YYYY.MM.DD
        Resources, Symbols, Sessions: epoch milliseconds
        """
        # If already in YYYY.MM.DD format, use as-is for Data/Setups
        if section_type in ("Data", "Setups"):
            if "." in date_str and len(date_str.split(".")[0]) == 4:
                return date_str  # Already YYYY.MM.DD
            # Try to parse and convert
            # For now, return as-is
            return date_str
        else:
            # Resources/Symbols/Sessions → epoch ms
            # Would need date parsing logic here parsing
            return date_str

    def _apply_add_ranking_condition(
        self, instruction: AddRankingConditionInstruction
    ) -> None:
        """Add a ranking condition to Rankings/Acceptance.

        The flat lane is created on demand. This applier used to be guarded by
        ``if self._task.rankings``, so on any task that did not pre-seed the
        section the instruction was discarded with no error and no trace. The
        phase4 retester template seeds only the complex ``rankings_section`` lane,
        so a mixed simple + advanced build silently lost its simple half. Both
        lanes now merge losslessly in the writer, so creating the section is
        enough; behaviour is unchanged whenever the lane already exists.
        """
        if self._task.rankings is None:
            self._task.rankings = SettingsSection(name="Rankings", settings={})
        # Find next available criterion index - count unique criterion prefixes
        existing_prefixes = set()
        for k in self._task.rankings.settings.keys():  # noqa: SIM118
            if k.startswith("Criterion"):
                # Extract the prefix (e.g., "Criterion1" from "Criterion1@metric")
                prefix = k.split("@")[0]
                existing_prefixes.add(prefix)
        next_idx = len(existing_prefixes) + 1
        prefix = f"Criterion{next_idx}"
        self._task.rankings.settings[f"{prefix}@metric"] = instruction.metric
        self._task.rankings.settings[f"{prefix}@operator"] = instruction.operator
        # Format value: remove .0 for whole numbers
        value = instruction.value
        if isinstance(value, float) and value == int(value):
            value = int(value)
        self._task.rankings.settings[f"{prefix}@value"] = str(value)

    def _apply_enable_crosscheck(
        self, instruction: EnableCrosscheckInstruction
    ) -> None:
        """Enable walk-forward and Monte-Carlo cross-checks.

        This applier used to be guarded by ``if self._task.cross_checks``, so on
        a real SQX archive the instruction was discarded with no error and no
        trace: the reader populates ``cross_checks_section`` and leaves the flat
        ``cross_checks`` lane empty, so the guard was false on precisely the
        files that matter.

        Two lanes, chosen by what the task actually carries:

        * ``cross_checks_section`` in the **generic** dialect owns typed
          ``mc_enabled`` / ``wf_enabled`` / ``wf_cycles`` fields, so those are
          updated — mirroring ``_apply_set_crosschecks`` and
          ``_apply_add_ranking_condition``;
        * anything else (no section, an unrecognised dialect, or no typed
          generic model) creates the flat lane on demand and fills it with the
          same keys it always used.

        The typed fields are not write-only: ``CrossChecksGeneric.to_xml()``
        re-emits the source children it kept verbatim in ``raw_xml``, so the
        values are synced back into that markup as well. Without that sync the
        typed fields would change while the emitted document did not, trading
        one silent discard for another.
        """
        section = self._task.cross_checks_section
        if (
            section is not None
            and section.dialect == "generic"
            and section.generic is not None
        ):
            generic = section.generic
            generic.mc_enabled = instruction.mc_enabled
            generic.wf_enabled = instruction.wf_enabled
            generic.wf_cycles = instruction.wf_cycles
            _sync_generic_cross_checks_xml(generic)
            return

        if self._task.cross_checks is None:
            self._task.cross_checks = SettingsSection(name="CrossChecks", settings={})
        self._task.cross_checks.settings["WalkForward@enabled"] = str(
            instruction.wf_enabled
        ).lower()
        self._task.cross_checks.settings["MonteCarlo@enabled"] = str(
            instruction.mc_enabled
        ).lower()
        self._task.cross_checks.settings["WalkForward@cycles"] = str(
            instruction.wf_cycles
        )

    # ── Phase 4 Appliers ────────────────────────────────────────────────

    def _apply_set_automatic_portfolio_builder(
        self, instruction: SetAutomaticPortfolioBuilderInstruction
    ) -> None:
        """Configure Automatic Portfolio Builder settings (create if missing)."""
        xml = f"""<AutomaticPortfolioBuilder>
  <Generations value="{instruction.generations}"/>
  <PopulationSize value="{instruction.population}"/>
  <FitnessFunction value="{instruction.fitness}"/>
  <MinStrategies value="{instruction.min_strategies}"/>
  <MaxStrategies value="{instruction.max_strategies if instruction.max_strategies else 10}"/>
  <RebalancingPeriod value="{instruction.rebalancing}"/>
</AutomaticPortfolioBuilder>"""
        if not self._task.automatic_portfolio_builder:
            self._task.automatic_portfolio_builder = AutomaticPortfolioBuilderConfig(
                raw_xml=""
            )
        self._task.automatic_portfolio_builder.raw_xml = xml

    def _apply_set_portfolio_settings(
        self, instruction: SetPortfolioSettingsInstruction
    ) -> None:
        """Configure Portfolio Settings (create if missing)."""
        xml = "<PortfolioSettings>"
        if instruction.weight_constraints:
            for sid, constraint in instruction.weight_constraints.items():
                xml += f'<WeightConstraint strategy="{sid}" constraint="{constraint}"/>'
        xml += "</PortfolioSettings>"
        if not self._task.portfolio_settings:
            self._task.portfolio_settings = PortfolioSettingsConfig(raw_xml="")
        self._task.portfolio_settings.raw_xml = xml

    def _apply_set_optimization(self, instruction: SetOptimizationInstruction) -> None:
        """Configure Optimizer main settings (create if missing)."""
        xml = f"""<Optimization>
  <Method value="{instruction.method}"/>
  <ObjectiveFunction value="{instruction.objective_function}"/>
  <WalkforwardCycles value="{instruction.walkforward_cycles}"/>
  <WalkforwardOOTRatio value="{instruction.walkforward_oot_ratio}"/>
</Optimization>"""
        if not self._task.optimization:
            self._task.optimization = OptimizationConfig(raw_xml="")
        self._task.optimization.raw_xml = xml

    def _apply_set_optimization_parameters(
        self, instruction: SetOptimizationParametersInstruction
    ) -> None:
        """Configure optimization parameter ranges (create if missing)."""
        xml = "<OptimizationParameters>"
        for name, rng in instruction.parameters.items():
            xml += f'<Parameter name="{name}" min="{rng["min"]}" max="{rng["max"]}" step="{rng["step"]}"/>'
        xml += "</OptimizationParameters>"
        if not self._task.optimization_parameters:
            self._task.optimization_parameters = OptimizationParametersConfig(
                raw_xml=""
            )
        self._task.optimization_parameters.raw_xml = xml

    def _apply_set_walkforward(self, instruction: SetWalkForwardInstruction) -> None:
        """Configure walk-forward settings (create if missing)."""
        xml = f"""<WalkForward>
  <Cycles value="{instruction.cycles}"/>
  <OOTRatio value="{instruction.oot_ratio}"/>
  <Anchored value="{str(instruction.anchored).lower()}"/>
</WalkForward>"""
        if not self._task.walk_forward:
            self._task.walk_forward = WalkForwardConfig(raw_xml="")
        self._task.walk_forward.raw_xml = xml

    def _apply_set_databanks(self, instruction: SetDatabanksInstruction) -> None:
        """Set databanks for optimizer/retester (create if missing)."""
        xml = "<Databanks>"
        for i, db in enumerate(instruction.databanks, 1):
            xml += f'<Databank index="{i}" name="{db}" enabled="true"/>'
        xml += "</Databanks>"
        if not self._task.databanks_section:
            self._task.databanks_section = DatabanksConfig(raw_xml="")
        self._task.databanks_section.raw_xml = xml

    def _apply_set_rankings(self, instruction: SetRankingsInstruction) -> None:
        """Configure retester rankings settings (create if missing)."""
        xml = f"""<Rankings>
  <MinTrades value="{instruction.min_trades}"/>"""
        for metric in instruction.metrics:
            xml += f'\n  <Metric name="{metric}"/>'
        xml += "\n</Rankings>"
        if not self._task.rankings_section:
            self._task.rankings_section = RankingsConfig(raw_xml="")
        self._task.rankings_section.raw_xml = xml

    def _apply_set_crosschecks(self, instruction: SetCrossChecksInstruction) -> None:
        """Configure retester cross-checks (Monte Carlo, Walk-Forward) — create if missing."""
        new_section = CrossChecksConfig(
            dialect="generic",
            generic=CrossChecksGeneric(
                mc_enabled=instruction.mc_enabled,
                mc_runs=instruction.mc_runs,
                mc_percentile=instruction.mc_percentile,
                wf_enabled=instruction.wf_enabled,
                wf_cycles=instruction.wf_cycles,
                confidence_level=instruction.confidence_level,
            ),
        )
        if not self._task.cross_checks_section:
            self._task.cross_checks_section = new_section
            return
        # Preserve raw_xml extras from the existing section while mutating
        # typed fields (never replace raw_xml outright).
        existing = self._task.cross_checks_section
        existing.dialect = "generic"
        existing.generic = new_section.generic
        if not existing.raw_xml:
            existing.raw_xml = ""

    def _apply_set_retester_data(self, instruction: SetRetesterDataInstruction) -> None:
        """Configure retester data settings (create if missing)."""
        xml = f"""<RetesterData>
  <MonteCarloRuns value="{instruction.monte_carlo_runs}"/>
  <WalkforwardCycles value="{instruction.walkforward_cycles}"/>
  <ConfidenceLevel value="{instruction.confidence_level}"/>
  <MinTrades value="{instruction.min_trades}"/>
  <MonteCarloPercentile value="{instruction.mc_percentile}"/>
  <Databanks>"""
        for db in instruction.databanks:
            xml += f'\n    <Databank name="{db}" enabled="true"/>'
        xml += "\n  </Databanks>\n</RetesterData>"
        if not self._task.retester_data:
            self._task.retester_data = RetesterDataConfig(raw_xml="")
        self._task.retester_data.raw_xml = xml

    @staticmethod
    def _build_advanced_rankings_xml(conditions: list[AdvancedRankingCondition]) -> str:
        """Build nested ``<Rankings><Conditions>`` XML from typed conditions."""
        return build_advanced_rankings_xml(conditions)

    def _apply_set_advanced_rankings(
        self, instruction: SetAdvancedRankingsInstruction
    ) -> None:
        """Replace the advanced rankings block with the given conditions."""
        xml = self._build_advanced_rankings_xml(instruction.conditions)
        if not self._task.rankings_section:
            self._task.rankings_section = RankingsConfig(raw_xml="")
        self._task.rankings_section.raw_xml = xml

    def _apply_add_advanced_ranking_condition(
        self, instruction: AddAdvancedRankingConditionInstruction
    ) -> None:
        """Append one advanced ranking condition to the existing Rankings section."""
        cond = instruction.condition
        section = self._task.rankings_section
        existing_xml = section.raw_xml if section else ""

        if not existing_xml:
            self._task.rankings_section = RankingsConfig(
                raw_xml=self._build_advanced_rankings_xml([cond])
            )
            return

        conditions = self._parse_conditions_from_xml(existing_xml)
        if not conditions:
            # Never silently discard a Rankings block we cannot interpret: the
            # simple SetRankingsInstruction path writes <Rankings> without a
            # <Conditions> child, and overwriting it would lose user config.
            raise ValidationError(
                "AddAdvancedRankingConditionInstruction: existing Rankings section has no "
                "<Conditions> block to append to. Use SetAdvancedRankingsInstruction to "
                "replace it."
            )

        conditions.append(cond)
        section.raw_xml = self._build_advanced_rankings_xml(conditions)  # type: ignore[union-attr]

    def _apply_set_data_range_parts(
        self, instruction: SetDataRangePartsInstruction
    ) -> None:
        """Replace the <Data> range-parts block (create if missing).

        The typed model is stored as-is rather than as a pre-rendered blob: the
        spec defines ``raw_xml`` as the lane for content that has *no* typed
        field, and PR 2's DSL/renderer wiring needs the typed fields to survive
        the patch. Call ``DataRangeParts.to_xml()`` to serialise.
        """
        self._task.data_range_parts = instruction.parts

    @staticmethod
    def _parse_conditions_from_xml(xml: str) -> list[AdvancedRankingCondition]:
        """Parse advanced ranking conditions from raw XML."""
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []

        conditions_el = root if root.tag == "Conditions" else root.find("Conditions")
        if conditions_el is None:
            return []
        conditions = []
        for cond_el in conditions_el.findall("Condition"):
            use = cond_el.get("use", "true").lower() == "true"
            result_type = cond_el.get("resultType", "main")
            sample_type = cond_el.get("sampleType", "127")
            direction = cond_el.get("direction", "0")
            pct_ratio = cond_el.get("pctRatio", "0")
            confidence_level = cond_el.get("confidenceLevel", "50")
            market = cond_el.get("market", "1")
            pl_type = cond_el.get("plType", "10")
            subresult = cond_el.get("subresult", "30")
            class_ = cond_el.get("class")
            name = cond_el.get("name")
            column_values = []
            for cv_el in cond_el.findall("Column-Value"):
                column_values.append(
                    ColumnValue(  # type: ignore[call-arg]
                        column=cv_el.get("column", ""),
                        column_type=cv_el.get("columnType", "0"),
                        format=cv_el.get("format", ""),
                        result_type=cv_el.get("resultType", "main"),
                        direction=cv_el.get("direction", "0"),
                        sample_type=cv_el.get("sampleType", "127"),
                        pl_type=cv_el.get("plType", "10"),
                        confidence_level=cv_el.get("confidenceLevel", "50"),
                        market=cv_el.get("market", "1"),
                        subresult=cv_el.get("subresult", "30"),
                        pct_ratio=cv_el.get("pctRatio", "0"),
                        class_=cv_el.get("class", ""),
                        name=cv_el.get("name"),
                    )
                )
            conditions.append(
                AdvancedRankingCondition(  # type: ignore[call-arg]
                    use=use,
                    result_type=result_type,
                    sample_type=sample_type,
                    direction=direction,
                    pct_ratio=pct_ratio,
                    confidence_level=confidence_level,
                    market=market,
                    pl_type=pl_type,
                    subresult=subresult,
                    class_=class_,
                    name=name,
                    column_values=column_values,
                )
            )
        return conditions

    # ── Domain convenience methods (exposed via dom.py) ───────────────

    def set_market(self, symbol: str) -> CfxPatcher:
        """Set the market symbol."""
        return self.apply([SetMarketInstruction(symbol=symbol)])

    def add_timeframe(self, timeframe: str) -> CfxPatcher:
        """Add a timeframe/chart."""
        return self.apply([AddTimeframeInstruction(timeframe=timeframe)])

    def enable_block(self, block_key: str, weight: int = 100) -> CfxPatcher:
        """Enable a building block with weight."""
        return self.apply([EnableBlockInstruction(block_key=block_key, weight=weight)])

    def disable_block(self, block_key: str) -> CfxPatcher:
        """Disable a building block."""
        return self.apply([DisableBlockInstruction(block_key=block_key)])

    def set_genetic(
        self, enabled: bool, generations: int, population: int
    ) -> CfxPatcher:
        """Configure genetic optimisation."""
        return self.apply(
            [
                SetGeneticInstruction(
                    enabled=enabled, generations=generations, population=population
                )
            ]
        )

    def set_date_range(self, start: str, end: str) -> CfxPatcher:
        """Set the backtest date range."""
        return self.apply([SetDateRangeInstruction(start=start, end=end)])

    def add_ranking_condition(
        self, metric: str, operator: str, value: float
    ) -> CfxPatcher:
        """Add a ranking acceptance condition."""
        return self.apply(
            [
                AddRankingConditionInstruction(
                    metric=metric, operator=operator, value=value
                )
            ]
        )

    def set_advanced_rankings(
        self, conditions: list[AdvancedRankingCondition]
    ) -> CfxPatcher:
        """Set the advanced rankings block with typed conditions."""
        return self.apply([SetAdvancedRankingsInstruction(conditions=conditions)])

    def add_advanced_ranking_condition(
        self, condition: AdvancedRankingCondition
    ) -> CfxPatcher:
        """Append one advanced ranking condition to the existing block."""
        return self.apply([AddAdvancedRankingConditionInstruction(condition=condition)])

    def set_data_range_parts(self, parts: DataRangeParts) -> CfxPatcher:
        """Set the <Data> range-parts block from a typed model."""
        return self.apply([SetDataRangePartsInstruction(parts=parts)])

    def enable_crosscheck(
        self, wf_enabled: bool, mc_enabled: bool, wf_cycles: int = 50
    ) -> CfxPatcher:
        """Enable walk-forward and Monte-Carlo cross-checks."""
        return self.apply(
            [
                EnableCrosscheckInstruction(
                    wf_enabled=wf_enabled, mc_enabled=mc_enabled, wf_cycles=wf_cycles
                )
            ]
        )

    # ── Commission / Spread convenience methods ──────────────────────

    def set_commission_settings(
        self,
        commission_type: str,
        value: float,
        currency: str,
        tiers: list[tuple[int, int, float]] | None = None,
    ) -> CfxPatcher:
        """Set commission cost settings on the primary task."""
        settings: dict[str, str] = {
            "CommissionType@value": commission_type,
            "CommissionValue@value": str(value),
            "CommissionCurrency@value": currency,
        }
        if tiers:
            tier_strs = [f"{vm}-{vx}:{r}" for vm, vx, r in tiers]
            settings["CommissionTiers@value"] = ",".join(tier_strs)
        self._task.commission_costs = SettingsSection(
            name="CommissionCosts", settings=settings
        )
        return self

    def set_spread_settings(
        self,
        base_spread: float,
        slippage_pips: float,
        session_multipliers: dict[str, float] | None = None,
    ) -> CfxPatcher:
        """Set spread and slippage settings on the primary task."""
        settings: dict[str, str] = {
            "BaseSpread@value": str(base_spread),
            "SlippagePips@value": str(slippage_pips),
        }
        if session_multipliers:
            for name, multiplier in session_multipliers.items():
                settings[f"Session{name}@multiplier"] = str(multiplier)
        if self._task.commission_costs is None:
            self._task.commission_costs = SettingsSection(
                name="CommissionCosts", settings=settings
            )
        else:
            self._task.commission_costs.settings.update(settings)
        return self


# ── Domain module facade ─────────────────────────────────────────────

# These are re-exported from quantlab.cfx.dom for cleaner API
# The actual dom.py module provides the public API
__all__ = ["CfxPatcher", "ValidationError"]
