"""T3-4 RED tests: Filtering, GoToTask, AutomaticPortfolioBuilder with condition trees."""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree

import pytest
from quantlab.customproject.generator import generate_cfx_archive
from quantlab.customproject.models import (
    CustomProject,
    CustomProjectTask,
    DatabankSpec,
    Filters,
    GoToTask,
)
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


class TestFilteringSerialization:
    """Filtering: <Filtering><ActionType><MaxStrategies><ConditionsType><Conditions>"""

    def test_emits_filtering_with_conditions_tree(self):
        project = CustomProject(
            name="filt",
            tasks=[
                CustomProjectTask(
                    type="Filtering",
                    name="Filtering",
                    source_databank="Results",
                    target_databank="Strategies to improve",
                    filters=Filters(
                        conditions=[
                            'NetProfit>1000',
                            'ProfitFactor>1.5',
                        ]
                    ),
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        filt = root.find("Filtering")
        assert filt is not None
        assert filt.find("ActionType").text == "1"
        assert filt.find("MaxStrategies").text == "10"
        assert filt.find("ConditionsType").text == "1"
        conditions = filt.find("Conditions")
        assert conditions is not None
        cond_list = conditions.findall("Condition")
        assert len(cond_list) == 2
        c0 = cond_list[0]
        assert c0.get("use") == "true"
        left = c0.find("Left-Side")
        assert left is not None
        col_val = left.find("Column-Value")
        assert col_val is not None
        # column attribute should be the condition string
        assert "NetProfit" in col_val.get("column", "")
        comp = c0.find("Comparator")
        assert comp is not None
        assert comp.get("value") == ">"
        right = c0.find("Right-Side")
        assert right is not None
        num_val = right.find("Numeric-Value")
        assert num_val is not None
        assert num_val.get("value") == "1000"


class TestGoToTaskSerialization:
    """GoToTask: <GoToTask task=... resetEvaluatedCycles=... resetActivatedCycles=...><Conditions>"""

    def test_emits_goto_with_attributes_and_conditions(self):
        project = CustomProject(
            name="goto",
            tasks=[
                CustomProjectTask(
                    type="GoToTask",
                    name="GoToTask",
                    goto=GoToTask(
                        target="Filtering",
                        condition="retest_failed",
                    ),
                    params={
                        "resetEvaluatedCycles": "true",
                        "resetActivatedCycles": "false",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        goto = root.find("GoToTask")
        assert goto is not None
        assert goto.get("task") == "Filtering"
        assert goto.get("resetEvaluatedCycles") == "true"
        assert goto.get("resetActivatedCycles") == "false"
        cond = goto.find("Conditions")
        assert cond is not None
        cond_cond = cond.find("Condition")
        assert cond_cond is not None
        assert cond_cond.get("use") == "true"
        # condition text in Left-Side Column-Value
        left = cond_cond.find("Left-Side")
        assert left is not None
        col = left.find("Column-Value")
        assert col is not None
        assert "retest_failed" in col.get("column", "")


class TestAutomaticPortfolioBuilderSerialization:
    """AutomaticPortfolioBuilder: <AutomaticPortfolioBuilder> with MoneyManagement inside."""

    def test_emits_apb_with_money_management(self):
        project = CustomProject(
            name="apb",
            tasks=[
                CustomProjectTask(
                    type="AutomaticPortfolioBuilder",
                    name="AutomaticPortfolioBuilder",
                    params={
                        "searchType": "genetic",
                        "genPopulationSize": "100",
                        "genGenerations": "50",
                        "genRunContinually": "false",
                        "genRestartAfterStagnation": "true",
                        "genGenerationLimit": "10",
                        "minStrategies": "2",
                        "maxStrategies": "8",
                        "maxStrategiesDatabank": "3",
                        "maxStrategiesSector": "2",
                        "dateRange": "last_month",
                        "dateRangeFrom": "2024-01-01",
                        "dateRangeTo": "2024-01-31",
                        "dateRangeIsPct": "0",
                        "dateRangeReverse": "false",
                        "fitnessType": "net_profit",
                        "corrMax": "0.7",
                        "corrType": "pearson",
                        "corrSampleType": "1",
                        "corrPeriod": "100",
                        "corrAllowNegative": "false",
                        "corrAddEmptyPeriods": "true",
                        "initialCapital": "10000",
                        "mmMethod": "FixedLot",
                        "mmParams": "LotSize=0.1",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        apb = root.find("AutomaticPortfolioBuilder")
        assert apb is not None
        assert apb.find("SearchType").text == "genetic"
        assert apb.find("GenPopulationSize").text == "100"
        assert apb.find("GenGenerations").text == "50"
        assert apb.find("MinStrategies").text == "2"
        assert apb.find("MaxStrategies").text == "8"
        # MoneyManagement inside APB
        mm = apb.find("MoneyManagement")
        assert mm is not None
        assert mm.find("InitialCapital").text == "10000"
        method = mm.find("Method")
        assert method is not None
        assert method.get("type") == "FixedLot"
        assert method.get("use") == "true"
        params = method.find("Params")
        assert params is not None
        p = params.find("Param")
        assert p is not None
        assert p.get("key") == "LotSize"
        assert p.text == "0.1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])