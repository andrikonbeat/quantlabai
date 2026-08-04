"""REQ-25: 21-task catalog coverage, Walk-Forward inside CrossChecks, unknown types rejected."""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree

import pytest

from quantlab.customproject.catalog import CATALOG_TYPES, TaskNotSupportedError
from quantlab.customproject.generator import generate_cfx_archive
from quantlab.customproject.models import (
    CustomProject,
    CustomProjectTask,
    DatabankSpec,
    GoToTask,
)

ALL_21 = [
    "Build",
    "Retest",
    "Optimize",
    "AutomaticRetest",
    "AutomaticPortfolioBuilder",
    "Filtering",
    "GoToTask",
    "LoadFromFiles",
    "SaveToFiles",
    "ClearDatabanks",
    "CreatePortfolio",
    "CustomAnalysis",
    "DeleteFile",
    "CallExternalScript",
    "LogDatabankStats",
    "NeuralNetworkTrainer",
    "Notification",
    "StopAndStart",
    "UpdateData",
    "WaitFor",
    "ApplyMassConfig",
]

STANDARD_DATABANKS = [
    DatabankSpec(name="Results"),
    DatabankSpec(name="Last generation"),
    DatabankSpec(name="Initial population"),
    DatabankSpec(name="Strategies to improve"),
]


def _archive_bytes(archive) -> bytes:
    from quantlab.cfx.writer import CfxWriter

    return CfxWriter.to_bytes(archive)


def _make_task(task_type: str, name: str | None = None) -> CustomProjectTask:
    kwargs = {"type": task_type, "name": name or task_type}
    if task_type == "GoToTask":
        kwargs["goto"] = GoToTask(target="Build", condition="retest_failed")
    return CustomProjectTask(**kwargs)


class TestCatalogCoverage:
    """REQ-25 scenario 1: all 21 catalog task types render."""

    @pytest.mark.parametrize("task_type", ALL_21)
    def test_each_catalog_type_renders_task_xml(self, task_type):
        project = CustomProject(
            name="catalog",
            tasks=[_make_task(task_type)],
            databanks=STANDARD_DATABANKS,
        )

        archive = generate_cfx_archive(project)
        raw = _archive_bytes(archive)

        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            assert "config.xml" in zf.namelist()
            task_xmls = [n for n in zf.namelist() if n.endswith(".xml") and n != "config.xml"]
            assert len(task_xmls) == 1
            # taskXMLFile routing matches the packaged file name.
            cfg = ElementTree.fromstring(zf.read("config.xml"))
            task_el = cfg.find("Tasks/Task")
            assert task_el is not None
            assert task_el.get("type") == task_type
            assert task_el.get("taskXMLFile") == task_xmls[0]
            # The task XML must be valid XML with a <Settings> root.
            task_root = ElementTree.fromstring(zf.read(task_xmls[0]))
            assert task_root.tag == "Settings"

    def test_catalog_exposes_exactly_21_types(self):
        assert len(CATALOG_TYPES) == 21
        assert CATALOG_TYPES == frozenset(ALL_21)

    def test_no_standalone_walkforward_task(self):
        assert "WalkForward" not in CATALOG_TYPES


class TestWalkForwardInsideCrossChecks:
    """REQ-25: Walk-Forward renders inside Retest/Optimize CrossChecks."""

    @pytest.mark.parametrize("task_type", ["Retest", "Optimize"])
    def test_walkforward_inside_crosschecks(self, task_type):
        project = CustomProject(
            name="wf",
            tasks=[
                CustomProjectTask(
                    type=task_type,
                    name=task_type,
                    params={"walkforward_cycles": "12"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )

        archive = generate_cfx_archive(project)
        raw = _archive_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            task_file = f"{task_type}-Task1.xml"
            task_root = ElementTree.fromstring(zf.read(task_file))

        cross_checks = task_root.find("CrossChecks")
        assert cross_checks is not None
        walk_forward = cross_checks.find("WalkForward")
        assert walk_forward is not None
        assert walk_forward.get("enabled") == "true"
        assert walk_forward.get("cycles") == "12"

    def test_walkforward_disabled_when_param_absent(self):
        project = CustomProject(
            name="wf-off",
            tasks=[CustomProjectTask(type="Retest", name="Retest")],
            databanks=STANDARD_DATABANKS,
        )

        archive = generate_cfx_archive(project)
        raw = _archive_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            task_root = ElementTree.fromstring(zf.read("Retest-Task1.xml"))

        cross_checks = task_root.find("CrossChecks")
        assert cross_checks is not None
        walk_forward = cross_checks.find("WalkForward")
        assert walk_forward is not None
        assert walk_forward.get("enabled") == "false"


class TestUnknownTypeRejected:
    """REQ-25 scenario 2: unknown task type raises TaskNotSupportedError."""

    def test_unknown_type_raises_naming_the_type(self):
        project = CustomProject(
            name="unknown",
            tasks=[CustomProjectTask(type="Hologram", name="Hologram")],
            databanks=STANDARD_DATABANKS,
        )

        with pytest.raises(TaskNotSupportedError) as exc:
            generate_cfx_archive(project)
        assert "Hologram" in str(exc.value)

    def test_error_is_a_value_error_subtype(self):
        assert issubclass(TaskNotSupportedError, ValueError)
