"""T3-5 RED tests: Retest and Optimize with full CrossChecks/Optimization dialect."""

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


class TestRetestCrossChecks:
    """Retest: CrossChecks with WalkForward, MonteCarlo, and acceptance settings."""

    def test_retest_walkforward_inside_crosschecks(self):
        project = CustomProject(
            name="retest-wf",
            tasks=[
                CustomProjectTask(
                    type="Retest",
                    name="Retest",
                    params={"walkforward_cycles": "12"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        cross_checks = root.find("CrossChecks")
        assert cross_checks is not None
        wf = cross_checks.find("WalkForward")
        assert wf is not None
        assert wf.get("enabled") == "true"
        assert wf.get("cycles") == "12"

    def test_retest_montecarlo_when_configured(self):
        project = CustomProject(
            name="retest-mc",
            tasks=[
                CustomProjectTask(
                    type="Retest",
                    name="Retest",
                    params={"monte_carlo_runs": "500"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        cross_checks = root.find("CrossChecks")
        mc = cross_checks.find("MonteCarlo")
        assert mc is not None
        assert mc.get("enabled") == "true"
        assert mc.get("simulations") == "500"

    def test_retest_montecarlo_disabled_when_not_configured(self):
        project = CustomProject(
            name="retest-mc-off",
            tasks=[CustomProjectTask(type="Retest", name="Retest")],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        cross_checks = root.find("CrossChecks")
        mc = cross_checks.find("MonteCarlo")
        assert mc is not None
        assert mc.get("enabled") == "false"


class TestOptimizeSerialization:
    """Optimize: full <Optimization> with Source, WalkForward, OptimizationMethod, WhatToParametrize, ManualSettings."""

    def test_emits_optimization_with_source_and_walkforward(self):
        project = CustomProject(
            name="opt",
            tasks=[
                CustomProjectTask(
                    type="Optimize",
                    name="Optimize",
                    params={
                        "sourceType": "0",
                        "sourceRelativePath": "true",
                        "sourcePath": "project.sqx",
                        "walkforwardType": "1",
                        "walkforwardPeriod": "20",
                        "walkforwardOptimization": "15",
                        "walkforwardParam1": "0.5",
                        "walkforwardParam2": "0.3",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        opt = root.find("Optimization")
        assert opt is not None
        assert opt.get("type") == "0"
        assert opt.get("maxOptimizations") == "1000"
        source = opt.find("Source")
        assert source is not None
        assert source.get("type") == "0"
        assert source.get("relativePath") == "true"
        assert source.text == "project.sqx"
        wf = opt.find("WalkForward")
        assert wf is not None
        assert wf.get("type") == "1"
        assert wf.get("period") == "20"
        assert wf.get("optimization") == "15"
        param1 = wf.find("Param1")
        param2 = wf.find("Param2")
        assert param1 is not None and param1.get("value") == "0.5"
        assert param2 is not None and param2.get("value") == "0.3"

    def test_emits_optimization_method_and_what_to_parametrize(self):
        project = CustomProject(
            name="opt2",
            tasks=[
                CustomProjectTask(
                    type="Optimize",
                    name="Optimize",
                    params={
                        "optimizationMethod": "genetic",
                        "whatToParametrizeType": "0",
                        "whatToParametrizeRecommended": "true",
                        "whatToParametrizePeriods": "true",
                        "whatToParametrizeShifts": "false",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        opt = root.find("Optimization")
        assert opt is not None
        om = opt.find("OptimizationMethod")
        assert om is not None
        assert om.get("settings") == "genetic"
        wtp = opt.find("WhatToParametrize")
        assert wtp is not None
        assert wtp.get("type") == "0"
        assert wtp.find("Recommended").text == "true"
        assert wtp.find("Periods").text == "true"
        assert wtp.find("Shifts").text == "false"


class TestOptimizeSimpleOptimization:
    """Optimize: SimpleOptimization parameters."""

    def test_emits_simple_optimization(self):
        project = CustomProject(
            name="opt-so",
            tasks=[
                CustomProjectTask(
                    type="Optimize",
                    name="Optimize",
                    params={
                        "pctToPass": "50",
                        "resultsCount": "100",
                        "stabilityRange": "10",
                    },
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_xml_root(project)
        opt = root.find("Optimization")
        so = opt.find("SimpleOptimization")
        assert so is not None
        assert so.get("type") == "0"
        assert so.get("pctToPass") == "50"
        assert so.get("resultsCount") == "100"
        assert so.get("stabilityRange") == "10"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])