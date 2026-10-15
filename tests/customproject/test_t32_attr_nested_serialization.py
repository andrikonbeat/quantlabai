"""T3-2 RED tests: attribute/nested task types emit authoritative XML dialect.

CallExternalScript, StopAndStart, ClearDatabanks, ApplyMassConfig.
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


class TestCallExternalScriptSerialization:
    """CallExternalScript: <CallExternalScript><File params="...">path</File><WaitFor hours="0" minutes="0">end|time</WaitFor></CallExternalScript>"""

    def test_emits_file_with_params_attr_and_waitfor_with_attrs(self):
        project = CustomProject(
            name="ces",
            tasks=[
                CustomProjectTask(
                    type="CallExternalScript",
                    name="CallExternalScript",
                    params={
                        "file": "/scripts/doit.sh",
                        "params": "--verbose",
                        "waitfor": "time",
                        "hours": "2",
                        "minutes": "30",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        ces = root.find("CallExternalScript")
        assert ces is not None
        file_el = ces.find("File")
        waitfor_el = ces.find("WaitFor")
        assert file_el is not None
        assert file_el.text == "/scripts/doit.sh"
        assert file_el.get("params") == "--verbose"
        assert waitfor_el is not None
        assert waitfor_el.text == "time"
        assert waitfor_el.get("hours") == "2"
        assert waitfor_el.get("minutes") == "30"

    def test_defaults_waitfor_end_hours_0_minutes_0(self):
        project = CustomProject(
            name="ces-def",
            tasks=[
                CustomProjectTask(
                    type="CallExternalScript",
                    name="CallExternalScript",
                    params={"file": "/x.sh"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        ces = root.find("CallExternalScript")
        assert ces is not None
        waitfor_el = ces.find("WaitFor")
        assert waitfor_el is not None
        assert waitfor_el.text == "end"
        assert waitfor_el.get("hours") == "0"
        assert waitfor_el.get("minutes") == "0"
        file_el = ces.find("File")
        assert file_el.get("params") == ""


class TestStopAndStartSerialization:
    """StopAndStart: <StopAndStart><StartProject use="true" skipToFirstProject="false">ProjectName</StartProject><Conditions/></StopAndStart>"""

    def test_emits_start_project_with_attrs_and_text(self):
        project = CustomProject(
            name="sas",
            tasks=[
                CustomProjectTask(
                    type="StopAndStart",
                    name="StopAndStart",
                    params={
                        "projectName": "MyProject",
                        "startAnother": "true",
                        "skipToFirstProject": "false",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        sas = root.find("StopAndStart")
        assert sas is not None
        sp = sas.find("StartProject")
        assert sp is not None
        assert sp.text == "MyProject"
        assert sp.get("use") == "true"
        assert sp.get("skipToFirstProject") == "false"
        # Conditions element exists (empty)
        cond = sas.find("Conditions")
        assert cond is not None

    def test_defaults_start_another_false_skip_true(self):
        project = CustomProject(
            name="sas-def",
            tasks=[CustomProjectTask(type="StopAndStart", name="StopAndStart", params={"projectName": "X"})],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        sas = root.find("StopAndStart")
        sp = sas.find("StartProject")
        assert sp.get("use") == "false"
        assert sp.get("skipToFirstProject") == "true"


class TestClearDatabanksSerialization:
    """ClearDatabanks: LIST of <Databank name="X"/> elements."""

    def test_emits_multiple_databank_elements_with_name_attr(self):
        project = CustomProject(
            name="cdb",
            tasks=[
                CustomProjectTask(
                    type="ClearDatabanks",
                    name="ClearDatabanks",
                    params={"databanks": ["Results", "Last generation", "CustomDB"]},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        cdb = root.find("ClearDatabanks")
        assert cdb is not None
        databank_els = cdb.findall("Databank")
        assert len(databank_els) == 3
        names = [el.get("name") for el in databank_els]
        assert names == ["Results", "Last generation", "CustomDB"]
        # No text content, only name attribute
        for el in databank_els:
            assert (el.text or "") == ""

    def test_single_databank_string_comma_separated(self):
        """Accept comma-separated string for backward compat."""
        project = CustomProject(
            name="cdb-str",
            tasks=[
                CustomProjectTask(
                    type="ClearDatabanks",
                    name="ClearDatabanks",
                    params={"databanks": "Results,Last generation"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        cdb = root.find("ClearDatabanks")
        databank_els = cdb.findall("Databank")
        assert len(databank_els) == 2
        assert [el.get("name") for el in databank_els] == ["Results", "Last generation"]

    def test_default_databanks_results(self):
        project = CustomProject(
            name="cdb-def",
            tasks=[CustomProjectTask(type="ClearDatabanks", name="ClearDatabanks")],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        cdb = root.find("ClearDatabanks")
        databank_els = cdb.findall("Databank")
        assert len(databank_els) == 1
        assert databank_els[0].get("name") == "Results"


class TestApplyMassConfigSerialization:
    """ApplyMassConfig: <ApplyMassConfig><LoadFrom><Type>...<File>...<Task>...</LoadFrom><WhatToApply><Data>bool</Data>...<TargetTasks>comma,list</TargetTasks></ApplyMassConfig>"""

    def test_emits_load_from_what_to_apply_target_tasks(self):
        project = CustomProject(
            name="amc",
            tasks=[
                CustomProjectTask(
                    type="ApplyMassConfig",
                    name="ApplyMassConfig",
                    params={
                        "loadFromType": "project",
                        "loadFromFile": "/path/project.sqx",
                        "loadFromTask": "Build",
                        "whatToApply": {
                            "data": "true",
                            "dataTradingEngine": "false",
                            "dataBacktestData": "true",
                            "dataTestParameters": "true",
                            "dataDataRangeParts": "false",
                            "tradingOptions": "true",
                            "blocks": "true",
                            "blocksSignals": "true",
                            "blocksIndicators": "false",
                            "blocksStopLimitEntry": "true",
                            "blocksOrderTypes": "false",
                            "blocksExitTypes": "true",
                            "atm": "true",
                            "moneyManagement": "true",
                            "crossChecks": "true",
                            "whatToBuild": "false",
                            "whatToRetest": "true",
                            "partsToImprove": "false",
                            "geneticOptions": "true",
                            "optimization": "false",
                            "ranking": "true",
                        },
                        "targetTasks": "Build,Retest,Optimize",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        amc = root.find("ApplyMassConfig")
        assert amc is not None
        load_from = amc.find("LoadFrom")
        assert load_from is not None
        assert load_from.find("Type").text == "project"
        assert load_from.find("File").text == "/path/project.sqx"
        assert load_from.find("Task").text == "Build"
        what_to_apply = amc.find("WhatToApply")
        assert what_to_apply is not None
        # Check a few boolean children
        assert what_to_apply.find("Data").text == "true"
        assert what_to_apply.find("DataTradingEngine").text == "false"
        assert what_to_apply.find("MoneyManagement").text == "true"
        target_tasks = amc.find("TargetTasks")
        assert target_tasks is not None
        assert target_tasks.text == "Build,Retest,Optimize"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])