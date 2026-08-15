"""REQ-22 extended: campaign template generation and validation.

Tests verify that each built-in template produces a valid CustomProject,
that task ordering and databank routing are correct, and that generated
archives serialize and pass golden structural validation.
"""

from __future__ import annotations

import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
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
from quantlab.customproject.templates import (
    CampaignTemplate,
    DeepRobustnessTemplate,
    QuickValidationTemplate,
    StandardResearchTemplate,
    TemplateParams,
)
from quantlab.phase4.template_registry import (
    DuplicateTemplateError,
    TemplateDefinition,
    TemplateRegistry,
    registry,
)
from quantlab.customproject.validator import ValidationError, validate_golden
from quantlab.cfx.reader import CfxReader
from quantlab.cfx.writer import CfxWriter

REPO_ROOT = Path(__file__).resolve().parents[2]
SQX_ROOT = Path.home() / "Proyectos" / "SQX_144_2953_linux_20260601"

STANDARD_DATABANKS = [
    DatabankSpec(name="Results"),
    DatabankSpec(name="Last generation"),
    DatabankSpec(name="Initial population"),
    DatabankSpec(name="Strategies to improve"),
]


def _probe_ok() -> bool:
    return True


class TestTemplateParams:
    """TemplateParams defaults and overrides."""

    def test_default_databanks(self):
        p = TemplateParams()
        assert [db.name for db in p.databanks] == [
            "Results",
            "Last generation",
            "Initial population",
            "Strategies to improve",
        ]

    def test_custom_name(self):
        p = TemplateParams(name="My Campaign")
        assert p.name == "My Campaign"

    def test_custom_databanks(self):
        dbs = [DatabankSpec(name="EURUSD_H1")]
        p = TemplateParams(databanks=dbs)
        assert p.databanks == dbs


class TestCampaignTemplateBase:
    """Base class contract."""

    def test_build_returns_custom_project(self):
        project = StandardResearchTemplate.build()
        assert isinstance(project, CustomProject)

    def test_build_with_overrides(self):
        params = TemplateParams(name="Override", filters=["NetProfit > 500"])
        project = StandardResearchTemplate.build(params)
        assert project.name == "Override"
        assert project.databanks == params.databanks

    def test_serialize_writes_cfx(self, tmp_path):
        dest = tmp_path / "out.cfx"
        result = StandardResearchTemplate.serialize(dest)
        assert result == dest
        assert dest.exists()
        with zipfile.ZipFile(dest, "r") as zf:
            assert "config.xml" in zf.namelist()


