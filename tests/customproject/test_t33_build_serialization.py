"""T3-3 RED tests: Build task emits authoritative XML dialect.

Build: <Build> with <Blocks><Calibration>, <Options><BuildTradingOptions><Params><Param key className>>,
<WhatToBuild><StrategyType attrs>, <RiskMoneyManagement><MoneyManagement><InitialCapital><Method>.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree

import pytest
from quantlab.customproject.generator import generate_cfx_archive
from quantlab.customproject.models import CustomProject, CustomProjectTask, DatabankSpec
from quantlab.cfx.writer import CfxWriter

STANDARD_DATABANKS = [
    DatabankSpec(name="Results"),
    DatabankSpec(name="Last generation"),
    DatabankSpec(name="Initial population"),
    DatabankSpec(name="Strategies to improve"),
]


def _archive_bytes(archive) -> bytes:
    return CfxWriter.to_bytes(archive)


def _task_xml_root(project: CustomProject) -> ElementTree.Element:
    archive = generate_cfx_archive(project)
    raw = _archive_bytes(archive)
    with zipfile.ZipFile(BytesIO(raw), "r") as zf:
        task_xmls = [n for n in zf.namelist() if n.endswith(".xml") and n != "config.xml"]
        assert len(task_xmls) == 1
        return ElementTree.fromstring(zf.read(task_xmls[0]))


class TestBuildCalibration:
    """Build -> <Blocks><Calibration calibrateBeforeStart useMaxSteps maxSteps/>"""

    def test_emits_calibration_attributes(self):
        project = CustomProject(
            name="build-cal",
            tasks=[
                CustomProjectTask(
                    type="Build",
                    name="Build",
                    params={
                        "calibrateBeforeStart": "true",
                        "useMaxSteps": "false",
                        "maxSteps": "100",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        build = root.find("Build")
        assert build is not None
        blocks = build.find("Blocks")
        assert blocks is not None
        cal = blocks.find("Calibration")
        assert cal is not None
        assert cal.get("calibrateBeforeStart") == "true"
        assert cal.get("useMaxSteps") == "false"
        assert cal.get("maxSteps") == "100"

    def test_defaults_false_false_0(self):
        project = CustomProject(
            name="build-cal-def",
            tasks=[CustomProjectTask(type="Build", name="Build")],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        build = root.find("Build")
        cal = build.find("Blocks").find("Calibration")
        assert cal.get("calibrateBeforeStart") == "false"
        assert cal.get("useMaxSteps") == "false"
        assert cal.get("maxSteps") == "0"


class TestBuildOptions:
    """Build -> <Options><BuildTradingOptions><Params><Param key className>value</Param></Options>"""

    def test_emits_build_trading_options_params(self):
        project = CustomProject(
            name="build-opt",
            tasks=[
                CustomProjectTask(
                    type="Build",
                    name="Build",
                    params={
                        "options": "DontTradeOnWeekends=true,ClosePositionsOnTime=false,MaxOpenPositions=5",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        build = root.find("Build")
        assert build is not None
        options = build.find("Options")
        assert options is not None
        bto = options.find("BuildTradingOptions")
        assert bto is not None
        params = bto.find("Params")
        assert params is not None
        param_els = params.findall("Param")
        assert len(param_els) == 3
        # Check key, className, text
        p0 = param_els[0]
        assert p0.get("key") == "DontTradeOnWeekends"
        assert p0.get("className") == "DontTradeOnWeekends"
        assert p0.text == "true"
        p1 = param_els[1]
        assert p1.get("key") == "ClosePositionsOnTime"
        assert p1.text == "false"


class TestBuildWhatToBuild:
    """Build -> <WhatToBuild><StrategyType attrs>"""

    def test_emits_strategy_type_attributes(self):
        project = CustomProject(
            name="build-wtb",
            tasks=[
                CustomProjectTask(
                    type="Build",
                    name="Build",
                    params={
                        "strategyType": "defaultForex",
                        "additionalCharts": "2",
                        "templateFile": "templates/forex.sqx",
                        "improveType": "0",
                        "strategyFile": "",
                        "improveDatabank": "",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        build = root.find("Build")
        wtb = build.find("WhatToBuild")
        assert wtb is not None
        st = wtb.find("StrategyType")
        assert st is not None
        assert st.get("type") == "defaultForex"
        assert st.get("additionalCharts") == "2"
        assert st.get("templateFile") == "templates/forex.sqx"
        assert st.get("improveType") == "0"


class TestBuildMoneyManagement:
    """Build -> <RiskMoneyManagement><MoneyManagement><InitialCapital><Method><Params>"""

    def test_emits_initial_capital_and_method(self):
        project = CustomProject(
            name="build-mm",
            tasks=[
                CustomProjectTask(
                    type="Build",
                    name="Build",
                    params={
                        "initialCapital": "10000",
                        "moneyManagementMethod": "FixedLot",
                        "moneyManagementParams": "LotSize=0.1,MaxLots=10",
                        "riskManagementMethod": "FixedRisk",
                        "riskManagementParams": "RiskPercent=2",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        build = root.find("Build")
        assert build is not None
        rmm = build.find("RiskMoneyManagement")
        assert rmm is not None
        mm = rmm.find("MoneyManagement")
        assert mm is not None
        ic = mm.find("InitialCapital")
        assert ic is not None
        assert ic.text == "10000"
        method = mm.find("Method")
        assert method is not None
        assert method.get("type") == "FixedLot"
        assert method.get("use") == "true"
        params = method.find("Params")
        assert params is not None
        param_els = params.findall("Param")
        assert len(param_els) == 2
        p0 = param_els[0]
        assert p0.get("key") == "LotSize"
        assert p0.get("className") == "LotSize"
        assert p0.text == "0.1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])