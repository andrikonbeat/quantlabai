"""REQ-22: CustomProject DSL ordered round-trip, GoToTask loop, per-task databank routing.

Tests drive the DSL models + generator end-to-end: the model is serialized
through ``generate_cfx_archive`` and the produced config.xml / task XMLs are
asserted. Task order must be preserved exactly as declared.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree

from quantlab.customproject.generator import generate_cfx_archive
from quantlab.customproject.models import (
    CustomProject,
    CustomProjectTask,
    DatabankSpec,
    Filters,
    GoToTask,
)

STANDARD_DATABANKS = [
    DatabankSpec(name="Results"),
    DatabankSpec(name="Last generation"),
    DatabankSpec(name="Initial population"),
    DatabankSpec(name="Strategies to improve"),
]


def _config_root(archive) -> ElementTree.Element:
    """Serialize an archive and return the parsed config.xml root element."""
    raw = archive_to_bytes(archive)
    with zipfile.ZipFile(BytesIO(raw), "r") as zf:
        return ElementTree.fromstring(zf.read("config.xml"))


def archive_to_bytes(archive) -> bytes:
    from quantlab.cfx.writer import CfxWriter

    return CfxWriter.to_bytes(archive)


def _task_xml(archive, filename: str) -> ElementTree.Element:
    raw = archive_to_bytes(archive)
    with zipfile.ZipFile(BytesIO(raw), "r") as zf:
        return ElementTree.fromstring(zf.read(filename))


class TestOrderedTasksRoundTrip:
    """REQ-22 scenario 1: ordered tasks round-trip."""

    def test_task_order_in_output_matches_declaration(self):
        project = CustomProject(
            name="ordered",
            tasks=[
                CustomProjectTask(type="Build", name="Build"),
                CustomProjectTask(type="Filtering", name="Filtering"),
                CustomProjectTask(type="Retest", name="Retest"),
                CustomProjectTask(type="Optimize", name="Optimize"),
            ],
            databanks=STANDARD_DATABANKS,
        )

        root = _config_root(generate_cfx_archive(project))
        tasks_el = root.find("Tasks")
        assert tasks_el is not None
        types = [t.get("type") for t in tasks_el.findall("Task")]
        assert types == ["Build", "Filtering", "Retest", "Optimize"]

    def test_every_task_retains_type_name_active_and_xmlfile(self):
        project = CustomProject(
            name="attrs",
            tasks=[
                CustomProjectTask(type="Retest", name="MyRetest", active=False),
                CustomProjectTask(type="Optimize", name="MyOptimize", active=True),
            ],
            databanks=STANDARD_DATABANKS,
        )

        root = _config_root(generate_cfx_archive(project))
        tasks_el = root.find("Tasks")
        assert tasks_el is not None
        entries = {t.get("name"): t for t in tasks_el.findall("Task")}

        retest = entries["MyRetest"]
        assert retest.get("type") == "Retest"
        assert retest.get("active") == "false"
        assert retest.get("taskXMLFile") == "Retest-Task1.xml"

        optimize = entries["MyOptimize"]
        assert optimize.get("type") == "Optimize"
        assert optimize.get("active") == "true"
        assert optimize.get("taskXMLFile") == "Optimize-Task1.xml"

    def test_explicit_taskxmlfile_override_is_honoured(self):
        project = CustomProject(
            name="override",
            tasks=[
                CustomProjectTask(
                    type="Build", name="Build", taskXMLFile="custom.xml"
                ),
            ],
            databanks=STANDARD_DATABANKS,
        )

        archive = generate_cfx_archive(project)
        root = _config_root(archive)
        task_el = root.find("Tasks/Task")
        assert task_el is not None
        assert task_el.get("taskXMLFile") == "custom.xml"
        # The overridden file must actually be packaged.
        raw = archive_to_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            assert "custom.xml" in zf.namelist()


class TestGoToTaskConditionalLoop:
    """REQ-22 scenario 2: GoToTask conditional loop."""

    def test_gototask_references_earlier_task_and_keeps_condition(self):
        project = CustomProject(
            name="loop",
            tasks=[
                CustomProjectTask(type="Filtering", name="Filtering"),
                CustomProjectTask(type="Retest", name="Retest"),
                CustomProjectTask(
                    type="GoToTask",
                    name="GoToTask",
                    goto=GoToTask(target="Filtering", condition="retest_failed"),
                ),
            ],
            databanks=STANDARD_DATABANKS,
        )

        archive = generate_cfx_archive(project)
        goto_xml = _task_xml(archive, "GoToTask-Task1.xml")

        goto_section = goto_xml.find("GoToTask")
        assert goto_section is not None
        assert goto_section.get("target") == "Filtering"
        assert goto_section.get("condition") == "retest_failed"

    def test_gototask_without_condition_renders_empty_condition(self):
        project = CustomProject(
            name="loop2",
            tasks=[
                CustomProjectTask(type="Build", name="Build"),
                CustomProjectTask(
                    type="GoToTask",
                    name="GoToTask",
                    goto=GoToTask(target="Build"),
                ),
            ],
            databanks=STANDARD_DATABANKS,
        )

        archive = generate_cfx_archive(project)
        goto_xml = _task_xml(archive, "GoToTask-Task1.xml")
        goto_section = goto_xml.find("GoToTask")
        assert goto_section is not None
        assert goto_section.get("target") == "Build"
        assert goto_section.get("condition", "") == ""


class TestPerTaskDatabankRouting:
    """REQ-22 scenario 3: per-task databank routing, no implicit sharing."""

    def _databank_names(self, task_xml: ElementTree.Element) -> set[str]:
        """Collect the actual databank names from a task XML.

        Uses the SQX-native ``value`` attribute (``<Databank name="Input"
        value="{databank}"/>``), falling back to ``name`` for legacy shapes.
        """
        names = set()
        for el in task_xml.iter("Databank"):
            value = el.get("value") or el.get("name")
            if value:
                names.add(value)
        return names

    def test_each_task_xml_references_only_its_own_databanks(self):
        project = CustomProject(
            name="routing",
            tasks=[
                CustomProjectTask(
                    type="Filtering",
                    name="Filtering",
                    source_databank="Results",
                    target_databank="Strategies to improve",
                    filters=Filters(conditions=["NetProfit > 1000"]),
                ),
                CustomProjectTask(
                    type="Retest",
                    name="Retest",
                    source_databank="Results",
                    target_databank="Results",
                ),
            ],
            databanks=STANDARD_DATABANKS,
        )

        archive = generate_cfx_archive(project)

        filtering = self._databank_names(_task_xml(archive, "Filtering-Task1.xml"))
        assert filtering == {"Results", "Strategies to improve"}

        retest = self._databank_names(_task_xml(archive, "Retest-Task1.xml"))
        assert retest == {"Results"}

    def test_task_without_databanks_has_no_databank_section(self):
        project = CustomProject(
            name="nodb",
            tasks=[
                CustomProjectTask(
                    type="GoToTask",
                    name="GoToTask",
                    goto=GoToTask(target="Build"),
                ),
            ],
            databanks=STANDARD_DATABANKS,
        )

        archive = generate_cfx_archive(project)
        goto_xml = _task_xml(archive, "GoToTask-Task1.xml")
        assert goto_xml.find("Databanks") is None