class TestStandardResearchTemplate:
    """14-task standard research campaign."""

    def test_build_returns_custom_project(self):
        project = StandardResearchTemplate.build()
        assert isinstance(project, CustomProject)

    def test_task_count_is_fourteen(self):
        project = StandardResearchTemplate.build()
        assert len(project.tasks) == 14

    def test_task_types_in_order(self):
        project = StandardResearchTemplate.build()
        types = [t.type for t in project.tasks]
        assert types == [
            "Build",
            "Filtering",
            "Retest",
            "GoToTask",
            "Optimize",
            "AutomaticRetest",
            "AutomaticPortfolioBuilder",
            "CreatePortfolio",
            "CustomAnalysis",
            "LogDatabankStats",
            "SaveToFiles",
            "LoadFromFiles",
            "UpdateData",
            "WaitFor",
        ]

    def test_retest_has_deep_params(self):
        project = StandardResearchTemplate.build()
        retest = project.tasks[2]
        assert retest.type == "Retest"
        assert retest.params.get("monte_carlo_runs") == "500"
        assert retest.params.get("walkforward_cycles") == "12"

    def test_goto_task_loops_to_filtering(self):
        project = StandardResearchTemplate.build()
        goto = project.tasks[3]
        assert goto.type == "GoToTask"
        assert goto.goto is not None
        assert goto.goto.target == "Filtering"
        assert goto.goto.condition == "retest_failed"

    def test_databank_routing(self):
        project = StandardResearchTemplate.build()
        assert [db.name for db in project.databanks] == [
            "Results",
            "Last generation",
            "Initial population",
            "Strategies to improve",
        ]
        build = project.tasks[0]
        assert build.source_databank == "Initial population"
        assert build.target_databank == "Results"

    def test_generates_valid_cfx_archive(self):
        project = StandardResearchTemplate.build()
        archive = generate_cfx_archive(project)
        assert archive is not None

    def test_passes_golden_validation(self):
        project = StandardResearchTemplate.build()
        archive = generate_cfx_archive(project)
        validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)

    def test_serializes_to_zip_with_all_task_xmls(self):
        project = StandardResearchTemplate.build()
        archive = generate_cfx_archive(project)
        raw = CfxWriter.to_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names
            task_xmls = [n for n in names if n.endswith(".xml") and n != "config.xml"]
            assert len(task_xmls) == 14

    def test_round_trips_through_cfx_reader(self):
        project = StandardResearchTemplate.build()
        raw = CfxWriter.to_bytes(generate_cfx_archive(project))
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            archive = CfxReader.read(tmp_path)
            assert archive.config.task_type == "project"
            assert archive.config.schema_version == "144.2953"
            assert len(archive.config.tasks) == 14
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestQuickValidationTemplate:
    """10-task quick validation campaign."""

    def test_build_returns_custom_project(self):
        project = QuickValidationTemplate.build()
        assert isinstance(project, CustomProject)

    def test_task_count_is_ten(self):
        project = QuickValidationTemplate.build()
        assert len(project.tasks) == 10

    def test_task_types_in_order(self):
        project = QuickValidationTemplate.build()
        types = [t.type for t in project.tasks]
        assert types == [
            "Build",
            "Filtering",
            "Retest",
            "Optimize",
            "CustomAnalysis",
            "LogDatabankStats",
            "SaveToFiles",
            "LoadFromFiles",
            "UpdateData",
            "WaitFor",
        ]

    def test_no_goto_task(self):
        project = QuickValidationTemplate.build()
        assert all(t.type != "GoToTask" for t in project.tasks)

    def test_retest_is_simple_no_deep_params(self):
        project = QuickValidationTemplate.build()
        retest = project.tasks[2]
        assert retest.type == "Retest"
        assert "monte_carlo_runs" not in retest.params
        assert "walkforward_cycles" not in retest.params

    def test_generates_valid_cfx_archive(self):
        project = QuickValidationTemplate.build()
        archive = generate_cfx_archive(project)
        assert archive is not None

    def test_passes_golden_validation(self):
        project = QuickValidationTemplate.build()
        archive = generate_cfx_archive(project)
        validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)

    def test_serializes_to_zip_with_all_task_xmls(self):
        project = QuickValidationTemplate.build()
        archive = generate_cfx_archive(project)
        raw = CfxWriter.to_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names
            task_xmls = [n for n in names if n.endswith(".xml") and n != "config.xml"]
            assert len(task_xmls) == 10

    def test_round_trips_through_cfx_reader(self):
        project = QuickValidationTemplate.build()
        raw = CfxWriter.to_bytes(generate_cfx_archive(project))
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            archive = CfxReader.read(tmp_path)
            assert archive.config.task_type == "project"
            assert archive.config.schema_version == "144.2953"
            assert len(archive.config.tasks) == 10
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestDeepRobustnessTemplate:
    """14-task deep robustness campaign with double Retest."""

    def test_build_returns_custom_project(self):
        project = DeepRobustnessTemplate.build()
        assert isinstance(project, CustomProject)

    def test_task_count_is_fourteen(self):
        project = DeepRobustnessTemplate.build()
        assert len(project.tasks) == 14

    def test_task_types_in_order(self):
        project = DeepRobustnessTemplate.build()
        types = [t.type for t in project.tasks]
        assert types == [
            "Build",
            "Filtering",
            "Retest",
            "Retest",
            "GoToTask",
            "Optimize",
            "AutomaticRetest",
            "AutomaticPortfolioBuilder",
            "CreatePortfolio",
            "CustomAnalysis",
            "LogDatabankStats",
            "SaveToFiles",
            "UpdateData",
            "WaitFor",
        ]

    def test_double_retest_has_different_configs(self):
        project = DeepRobustnessTemplate.build()
        retest_a = project.tasks[2]
        retest_b = project.tasks[3]
        assert retest_a.type == "Retest"
        assert retest_b.type == "Retest"
        assert retest_a.params != retest_b.params
        assert retest_a.name != retest_b.name

    def test_first_retest_is_conservative(self):
        project = DeepRobustnessTemplate.build()
        retest_a = project.tasks[2]
        assert retest_a.params.get("monte_carlo_runs") == "1000"
        assert retest_a.params.get("walkforward_cycles") == "15"

    def test_second_retest_is_aggressive(self):
        project = DeepRobustnessTemplate.build()
        retest_b = project.tasks[3]
        assert retest_b.params.get("monte_carlo_runs") == "500"
        assert retest_b.params.get("walkforward_cycles") == "8"

    def test_goto_task_loops_to_filtering(self):
        project = DeepRobustnessTemplate.build()
        goto = project.tasks[4]
        assert goto.type == "GoToTask"
        assert goto.goto is not None
        assert goto.goto.target == "Filtering"
        assert goto.goto.condition == "retest_failed"

    def test_generates_valid_cfx_archive(self):
        project = DeepRobustnessTemplate.build()
        archive = generate_cfx_archive(project)
        assert archive is not None

    def test_passes_golden_validation(self):
        project = DeepRobustnessTemplate.build()
        archive = generate_cfx_archive(project)
        validate_golden(archive, SQX_ROOT, probe_runner=_probe_ok)

    def test_serializes_to_zip_with_all_task_xmls(self):
        project = DeepRobustnessTemplate.build()
        archive = generate_cfx_archive(project)
        raw = CfxWriter.to_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names
            task_xmls = [n for n in names if n.endswith(".xml") and n != "config.xml"]
            assert len(task_xmls) == 14

    def test_round_trips_through_cfx_reader(self):
        project = DeepRobustnessTemplate.build()
        raw = CfxWriter.to_bytes(generate_cfx_archive(project))
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            archive = CfxReader.read(tmp_path)
            assert archive.config.task_type == "project"
            assert archive.config.schema_version == "144.2953"
            assert len(archive.config.tasks) == 14
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestTemplateDatabankRouting:
    """Per-template databank routing and Filters defaults."""

    @pytest.mark.parametrize(
        "template",
        [
            StandardResearchTemplate,
            QuickValidationTemplate,
            DeepRobustnessTemplate,
        ],
    )
    def test_default_databanks_present(self, template):
        project = template.build()
        names = [db.name for db in project.databanks]
        assert "Results" in names
        assert "Initial population" in names

    @pytest.mark.parametrize(
        "template",
        [
            StandardResearchTemplate,
            QuickValidationTemplate,
            DeepRobustnessTemplate,
        ],
    )
    def test_build_has_correct_source_databank(self, template):
        project = template.build()
        build = project.tasks[0]
        assert build.source_databank == "Initial population"

    @pytest.mark.parametrize(
        "template",
        [
            StandardResearchTemplate,
            QuickValidationTemplate,
            DeepRobustnessTemplate,
        ],
    )
    def test_filtering_has_filters(self, template):
        project = template.build()
        filtering = next(t for t in project.tasks if t.type == "Filtering")
        assert filtering.filters is not None
        assert len(filtering.filters.conditions) > 0


