"""Pydantic v2 models for .cfx archive contents.

Mirrors the CFX XML schema 1:1 via element.attrib → field mapping.
All models use Pydantic v2 BaseModel with strict mode disabled to
accommodate string-typed attribute values from XML parsing.
"""

from __future__ import annotations

from typing import Union

from pydantic import BaseModel, Field


# ── Section Types ────────────────────────────────────────────────────


class SettingsSection(BaseModel):
    """Simple key-value section (Options, Data, Rankings, etc.)."""

    name: str
    settings: dict[str, str]


class RawXmlSection(BaseModel):
    """Byte-for-byte passthrough for unrecognized sections."""

    name: str
    raw_xml: str


# ── Complex Section Models ───────────────────────────────────────────


class BlockConfig(BaseModel):
    """Typed model for the <Blocks> section."""

    raw_xml: str = ""


class AtmConfig(BaseModel):
    """Typed model for the <ATMs> section."""

    raw_xml: str = ""


class DataBankConfig(BaseModel):
    """Typed model for the <DataBanks> section."""

    raw_xml: str = ""


class ResourceConfig(BaseModel):
    """Typed model for the <Resources> section."""

    raw_xml: str = ""


# ── BuildTask ────────────────────────────────────────────────────────


class BuildTask(BaseModel):
    """A single build task extracted from a CFX archive."""

    options: SettingsSection | None = None
    what_to_build: SettingsSection | None = None
    risk_money_mgmt: SettingsSection | None = None
    data: SettingsSection | None = None
    rankings: SettingsSection | None = None
    parts_to_improve: SettingsSection | None = None
    cross_checks: SettingsSection | None = None
    notes: SettingsSection | None = None
    blocks: BlockConfig | None = None
    atms: AtmConfig | None = None
    databanks: DataBankConfig | None = None
    resources: ResourceConfig | None = None
    unknown_sections: list[RawXmlSection] = Field(default_factory=list)


# ── Archive Models ───────────────────────────────────────────────────


class CfxConfig(BaseModel):
    """Single-file config: <Task> root, one BuildTask."""

    task: BuildTask
    schema_version: str

    @property
    def task_type(self) -> str:
        return "config"


class CfxProject(BaseModel):
    """Multi-file project: <Project> root, task routing."""

    name: str
    tasks: dict[str, BuildTask]
    schema_version: str

    @property
    def task_type(self) -> str:
        return "project"


class CfxArchive(BaseModel):
    """Top-level CFX archive holding config/project + task file lookup."""

    config: CfxConfig | CfxProject
    task_files: dict[str, BuildTask] = Field(default_factory=dict)


# ── PatchInstruction Types ───────────────────────────────────────────


class SetMarketInstruction(BaseModel):
    """Set the market symbol on the first data setup."""

    symbol: str
    instruction_type: str = "set_market"


class AddTimeframeInstruction(BaseModel):
    """Add a new timeframe/chart to the data section."""

    timeframe: str
    instruction_type: str = "add_timeframe"


class EnableBlockInstruction(BaseModel):
    """Enable a building block with an optional weight override."""

    block_key: str
    weight: int = 100
    instruction_type: str = "enable_block"


class DisableBlockInstruction(BaseModel):
    """Disable a building block by key."""

    block_key: str
    instruction_type: str = "disable_block"


class SetGeneticInstruction(BaseModel):
    """Configure genetic optimisation parameters."""

    enabled: bool
    generations: int
    population: int
    instruction_type: str = "set_genetic"


class SetDateRangeInstruction(BaseModel):
    """Set the date range for backtesting data."""

    start: str
    end: str
    instruction_type: str = "set_date_range"


class AddRankingConditionInstruction(BaseModel):
    """Add a ranking condition with metric, operator, and threshold."""

    metric: str
    operator: str
    value: float
    instruction_type: str = "add_ranking_condition"


class EnableCrosscheckInstruction(BaseModel):
    """Enable walk-forward and Monte-Carlo cross-checks."""

    wf_enabled: bool
    mc_enabled: bool
    wf_cycles: int = 50
    instruction_type: str = "enable_crosscheck"


PatchInstruction = Union[
    SetMarketInstruction,
    AddTimeframeInstruction,
    EnableBlockInstruction,
    DisableBlockInstruction,
    SetGeneticInstruction,
    SetDateRangeInstruction,
    AddRankingConditionInstruction,
    EnableCrosscheckInstruction,
]
"""Union of all 8 typed instruction models for CfxPatcher."""
