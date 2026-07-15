"""quantlab.cfx — CFX archive editing toolkit.

SDK for reading, writing, and patching StrategyQuant .cfx archives
using Pydantic v2 models backed by stdlib xml.etree.ElementTree.
"""

from quantlab.cfx.errors import (
    CfxCorruptError,
    CfxNotFoundError,
    CfxParseError,
    VersionError,
)
from quantlab.cfx.models import (
    AddRankingConditionInstruction,
    AddTimeframeInstruction,
    AtmConfig,
    BlockConfig,
    BuildTask,
    CfxArchive,
    CfxConfig,
    CfxProject,
    DataBankConfig,
    DisableBlockInstruction,
    EnableBlockInstruction,
    EnableCrosscheckInstruction,
    PatchInstruction,
    RawXmlSection,
    ResourceConfig,
    SetDateRangeInstruction,
    SetGeneticInstruction,
    SetMarketInstruction,
    SettingsSection,
)
from quantlab.cfx.reader import CfxReader
from quantlab.cfx.writer import CfxWriter

__all__ = [
    "CfxArchive",
    "CfxConfig",
    "CfxProject",
    "BuildTask",
    "SettingsSection",
    "RawXmlSection",
    "BlockConfig",
    "AtmConfig",
    "DataBankConfig",
    "ResourceConfig",
    "PatchInstruction",
    "SetMarketInstruction",
    "AddTimeframeInstruction",
    "EnableBlockInstruction",
    "DisableBlockInstruction",
    "SetGeneticInstruction",
    "SetDateRangeInstruction",
    "AddRankingConditionInstruction",
    "EnableCrosscheckInstruction",
    "CfxReader",
    "CfxWriter",
    "CfxNotFoundError",
    "CfxCorruptError",
    "CfxParseError",
    "VersionError",
]