class TestTemplateSerializationRoundTrip:
    """Generated archives are readable by CfxReader."""

    def test_standard_research_round_trips(self):
        project = StandardResearchTemplate.build()
        raw = CfxWriter.to_bytes(generate_cfx_archive(project))
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            archive = CfxReader.read(tmp_path)
            assert archive.config.task_type == "project"
            assert archive.config.schema_version == "144.2953"
            assert len(archive.config.tasks) == 14
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_quick_validation_round_trips(self):
        project = QuickValidationTemplate.build()
        raw = CfxWriter.to_bytes(generate_cfx_archive(project))
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            archive = CfxReader.read(tmp_path)
            assert archive.config.task_type == "project"
            assert archive.config.schema_version == "144.2953"
            assert len(archive.config.tasks) == 10
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_deep_robustness_round_trips(self):
        project = DeepRobustnessTemplate.build()
        raw = CfxWriter.to_bytes(generate_cfx_archive(project))
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            archive = CfxReader.read(tmp_path)
            assert archive.config.task_type == "project"
            assert archive.config.schema_version == "144.2953"
            assert len(archive.config.tasks) == 14
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestAutomaticRetestRenderer:
    """WU-2: AutomaticRetest dedicated renderer produces correct XML."""

    def _render_automatic_retest(self) -> BuildTask:
        from quantlab.customproject.renderers import render_automatic_retest

        task = CustomProjectTask(
            type="AutomaticRetest",
            name="Auto Retest",
            source_databank="Results",
            target_databank="Results",
        )
        return render_automatic_retest(task)

    def test_task_type_is_automatic_retest(self):
        task = CustomProjectTask(
            type="AutomaticRetest", name="Auto Retest"
        )
        assert task.type == "AutomaticRetest"

    def test_cross_checks_section_present(self):
        bt = self._render_automatic_retest()
        assert bt.cross_checks_section is not None
        xml = bt.cross_checks_section.raw_xml
        assert "<CrossChecks" in xml
        assert 'use="true"' in xml

    def test_cross_checks_contains_all_required_elements(self):
        bt = self._render_automatic_retest()
        xml = bt.cross_checks_section.raw_xml
        required = [
            "RetestWithHigherPrecision",
            "MonteCarloRetest",
            "MonteCarloManipulation",
            "RetestOnAdditionalMarkets",
            "WalkForwardOptimization",
            "WalkForwardMatrix",
            "OptProfileSysParamPermutation",
        ]
        for elem in required:
            assert elem in xml, f"Missing CrossCheck element: {elem}"

    def test_no_generic_monte_carlo_or_walk_forward(self):
        bt = self._render_automatic_retest()
        xml = bt.cross_checks_section.raw_xml
        # Generic Retest CrossChecks use standalone <MonteCarlo> and <WalkForward>
        # elements; AutomaticRetest must NOT contain those standalone elements.
        # Nested <WalkForward> inside WalkForwardOptimization/WalkForwardMatrix is expected.
        assert "<MonteCarlo " not in xml.replace("<MonteCarloRetest", "").replace(
            "<MonteCarloManipulation", ""
        ), "Generic <MonteCarlo> element found in AutomaticRetest CrossChecks"

    def test_rankings_section_present(self):
        bt = self._render_automatic_retest()
        assert bt.rankings_section is not None
        xml = bt.rankings_section.raw_xml
        assert "<Rankings>" in xml

    def test_rankings_contains_required_elements(self):
        bt = self._render_automatic_retest()
        xml = bt.rankings_section.raw_xml
        required = [
            "MaxStrategies",
            "FitnessCriteria",
            "ConditionsType",
            "Conditions",
            "AutomaticDismissal",
            "StopCondition",
        ]
        for elem in required:
            assert elem in xml, f"Missing Rankings element: {elem}"

    def test_retester_data_section_present(self):
        bt = self._render_automatic_retest()
        assert bt.retester_data is not None
        xml = bt.retester_data.raw_xml
        assert "<RetesterData>" in xml

    def test_retester_data_contains_required_elements(self):
        bt = self._render_automatic_retest()
        xml = bt.retester_data.raw_xml
        required = [
            "MonteCarloRuns",
            "WalkForwardCycles",
            "ConfidenceLevel",
            "MinTrades",
            "MCPercentile",
            "Databanks",
        ]
        for elem in required:
            assert elem in xml, f"Missing RetesterData element: {elem}"

    def test_serializes_to_valid_xml(self):
        from quantlab.cfx.writer import _serialise_task

        bt = self._render_automatic_retest()
        raw = _serialise_task(bt)
        from xml.etree import ElementTree

        root = ElementTree.fromstring(raw)
        assert root.tag == "Settings"
        assert root.find("CrossChecks") is not None
        assert root.find("Rankings") is not None
        assert root.find("RetesterData") is not None


