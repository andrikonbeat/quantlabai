"""REQ-43/REQ-44: Retest and Optimize as chained tasks in ONE project load.

A multi-task Custom Project declaring Filtering → Retest → Optimize renders
each task in order in a single CFX archive: the Retest task XML carries its
CrossChecks (Monte Carlo + Walk-Forward), the Optimize task XML carries its
parameter ranges + Walk-Forward settings, and SQX executes them chained in one
load. Standalone ``Retester.run`` / ``Optimizer.run`` signatures stay
unchanged (scenario 2 of both requirements).
"""

from __future__ import annotations

import inspect
import zipfile
from io import BytesIO
from xml.etree import ElementTree

from quantlab.customproject.generator import generate_cfx_archive
from quantlab.customproject.models import (
    CustomProject,
    CustomProjectTask,
    DatabankSpec,
)
from quantlab.phase4.optimizer import Optimizer
from quantlab.phase4.retester import Retester

STANDARD_DATABANKS = [
    DatabankSpec(name="Results"),
    DatabankSpec(name="Last generation"),
    DatabankSpec(name="Initial population"),
    DatabankSpec(name="Strategies to improve"),
]


def _archive_bytes(archive) -> bytes:
    from quantlab.cfx.writer import CfxWriter

    return CfxWriter.to_bytes(archive)


def _chain_project() -> CustomProject:
    """Filtering → Retest → Optimize in one project load (REQ-43/44)."""
    return CustomProject(
        name="chained",
        tasks=[
            CustomProjectTask(
                type="Filtering",
                name="Filtering",
                source_databank="Results",
            ),
            CustomProjectTask(
                type="Retest",
                name="Retest",
                source_databank="Results",
                params={
                    "walkforward_cycles": "12",
                    "monte_carlo_runs": "500",
                },
            ),
            CustomProjectTask(
                type="Optimize",
                name="Optimize",
                source_databank="Results",
                params={
                    "walkforward_cycles": "12",
                    "optimize_params": "maxOptimizations=100",
                },
            ),
        ],
        databanks=STANDARD_DATABANKS,
    )


def _annotation_name(annotation: object) -> str:
    """Resolve a parameter annotation to its type name.

    Forward references arrive as plain strings (e.g. ``"RetesterConfig"``);
    resolved annotations arrive as classes.
    """
    if isinstance(annotation, str):
        return annotation
    return getattr(annotation, "__name__", str(annotation))


def _task_root(archive, task_file: str) -> ElementTree.Element:
    raw = _archive_bytes(archive)
    with zipfile.ZipFile(BytesIO(raw), "r") as zf:
        return ElementTree.fromstring(zf.read(task_file))


class TestChainedTasksInOneLoad:
    """REQ-43/44 scenario 1: Filtering → Retest → Optimize chain."""

    def test_chain_emits_three_tasks_in_order(self) -> None:
        """GIVEN a multi-task project declaring Filtering → Retest → Optimize
        WHEN the generator emits the project
        THEN the three tasks appear in order in ONE archive.
        """
        archive = generate_cfx_archive(_chain_project())
        raw = _archive_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            cfg = ElementTree.fromstring(zf.read("config.xml"))
        tasks = [t.get("type") for t in cfg.findall("Tasks/Task")]
        assert tasks == ["Filtering", "Retest", "Optimize"]

    def test_retest_crosschecks_carry_monte_carlo_and_walkforward(self) -> None:
        """GIVEN a Retest task with MC + WF params
        WHEN the generator emits it
        THEN its CrossChecks carry Monte Carlo and Walk-Forward settings.
        """
        root = _task_root(generate_cfx_archive(_chain_project()), "Retest-Task1.xml")
        cross = root.find("CrossChecks")
        assert cross is not None

        walk = cross.find("WalkForward")
        assert walk is not None
        assert walk.get("enabled") == "true"
        assert walk.get("cycles") == "12"

        mc = cross.find("MonteCarlo")
        assert mc is not None
        assert mc.get("enabled") == "true"
        assert mc.get("simulations") == "500"

    def test_optimize_crosschecks_carry_param_ranges_and_walkforward(self) -> None:
        """GIVEN an Optimize task after Retest
        WHEN the generator emits it
        THEN its CrossChecks carry parameter ranges and Walk-Forward.
        """
        root = _task_root(
            generate_cfx_archive(_chain_project()), "Optimize-Task1.xml"
        )
        cross = root.find("CrossChecks")
        assert cross is not None

        walk = cross.find("WalkForward")
        assert walk is not None
        assert walk.get("enabled") == "true"

        params = cross.find("Parameters")
        assert params is not None
        assert params.get("enabled") == "true"
        assert params.get("maxOptimizations") == "100"

    def test_retest_without_mc_param_keeps_walkforward_only(self) -> None:
        """GIVEN a Retest task without Monte Carlo params
        WHEN the generator emits it
        THEN Monte Carlo is disabled (fail-safe, no ghost MC).
        """
        project = CustomProject(
            name="retest-only",
            tasks=[
                CustomProjectTask(
                    type="Retest",
                    name="Retest",
                    params={"walkforward_cycles": "8"},
                )
            ],
            databanks=STANDARD_DATABANKS,
        )
        root = _task_root(generate_cfx_archive(project), "Retest-Task1.xml")
        mc = root.find("CrossChecks/MonteCarlo")
        assert mc is not None
        assert mc.get("enabled") == "false"


class TestStandalonePathsPreserved:
    """REQ-43/44 scenario 2: standalone run() signatures unchanged."""

    def test_retester_run_signature_unchanged(self) -> None:
        """GIVEN RetesterAutomation invoked standalone
        WHEN run(config, campaign_name, output_dir, timeout) is called
        THEN the signature is identical to the pre-change contract.
        """
        params = inspect.signature(Retester.run).parameters
        assert list(params) == [
            "self",
            "config",
            "campaign_name",
            "output_dir",
            "timeout",
        ]
        assert _annotation_name(params["config"].annotation) == "RetesterConfig"

    def test_optimizer_run_signature_unchanged(self) -> None:
        """GIVEN Optimizer invoked standalone
        WHEN run(config, campaign_name, output_dir, timeout) is called
        THEN the signature is identical to the pre-change contract.
        """
        params = inspect.signature(Optimizer.run).parameters
        assert list(params) == [
            "self",
            "config",
            "campaign_name",
            "output_dir",
            "timeout",
        ]
        assert _annotation_name(params["config"].annotation) == "OptimizerConfig"
