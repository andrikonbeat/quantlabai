"""T3-1 RED tests: simple text/scalar task types emit authoritative XML dialect.

Each test verifies the exact SQX 144/2953 XML structure for the 9 simple types:
CreatePortfolio, CustomAnalysis, LogDatabankStats, SaveToFiles, LoadFromFiles,
UpdateData, WaitFor, DeleteFile, Notification.
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
    """Generate CFX and return the single task's <Settings> root."""
    archive = generate_cfx_archive(project)
    raw = _archive_bytes(archive)
    with zipfile.ZipFile(BytesIO(raw), "r") as zf:
        task_xmls = [n for n in zf.namelist() if n.endswith(".xml") and n != "config.xml"]
        assert len(task_xmls) == 1
        return ElementTree.fromstring(zf.read(task_xmls[0]))


class TestCreatePortfolioSerialization:
    """CreatePortfolio: <CreatePortfolio><MaxStrategies>int</MaxStrategies></CreatePortfolio>"""

    def test_emits_max_strategies_child_text(self):
        project = CustomProject(
            name="cp",
            tasks=[
                CustomProjectTask(
                    type="CreatePortfolio",
                    name="CreatePortfolio",
                    params={"maxStrategies": "42"},
                    source_databank="Results",
                    target_databank="Last generation",
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        create_portfolio = root.find("CreatePortfolio")
        assert create_portfolio is not None
        max_strat = create_portfolio.find("MaxStrategies")
        assert max_strat is not None
        assert max_strat.text == "42"

    def test_databanks_section_not_inside_create_portfolio(self):
        """Databanks go in <Settings><Databanks>, not inside <CreatePortfolio>."""
        project = CustomProject(
            name="cp-db",
            tasks=[
                CustomProjectTask(
                    type="CreatePortfolio",
                    name="CreatePortfolio",
                    params={"maxStrategies": "10"},
                    source_databank="Results",
                    target_databank="Strategies to improve",
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        # Databanks is a sibling of CreatePortfolio
        databanks = root.find("Databanks")
        assert databanks is not None
        input_db = databanks.find('Databank[@name="Input"]')
        output_db = databanks.find('Databank[@name="Output"]')
        assert input_db is not None
        assert input_db.get("value") == "Results"
        assert output_db is not None
        assert output_db.get("value") == "Strategies to improve"
        # CreatePortfolio has NO Databank children
        create_portfolio = root.find("CreatePortfolio")
        assert create_portfolio.find("Databank") is None


class TestCustomAnalysisSerialization:
    """CustomAnalysis: all child text nodes per harvest."""

    def test_emits_all_custom_analysis_children(self):
        project = CustomProject(
            name="ca",
            tasks=[
                CustomProjectTask(
                    type="CustomAnalysis",
                    name="CustomAnalysis",
                    params={
                        "perStrategy1": "summary",
                        "perStrategy2": "detailed",
                        "fullDatabank1": "all",
                        "fullDatabank2": "best",
                        "filter": "true",
                        "inputArgsPerStrategy1": "json",
                        "inputArgsPerStrategy2": "csv",
                        "inputArgsFullDatabank1": "xml",
                        "inputArgsFullDatabank2": "yaml",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        ca = root.find("CustomAnalysis")
        assert ca is not None
        expected = {
            "PerStrategy1": "summary",
            "PerStrategy2": "detailed",
            "FullDatabank1": "all",
            "FullDatabank2": "best",
            "Filter": "true",
            "InputArgsPerStrategy1": "json",
            "InputArgsPerStrategy2": "csv",
            "InputArgsFullDatabank1": "xml",
            "InputArgsFullDatabank2": "yaml",
        }
        for child_name, expected_text in expected.items():
            child = ca.find(child_name)
            assert child is not None, f"Missing <{child_name}>"
            assert child.text == expected_text, f"<{child_name}> text mismatch"


class TestLogDatabankStatsSerialization:
    """LogDatabankStats: <Databank> + list of <LogStats type="..."> with <Conditions>/<Column>"""

    def test_emits_databank_and_log_stats_list(self):
        project = CustomProject(
            name="lds",
            tasks=[
                CustomProjectTask(
                    type="LogDatabankStats",
                    name="LogDatabankStats",
                    params={
                        "databank": "Results",
                        "logStats": [
                            {"type": "sum", "column": "NetProfit"},
                            {"type": "avg", "column": "ProfitFactor"},
                        ],
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        lds = root.find("LogDatabankStats")
        assert lds is not None
        databank = lds.find("Databank")
        assert databank is not None
        assert databank.text == "Results"
        log_stats_list = lds.findall("LogStats")
        assert len(log_stats_list) == 2
        assert log_stats_list[0].get("type") == "sum"
        assert log_stats_list[1].get("type") == "avg"
        # Column child inside LogStats
        col0 = log_stats_list[0].find("Column")
        assert col0 is not None
        assert col0.text == "NetProfit"


class TestSaveToFilesSerialization:
    """SaveToFiles: many child text scalars + SaveSourceCode with attrs."""

    def test_emits_all_save_to_files_children(self):
        project = CustomProject(
            name="stf",
            tasks=[
                CustomProjectTask(
                    type="SaveToFiles",
                    name="SaveToFiles",
                    params={
                        "destDirectorySqx": "/out/sqx",
                        "destDirectoryStr": "/out/str",
                        "destDirectoryDatabank": "/out/db",
                        "destDirectoryTrades": "/out/trades",
                        "destDirectoryHtml": "/out/html",
                        "destDirectoryPdf": "/out/pdf",
                        "destDirectorySC": "/out/sc",
                        "saveInSqxFormat": "true",
                        "saveInStrFormat": "false",
                        "exportDatabank": "true",
                        "exportTrades": "true",
                        "saveInHtmlFormat": "true",
                        "saveInPdfFormat": "false",
                        "saveSourceCode": "true",
                        "saveSourceCodeType": "source",
                        "saveSourceCodeFormat": "text",
                        "overwriteFiles": "true",
                        "mnActive": "false",
                        "mnValue": "100",
                        "data": "strategies",
                        "format": "csv",
                        "useComma": "true",
                        "setNoteActive": "true",
                        "setNoteType": "custom",
                        "setNoteCustom": "my note",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        stf = root.find("SaveToFiles")
        assert stf is not None
        # All simple child text
        expected = {
            "DestDirectorySqx": "/out/sqx",
            "DestDirectoryStr": "/out/str",
            "DestDirectoryDatabank": "/out/db",
            "DestDirectoryTrades": "/out/trades",
            "DestDirectoryHtml": "/out/html",
            "DestDirectoryPdf": "/out/pdf",
            "DestDirectorySC": "/out/sc",
            "SaveInSqxFormat": "true",
            "SaveInStrFormat": "false",
            "ExportDatabank": "true",
            "ExportTrades": "true",
            "SaveInHtmlFormat": "true",
            "SaveInPdfFormat": "false",
            "OverwriteFiles": "true",
            "MNActive": "false",
            "MNValue": "100",
            "Data": "strategies",
            "Format": "csv",
            "UseComma": "true",
            "SetNoteActive": "true",
            "SetNoteType": "custom",
            "SetNoteCustom": "my note",
        }
        for child_name, expected_text in expected.items():
            child = stf.find(child_name)
            assert child is not None, f"Missing <{child_name}>"
            assert child.text == expected_text
        # SaveSourceCode has attributes
        ssc = stf.find("SaveSourceCode")
        assert ssc is not None
        assert ssc.text == "true"
        assert ssc.get("type") == "source"
        assert ssc.get("format") == "text"


class TestLoadFromFilesSerialization:
    """LoadFromFiles: all child text."""

    def test_emits_load_from_files_children(self):
        project = CustomProject(
            name="lff",
            tasks=[
                CustomProjectTask(
                    type="LoadFromFiles",
                    name="LoadFromFiles",
                    params={
                        "sourceDirectory": "/data/strats",
                        "includeSubdirectories": "true",
                        "unrecognizedInstrumentAction": "skip",
                        "unrecognizedInstrumentValue": "",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        lff = root.find("LoadFromFiles")
        assert lff is not None
        expected = {
            "SourceDirectory": "/data/strats",
            "IncludeSubdirectories": "true",
            "UnrecognizedInstrumentAction": "skip",
            "UnrecognizedInstrumentValue": "",
        }
        for child_name, expected_text in expected.items():
            child = lff.find(child_name)
            assert child is not None, f"Missing <{child_name}>"
            actual = child.text or ""
            assert actual == expected_text


class TestUpdateDataSerialization:
    """UpdateData: <Type>project</Type>."""

    def test_emits_type_child_text(self):
        project = CustomProject(
            name="ud",
            tasks=[
                CustomProjectTask(
                    type="UpdateData",
                    name="UpdateData",
                    params={"type": "project"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        ud = root.find("UpdateData")
        assert ud is not None
        type_el = ud.find("Type")
        assert type_el is not None
        assert type_el.text == "project"

    def test_default_type_is_project(self):
        project = CustomProject(
            name="ud-def",
            tasks=[CustomProjectTask(type="UpdateData", name="UpdateData")],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        ud = root.find("UpdateData")
        assert ud is not None
        type_el = ud.find("Type")
        assert type_el is not None
        assert type_el.text == "project"


class TestWaitForSerialization:
    """WaitFor: <File> + <Action> (default user)."""

    def test_emits_file_and_action(self):
        project = CustomProject(
            name="wf",
            tasks=[
                CustomProjectTask(
                    type="WaitFor",
                    name="WaitFor",
                    params={"file": "/tmp/signal", "action": "continue"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        wf = root.find("WaitFor")
        assert wf is not None
        file_el = wf.find("File")
        action_el = wf.find("Action")
        assert file_el is not None and file_el.text == "/tmp/signal"
        assert action_el is not None and action_el.text == "continue"

    def test_default_action_is_user(self):
        project = CustomProject(
            name="wf-def",
            tasks=[CustomProjectTask(type="WaitFor", name="WaitFor", params={"file": "/x"})],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        wf = root.find("WaitFor")
        assert wf is not None
        action_el = wf.find("Action")
        assert action_el is not None
        assert action_el.text == "user"


class TestDeleteFileSerialization:
    """DeleteFile: <File>path</File>."""

    def test_emits_file_child_text(self):
        project = CustomProject(
            name="df",
            tasks=[
                CustomProjectTask(
                    type="DeleteFile",
                    name="DeleteFile",
                    params={"file": "/tmp/junk.txt"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        df = root.find("DeleteFile")
        assert df is not None
        file_el = df.find("File")
        assert file_el is not None
        assert file_el.text == "/tmp/junk.txt"


class TestNotificationSerialization:
    """Notification: <Type>email</Type><Email>...</Email><Wait>false</Wait>."""

    def test_emits_all_notification_children(self):
        project = CustomProject(
            name="notif",
            tasks=[
                CustomProjectTask(
                    type="Notification",
                    name="Notification",
                    params={"type": "email", "email": "test@example.com", "wait": "true"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        notif = root.find("Notification")
        assert notif is not None
        type_el = notif.find("Type")
        email_el = notif.find("Email")
        wait_el = notif.find("Wait")
        assert type_el is not None and type_el.text == "email"
        assert email_el is not None and email_el.text == "test@example.com"
        assert wait_el is not None and wait_el.text == "true"

    def test_defaults_type_email_wait_false(self):
        project = CustomProject(
            name="notif-def",
            tasks=[CustomProjectTask(type="Notification", name="Notification")],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        notif = root.find("Notification")
        assert notif is not None
        assert notif.find("Type").text == "email"
        assert (notif.find("Email").text or "") == ""
        assert notif.find("Wait").text == "false"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])