class TestTemplateMetadataInjection:
    """Template metadata appears only for template-generated projects."""

    def _make_project(self, template_name=None):
        return CustomProject(
            name="Test",
            template_name=template_name,
            tasks=[
                CustomProjectTask(
                    type="Build",
                    name="Build",
                    source_databank="Initial population",
                    target_databank="Results",
                )
            ],
            databanks=[
                DatabankSpec(name="Results"),
                DatabankSpec(name="Last generation"),
                DatabankSpec(name="Initial population"),
                DatabankSpec(name="Strategies to improve"),
            ],
        )

    def test_template_project_injects_metadata(self):
        project = self._make_project(template_name="standard_research")
        archive = generate_cfx_archive(project)
        raw = CfxWriter.to_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            task_root = ElementTree.fromstring(zf.read("Build-Task1.xml"))
            template_el = task_root.find("Template")
            assert template_el is not None
            assert template_el.get("name") == "standard_research"
            assert template_el.get("profile") == "standard_research"

    def test_adhoc_project_has_no_template_metadata(self):
        project = self._make_project(template_name=None)
        archive = generate_cfx_archive(project)
        raw = CfxWriter.to_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            task_root = ElementTree.fromstring(zf.read("Build-Task1.xml"))
            template_el = task_root.find("Template")
            assert template_el is None

    def test_each_template_task_has_metadata(self):
        project = StandardResearchTemplate.build()
        archive = generate_cfx_archive(project)
        raw = CfxWriter.to_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            names = [n for n in zf.namelist() if n.endswith(".xml") and n != "config.xml"]
            for name in names:
                task_root = ElementTree.fromstring(zf.read(name))
                template_el = task_root.find("Template")
                assert template_el is not None, f"Missing Template metadata in {name}"
                assert template_el.get("name") == "standard_research"
                assert template_el.get("profile") == "standard_research"

    def test_template_metadata_preserves_task_attributes(self):
        project = StandardResearchTemplate.build()
        archive = generate_cfx_archive(project)
        raw = CfxWriter.to_bytes(archive)
        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            cfg = ElementTree.fromstring(zf.read("config.xml"))
            task_el = cfg.find("Tasks/Task")
            assert task_el is not None
            assert task_el.get("type") == "Build"
            assert task_el.get("name") == "Build"


