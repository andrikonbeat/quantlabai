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
from quantlab.cfx.dom import (
    add_ranking_condition,
    add_timeframe,
    disable_block,
    enable_block,
    enable_crosscheck,
    set_date_range,
    set_genetic,
    set_market,
)
from quantlab.cfx.patcher import CfxPatcher, ValidationError
from quantlab.cfx.reader import CfxReader
from quantlab.cfx.writer import CfxWriter
from quantlab.translate.translator import generate_cfx_xml

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
    "CfxPatcher",
    "ValidationError",
    "CfxReader",
    "CfxWriter",
    "CfxNotFoundError",
    "CfxCorruptError",
    "CfxParseError",
    "VersionError",
    # Domain methods
    "set_market",
    "add_timeframe",
    "enable_block",
    "disable_block",
    "set_genetic",
    "set_date_range",
    "add_ranking_condition",
    "enable_crosscheck",
    # Translator integration
    "generate_cfx_xml",
]
