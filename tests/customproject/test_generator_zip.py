"""REQ-23: multi-task CFX ZIP shape, taskXMLFile routing, <Databanks> completeness,
single-task byte-identity against the verified golden sample."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from quantlab.customproject.generator import generate_cfx_archive
from quantlab.customproject.models import (
    CustomProject,
    CustomProjectTask,
    DatabankSpec,
    Filters,
    GoToTask,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_E2E = (
    REPO_ROOT
    / "assets"
    / "SQX_144_2953_linux_20260601"
    / "user"
    / "projects"
    / "e2e-test"
    / "project.cfx"
)

STANDARD_DATABANKS = [
    DatabankSpec(name="Results"),
    DatabankSpec(name="Last generation"),
    DatabankSpec(name="Initial population"),
    DatabankSpec(name="Strategies to improve"),
]


def _four_task_project() -> CustomProject:
    """Build → Filtering → Retest → GoToTask(Filtering) loop (the E2E shape)."""
    return CustomProject(
        name="four-task",
        tasks=[
            CustomProjectTask(
                type="Build",
                name="Build",
                source_databank="Initial population",
                target_databank="Results",
            ),
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
            CustomProjectTask(
                type="GoToTask",
                name="GoToTask",
                goto=GoToTask(target="Filtering", condition="retest_failed"),
            ),
        ],
        databanks=STANDARD_DATABANKS,
    )


class TestZipShape:
    """REQ-23 scenario 1: ZIP matches the verified format."""

    def _zip(self, archive) -> zipfile.ZipFile:
        from quantlab.cfx.writer import CfxWriter

        return zipfile.ZipFile(BytesIO(CfxWriter.to_bytes(archive)), "r")

    def test_zip_contains_config_and_one_xml_per_task(self):
        archive = generate_cfx_archive(_four_task_project())
        with self._zip(archive) as zf:
            names = zf.namelist()
            assert "config.xml" in names
            task_xmls = [n for n in names if n.endswith(".xml") and n != "config.xml"]
            assert sorted(task_xmls) == [
                "Build-Task1.xml",
                "Filtering-Task1.xml",
                "GoToTask-Task1.xml",
                "Retest-Task1.xml",
            ]

    def test_taskxmlfile_routing_matches_packaged_files(self):
        archive = generate_cfx_archive(_four_task_project())
        with self._zip(archive) as zf:
            cfg = ElementTree.fromstring(zf.read("config.xml"))
            names = set(zf.namelist())
            tasks_el = cfg.find("Tasks")
            assert tasks_el is not None
            for task_el in tasks_el.findall("Task"):
                task_xml_file = task_el.get("taskXMLFile")
                assert task_xml_file is not None
                assert task_xml_file in names
                # Every packaged task XML must be referenced from <Tasks>.
                assert ElementTree.fromstring(zf.read(task_xml_file)).tag == "Settings"
            referenced = {
                t.get("taskXMLFile") for t in tasks_el.findall("Task")
            }
            packaged = {n for n in names if n.endswith(".xml") and n != "config.xml"}
            assert referenced == packaged

    def test_project_root_attributes(self):
        archive = generate_cfx_archive(_four_task_project())
        with self._zip(archive) as zf:
            cfg = ElementTree.fromstring(zf.read("config.xml"))
            assert cfg.tag == "Project"
            assert cfg.get("name") == "four-task"
            assert cfg.get("version") == "144.2953"

    def test_databanks_lists_every_declared_databank(self):
        archive = generate_cfx_archive(_four_task_project())
        with self._zip(archive) as zf:
            cfg = ElementTree.fromstring(zf.read("config.xml"))
            databanks_el = cfg.find("Databanks")
            assert databanks_el is not None
            names = [d.get("name") for d in databanks_el.findall("Databank")]
            assert names == [
                "Results",
                "Last generation",
                "Initial population",
                "Strategies to improve",
            ]
            for db in databanks_el.findall("Databank"):
                assert db.get("name")
                assert db.get("view") == "Default - Main data"
                assert db.get("syncType") == "Auto-sync never"

    def test_position_attribute_emitted_when_set(self):
        project = CustomProject(
            name="pos",
            tasks=[CustomProjectTask(type="Build", name="Build")],
            databanks=[DatabankSpec(name="Results", position=10)],
        )
        archive = generate_cfx_archive(project)
        with self._zip(archive) as zf:
            cfg = ElementTree.fromstring(zf.read("config.xml"))
            db = cfg.find("Databanks/Databank")
            assert db is not None
            assert db.get("position") == "10"


class TestSingleTaskByteIdentity:
    """REQ-23 scenario 2: single-task output identical to the golden CFX."""

    def test_config_xml_matches_golden_bytes(self):
        assert GOLDEN_E2E.exists(), f"golden sample missing: {GOLDEN_E2E}"

        with zipfile.ZipFile(GOLDEN_E2E, "r") as zf:
            golden_cfg = zf.read("config.xml")

        project = CustomProject(
            name="e2e-test",
            tasks=[
                CustomProjectTask(
                    type="Build",
                    name="Build",
                    source_databank="Initial population",
                    target_databank="Results",
                )
            ],
            databanks=STANDARD_DATABANKS,
        )

        from quantlab.cfx.writer import CfxWriter

        raw = CfxWriter.to_bytes(generate_cfx_archive(project))
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            generated_cfg = zf.read("config.xml")

        # Byte-identical config.xml to the verified SQX sample (LF endings,
        # golden-style attribute order, self-closing elements).
        assert generated_cfg == golden_cfg

    def test_golden_config_round_trips_through_reader(self):
        """The generated single-task archive must be accepted by the existing reader."""
        from quantlab.cfx.reader import CfxReader

        project = CustomProject(
            name="e2e-test",
            tasks=[CustomProjectTask(type="Build", name="Build")],
            databanks=STANDARD_DATABANKS,
        )

        from quantlab.cfx.writer import CfxWriter

        import tempfile

        raw = CfxWriter.to_bytes(generate_cfx_archive(project))
        with tempfile.NamedTemporaryFile(suffix=".cfx") as f:
            f.write(raw)
            f.flush()
            archive = CfxReader.read(f.name)

        assert archive.config.task_type == "project"
        assert archive.config.schema_version == "144.2953"
        assert "Build-Task1.xml" in archive.task_files
