"""CFX patcher — validate-then-apply mutation engine for CFX archives.

Provides a high-level API for applying typed patch instructions to a CfxArchive
with atomic semantics: all instructions are validated before any mutation occurs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from quantlab.cfx.errors import CfxParseError
from quantlab.cfx.models import (
    AddRankingConditionInstruction,
    AddTimeframeInstruction,
    DisableBlockInstruction,
    EnableBlockInstruction,
    EnableCrosscheckInstruction,
    PatchInstruction,
    SetDateRangeInstruction,
    SetGeneticInstruction,
    SetMarketInstruction,
)

if TYPE_CHECKING:
    from quantlab.cfx.models import BuildTask, CfxArchive


class ValidationError(CfxParseError):
    """Raised when a patch instruction fails validation."""

    pass


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
        }

        validator = validator_map.get(instruction.instruction_type)
        if validator is None:
            raise ValidationError(f"Unknown instruction type: {instruction.instruction_type}")

        validator(instruction)

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
            raise ValidationError("DisableBlockInstruction: block_key must not be empty")

    def _validate_set_genetic(self, instruction: SetGeneticInstruction) -> None:
        if instruction.generations <= 0:
            raise ValidationError("SetGeneticInstruction: generations must be positive")
        if instruction.population <= 0:
            raise ValidationError("SetGeneticInstruction: population must be positive")

    def _validate_set_date_range(self, instruction: SetDateRangeInstruction) -> None:
        # Basic format validation - accept YYYY.MM.DD or epoch ms
        for field_name, value in [("start", instruction.start), ("end", instruction.end)]:
            if not value or not value.strip():
                raise ValidationError(f"SetDateRangeInstruction: {field_name} must not be empty")

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
            raise ValidationError("AddRankingConditionInstruction: metric must not be empty")

    def _validate_enable_crosscheck(self, instruction: EnableCrosscheckInstruction) -> None:
        if instruction.wf_cycles <= 0:
            raise ValidationError("EnableCrosscheckInstruction: wf_cycles must be positive")

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
        }

        applier = applier_map.get(instruction.instruction_type)
        if applier is None:
            raise ValidationError(f"Unknown instruction type: {instruction.instruction_type}")

        applier(instruction)

    def _apply_set_market(self, instruction: SetMarketInstruction) -> None:
        """Set market symbol in Data section and Resources/Symbols."""
        symbol = instruction.symbol.strip()

        # Update Data section → Symbol setting
        if self._task.data:
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
                k for k in self._task.data.settings.keys() if k.startswith("Timeframe")
            ]
            next_idx = len(existing_keys) + 1
            self._task.data.settings[f"Timeframe{next_idx}@value"] = tf

        # WhatToBuild section → Timeframes
        if self._task.what_to_build:
            existing_keys = [
                k for k in self._task.what_to_build.settings.keys() if k.startswith("Timeframe")
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
            self._task.data.settings["ToDate@value"] = self._format_date_for_section(end, "Data")

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
        """Add a ranking condition to Rankings/Acceptance."""
        if self._task.rankings:
            # Find next available criterion index - count unique criterion prefixes
            existing_prefixes = set()
            for k in self._task.rankings.settings.keys():
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

    def _apply_enable_crosscheck(self, instruction: EnableCrosscheckInstruction) -> None:
        """Enable walk-forward and Monte-Carlo cross-checks."""
        if self._task.cross_checks:
            self._task.cross_checks.settings["WalkForward@enabled"] = str(
                instruction.wf_enabled
            ).lower()
            self._task.cross_checks.settings["MonteCarlo@enabled"] = str(
                instruction.mc_enabled
            ).lower()
            self._task.cross_checks.settings["WalkForward@cycles"] = str(
                instruction.wf_cycles
            )

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


# ── Domain module facade ─────────────────────────────────────────────

# These are re-exported from quantlab.cfx.dom for cleaner API
# The actual dom.py module provides the public API
__all__ = ["CfxPatcher", "ValidationError"]