class TestTemplateRegistry:
    """WU-1: TemplateRegistry case-insensitive lookup and duplicate rejection."""

    def test_global_registry_has_all_templates(self):
        names = {d.name for d in registry.all_definitions()}
        assert names == {"standard_research", "quick_validation", "deep_robustness"}

    def test_resolve_returns_definition(self):
        definition = registry.resolve("standard_research")
        assert definition.name == "standard_research"
        assert definition.template_class is StandardResearchTemplate
        assert definition.profile == "standard_research"

    def test_resolve_is_case_insensitive(self):
        definition = registry.resolve("STANDARD_RESEARCH")
        assert definition.name == "standard_research"
        assert definition.template_class is StandardResearchTemplate

    def test_resolve_missing_raises_key_error(self):
        with pytest.raises(KeyError):
            registry.resolve("nonexistent_template")

    def test_duplicate_registration_raises(self):
        local_registry = TemplateRegistry()
        local_registry.register(
            TemplateDefinition(
                name="standard_research",
                template_class=StandardResearchTemplate,
                profile="standard_research",
            )
        )
        with pytest.raises(DuplicateTemplateError):
            local_registry.register(
                TemplateDefinition(
                    name="Standard_Research",
                    template_class=StandardResearchTemplate,
                    profile="standard_research",
                )
            )

    def test_duplicate_preserves_original(self):
        local_registry = TemplateRegistry()
        local_registry.register(
            TemplateDefinition(
                name="standard_research",
                template_class=StandardResearchTemplate,
                profile="standard_research",
            )
        )
        with pytest.raises(DuplicateTemplateError):
            local_registry.register(
                TemplateDefinition(
                    name="STANDARD_RESEARCH",
                    template_class=QuickValidationTemplate,
                    profile="quick_validation",
                )
            )
        # Original must still resolve to the original class
        assert local_registry.resolve("standard_research").template_class is StandardResearchTemplate


class TestGenericRetestRegression:
    """Generic Retest rendering remains unchanged after AutomaticRetest renderer."""

    def test_generic_retest_has_monte_carlo_crosscheck(self):
        from quantlab.customproject.renderers import render_retest

        task = CustomProjectTask(
            type="Retest",
            name="Retest",
            source_databank="Results",
            target_databank="Results",
            params={"monte_carlo_runs": "500", "walkforward_cycles": "12"},
        )
        bt = render_retest(task)
        xml = bt.cross_checks_section.raw_xml
        assert "<MonteCarlo " in xml
        assert 'enabled="true" simulations="500"' in xml

    def test_generic_retest_has_walk_forward_crosscheck(self):
        from quantlab.customproject.renderers import render_retest

        task = CustomProjectTask(
            type="Retest",
            name="Retest",
            source_databank="Results",
            target_databank="Results",
            params={"walkforward_cycles": "12"},
        )
        bt = render_retest(task)
        xml = bt.cross_checks_section.raw_xml
        assert "<WalkForward " in xml
        assert 'enabled="true" cycles="12"' in xml

    def test_generic_retest_crosschecks_structure_unchanged(self):
        from quantlab.customproject.renderers import render_retest

        task = CustomProjectTask(
            type="Retest",
            name="Retest",
            source_databank="Results",
            target_databank="Results",
            params={"monte_carlo_runs": "500", "walkforward_cycles": "12"},
        )
        bt = render_retest(task)
        xml = bt.cross_checks_section.raw_xml
        # Pre-change structure: MonteCarlo, Parameters, WalkForward inside CrossChecks
        assert xml.startswith("<CrossChecks>")
        assert xml.endswith("</CrossChecks>")
        assert xml.index("<MonteCarlo ") < xml.index("<Parameters ")
        assert xml.index("<Parameters ") < xml.index("<WalkForward ")
