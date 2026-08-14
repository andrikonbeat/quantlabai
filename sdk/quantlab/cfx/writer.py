"""CFX archive writer — serialises CfxArchive models to .cfx ZIP files.

Produces ZIP archives with ZIP_DEFLATED compression and UTF-8 filename
encoding. All XML output uses UTF-8 without an XML declaration to match
the existing SQX convention.
"""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import quoteattr

from quantlab.cfx.models import (
    AtmConfig,
    AutomaticPortfolioBuilderConfig,
    BlockConfig,
    BuildTask,
    CfxArchive,
    CfxConfig,
    CfxProject,
    CrossChecksConfig,
    DataBankConfig,
    DatabanksConfig,
    OptimizationConfig,
    OptimizationParametersConfig,
    PortfolioSettingsConfig,
    RankingsConfig,
    ResourceConfig,
    RetesterDataConfig,
    SettingsSection,
    TaskMeta,
    WalkForwardConfig,
)


def _append_complex_section(
    parent: ElementTree.Element,
    tag: str,
    config: (
        BlockConfig
        | AtmConfig
        | DataBankConfig
        | ResourceConfig
        | AutomaticPortfolioBuilderConfig
        | OptimizationConfig
        | OptimizationParametersConfig
        | WalkForwardConfig
        | DatabanksConfig
        | RankingsConfig
        | CrossChecksConfig
        | RetesterDataConfig
        | None
    ),
) -> None:
    """Append a complex section via raw XML passthrough."""
    if config is None or not config.raw_xml:
        return
    try:
        el = ElementTree.fromstring(config.raw_xml)
        parent.append(el)
    except ElementTree.ParseError:
        pass


# ── Phase 4: Builder-style setter methods ─────────────────────────────


class CfxWriter:
    """Writes CfxArchive models to .cfx ZIP archives."""

    @staticmethod
    def write(archive: CfxArchive, path: str | Path) -> None:
        """Serialise a CfxArchive to a .cfx file on disk.

        Args:
            archive: The typed archive model to serialise.
            path: Destination filesystem path (should end in .cfx).
        """
        buffer = CfxWriter._build_zip(archive)
        Path(path).write_bytes(buffer.getvalue())

    @staticmethod
    def dry_run(archive: CfxArchive) -> str:
        """Serialise a CfxArchive to a JSON string without writing a file.

        Returns:
            A JSON string representation of the archive model.
        """
        return archive.model_dump_json(indent=2, by_alias=True)

    @staticmethod
    def to_bytes(archive: CfxArchive) -> bytes:
        """Serialise to in-memory ZIP bytes (useful for testing)."""
        return CfxWriter._build_zip(archive).getvalue()

    @staticmethod
    def _build_zip(archive: CfxArchive) -> BytesIO:
        """Build an in-memory ZIP file from the archive model."""
        buf = BytesIO()

        with zipfile.ZipFile(
            buf,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as zf:
            config = archive.config

            if isinstance(config, CfxConfig):
                _write_config_archive(zf, config, archive.task_files or None)
            elif isinstance(config, CfxProject):
                _write_project_archive(zf, config)
            else:
                raise TypeError(f"Unknown config type: {type(config).__name__}")

        return buf

    # ── Phase 4 Builder Methods ──────────────────────────────────────────

    @staticmethod
    def set_automatic_portfolio_builder(
        task: BuildTask,
        generations: int,
        population: int,
        fitness: str,
        min_strategies: int = 1,
        max_strategies: int | None = None,
        rebalancing: str = "Monthly",
    ) -> BuildTask:
        """Set Automatic Portfolio Builder configuration.

        Args:
            task: BuildTask to modify.
            generations: Number of genetic generations.
            population: Population size.
            fitness: Fitness function name.
            min_strategies: Minimum strategies in portfolio.
            max_strategies: Maximum strategies in portfolio.
            rebalancing: Rebalancing period.

        Returns:
            Modified BuildTask (for chaining).
        """
        xml = f"""<AutomaticPortfolioBuilder>
  <Generations value="{generations}"/>
  <Population value="{population}"/>
  <Fitness value="{fitness}"/>
  <MinStrategies value="{min_strategies}"/>
  {f'<MaxStrategies value="{max_strategies}"/>' if max_strategies else ''}
  <Rebalancing value="{rebalancing}"/>
</AutomaticPortfolioBuilder>"""
        task.automatic_portfolio_builder = AutomaticPortfolioBuilderConfig(raw_xml=xml)
        return task

    @staticmethod
    def set_portfolio_settings(
        task: BuildTask,
        weight_constraints: dict[str, str] | None = None,
    ) -> BuildTask:
        """Set Portfolio Settings.

        Args:
            task: BuildTask to modify.
            weight_constraints: Optional mapping of strategy_id -> constraint.

        Returns:
            Modified BuildTask.
        """
        xml = "<PortfolioSettings>"
        if weight_constraints:
            for sid, constraint in weight_constraints.items():
                xml += f'<Strategy id="{sid}" constraint="{constraint}"/>'
        xml += "</PortfolioSettings>"
        task.portfolio_settings = PortfolioSettingsConfig(raw_xml=xml)
        return task

    @staticmethod
    def set_optimization(
        task: BuildTask,
        method: str = "Genetic",
        objective_function: str = "NetProfit",
        walkforward_cycles: int = 5,
        walkforward_oot_ratio: float = 0.3,
    ) -> BuildTask:
        """Set Optimization configuration.

        Args:
            task: BuildTask to modify.
            method: Optimization method (Genetic, BruteForce, Grid).
            objective_function: Fitness function to optimize.
            walkforward_cycles: Number of walk-forward cycles.
            walkforward_oot_ratio: Out-of-sample ratio.

        Returns:
            Modified BuildTask.
        """
        xml = f"""<Optimization>
  <Method value="{method}"/>
  <ObjectiveFunction value="{objective_function}"/>
  <WalkforwardCycles value="{walkforward_cycles}"/>
  <WalkforwardOOTRatio value="{walkforward_oot_ratio}"/>
</Optimization>"""
        task.optimization = OptimizationConfig(raw_xml=xml)
        return task

    @staticmethod
    def set_optimization_parameters(
        task: BuildTask,
        parameters: dict[str, dict[str, float]],
    ) -> BuildTask:
        """Set Optimization Parameters ranges.

        Args:
            task: BuildTask to modify.
            parameters: Dict of param_name -> {min, max, step}.

        Returns:
            Modified BuildTask.
        """
        xml = "<OptimizationParameters>"
        for name, rng in parameters.items():
            xml += f"""<Parameter name="{name}" min="{rng['min']}" max="{rng['max']}" step="{rng['step']}"/>"""
        xml += "</OptimizationParameters>"
        task.optimization_parameters = OptimizationParametersConfig(raw_xml=xml)
        return task

    @staticmethod
    def set_walkforward(
        task: BuildTask,
        cycles: int,
        oot_ratio: float,
        anchored: bool = False,
    ) -> BuildTask:
        """Set Walk-Forward configuration.

        Args:
            task: BuildTask to modify.
            cycles: Number of walk-forward cycles.
            oot_ratio: Out-of-sample ratio.
            anchored: Whether to use anchored walk-forward.

        Returns:
            Modified BuildTask.
        """
        xml = f"""<WalkForward>
  <Cycles value="{cycles}"/>
  <OOTRatio value="{oot_ratio}"/>
  <Anchored value="{str(anchored).lower()}"/>
</WalkForward>"""
        task.walk_forward = WalkForwardConfig(raw_xml=xml)
        return task

    @staticmethod
    def set_databanks(
        task: BuildTask,
        databanks: list[str],
    ) -> BuildTask:
        """Set Databanks for optimizer/retester.

        Args:
            task: BuildTask to modify.
            databanks: List of databank names (e.g., ["EURUSD_H1", "GBPUSD_H1"]).

        Returns:
            Modified BuildTask.
        """
        xml = "<Databanks>"
        for i, db in enumerate(databanks, 1):
            xml += f'<Databank index="{i}" name="{db}" enabled="true"/>'
        xml += "</Databanks>"
        task.databanks_section = DatabanksConfig(raw_xml=xml)
        return task

    @staticmethod
    def set_rankings(
        task: BuildTask,
        metrics: list[str],
        min_trades: int = 30,
    ) -> BuildTask:
        """Set Retester Rankings configuration.

        Args:
            task: BuildTask to modify.
            metrics: List of ranking metric names.
            min_trades: Minimum trades for ranking eligibility.

        Returns:
            Modified BuildTask.
        """
        xml = f"""<Rankings>
  <MinTrades value="{min_trades}"/>"""
        for metric in metrics:
            xml += f'\n  <Metric name="{metric}"/>'
        xml += "\n</Rankings>"
        task.rankings_section = RankingsConfig(raw_xml=xml)
        return task

    @staticmethod
    def set_crosschecks(
        task: BuildTask,
        mc_enabled: bool,
        wf_enabled: bool,
        mc_runs: int = 100,
        mc_percentile: int = 95,
        wf_cycles: int = 5,
        confidence_level: float = 0.95,
    ) -> BuildTask:
        """Set Retester Cross-Checks configuration.

        Args:
            task: BuildTask to modify.
            mc_enabled: Enable Monte Carlo.
            mc_runs: Number of Monte Carlo runs.
            mc_percentile: Monte Carlo percentile.
            wf_enabled: Enable Walk-Forward.
            wf_cycles: Walk-Forward cycles.
            confidence_level: Confidence level for statistics.

        Returns:
            Modified BuildTask.
        """
        xml = f"""<CrossChecks>
  <MonteCarlo enabled="{str(mc_enabled).lower()}" runs="{mc_runs}" percentile="{mc_percentile}"/>
  <WalkForward enabled="{str(wf_enabled).lower()}" cycles="{wf_cycles}"/>
  <ConfidenceLevel value="{confidence_level}"/>
</CrossChecks>"""
        task.cross_checks_section = CrossChecksConfig(raw_xml=xml)
        return task

    @staticmethod
    def set_retester_data(
        task: BuildTask,
        databanks: list[str],
        monte_carlo_runs: int = 100,
        walkforward_cycles: int = 5,
        confidence_level: float = 0.95,
        min_trades: int = 30,
        mc_percentile: int = 95,
    ) -> BuildTask:
        """Set Retester Data configuration.

        Args:
            task: BuildTask to modify.
            databanks: List of databank names.
            monte_carlo_runs: Number of Monte Carlo runs.
            walkforward_cycles: Number of walk-forward cycles.
            confidence_level: Statistical confidence level.
            min_trades: Minimum trades for analysis.
            mc_percentile: Monte Carlo percentile.

        Returns:
            Modified BuildTask.
        """
        xml = f"""<RetesterData>
  <MonteCarloRuns value="{monte_carlo_runs}"/>
  <WalkforwardCycles value="{walkforward_cycles}"/>
  <ConfidenceLevel value="{confidence_level}"/>
  <MinTrades value="{min_trades}"/>
  <MonteCarloPercentile value="{mc_percentile}"/>
  <Databanks>"""
        for db in databanks:
            xml += f'\n    <Databank name="{db}" enabled="true"/>'
        xml += "\n  </Databanks>\n</RetesterData>"
        task.retester_data = RetesterDataConfig(raw_xml=xml)
        return task


# ── XML serialisation helpers ────────────────────────────────────────


def _xml_to_bytes(element: ElementTree.Element) -> bytes:
    """Serialise an ElementTree element to UTF-8 bytes WITHOUT an XML declaration."""
    raw = ElementTree.tostring(element, encoding="unicode")
    return raw.encode("utf-8")


# ── Config archive writer (single-task) ──────────────────────────────


def _write_config_archive(
    zf: zipfile.ZipFile,
    config: CfxConfig,
    task_files: dict[str, BuildTask] | None = None,
) -> None:
    """Write config.xml + task file for a single-task CFX archive.

    Args:
        zf: Open ZipFile to write into.
        config: The CfxConfig with a single BuildTask.
        task_files: Optional task file name overrides. When provided, uses
            the first (filename, task) pair instead of the hardcoded
            Build-Task1.xml + config.task.
    """
    if task_files and len(task_files) == 1:
        task_filename, task = next(iter(task_files.items()))
    else:
        task_filename = "Build-Task1.xml"
        task = config.task

    task_root = ElementTree.Element(
        "Task",
        attrib={
            "type": "Build",
            "name": task_filename.replace(".xml", ""),
            "active": "true",
            "version": config.schema_version,
            "taskXMLFile": task_filename,
        },
    )
    zf.writestr("config.xml", _xml_to_bytes(task_root))
    zf.writestr(task_filename, _serialise_task(task))


# ── Project archive writer (multi-file) ──────────────────────────────


def _write_project_archive(zf: zipfile.ZipFile, project: CfxProject) -> None:
    """Write config.xml + task XML files for a multi-file project.

    Emits the verified golden layout (assets/SQX_144_2953_linux_20260601/
    user/projects/*/project.cfx): ``<Project name= version=>`` root, ordered
    ``<Tasks>`` with one ``<Task type= name= showSettingsOverview= sampleName=
    active= taskXMLFile=>`` per task, and a ``<Databanks>`` registry section
    (REQ-23). Per-task type/name/active come from ``project.task_meta``;
    missing entries fall back to the legacy behaviour (type Build, name from
    the file name, active true) so pre-existing callers keep their output.
    """
    lines: list[str] = [
        f"<Project name={quoteattr(project.name)} version={quoteattr(project.schema_version)}>",
        "  <Tasks>",
    ]
    for filename in project.tasks:
        meta = project.task_meta.get(filename)
        task_type = meta.task_type if meta else "Build"
        task_name = meta.name if meta and meta.name else filename.replace(".xml", "")
        active = "true" if meta is None or meta.active else "false"
        overview = (
            str(meta.show_settings_overview).lower()
            if meta
            else "false"
        )
        sample = meta.sample_name if meta else "Custom"
        lines.append(
            "    <Task"
            f" type={quoteattr(task_type)}"
            f" name={quoteattr(task_name)}"
            f" showSettingsOverview={quoteattr(overview)}"
            f" sampleName={quoteattr(sample)}"
            f" active={quoteattr(active)}"
            f" taskXMLFile={quoteattr(filename)}"
            " />"
        )
    lines.append("  </Tasks>")

    if project.databanks:
        lines.append("  <Databanks>")
        for db in project.databanks:
            position = f" position={quoteattr(str(db.position))}" if db.position is not None else ""
            lines.append(
                "    <Databank"
                f" name={quoteattr(db.name)}"
                f" view={quoteattr(db.view)}"
                f" syncType={quoteattr(db.sync_type)}"
                f"{position}"
                " />"
            )
        lines.append("  </Databanks>")

    if project.metadata:
        lines.append("  <Metadata>")
        for key, value in project.metadata.items():
            lines.append(
                f"    <Entry key={quoteattr(str(key))} value={quoteattr(str(value))} />"
            )
        lines.append("  </Metadata>")

    lines.append("</Project>")
    zf.writestr("config.xml", "\n".join(lines).encode("utf-8"))

    # Write each task XML.
    for filename, task in project.tasks.items():
        zf.writestr(filename, _serialise_task(task))


# ── BuildTask XML serialisation ──────────────────────────────────────


def _serialise_task(task: BuildTask) -> bytes:
    """Serialise a BuildTask to <Settings> XML bytes.

    Produces elements for each populated section in the BuildTask,
    writing complex sections (Blocks, ATMs, etc.) as raw XML passthrough
    and simple sections as reconstructed element trees.
    """
    root = ElementTree.Element("Settings")

    # Simple sections (SettingsSection) — in the order they appear
    # in the CFX schema.
    _append_settings_section(root, "Options", task.options)
    _append_settings_section(root, "RiskMoneyManagement", task.risk_money_mgmt)
    _append_settings_section(root, "WhatToBuild", task.what_to_build)
    _append_settings_section(root, "Data", task.data)
    _append_settings_section(root, "Rankings", task.rankings)
    _append_settings_section(root, "PartsToImprove", task.parts_to_improve)
    _append_settings_section(root, "CrossChecks", task.cross_checks)
    _append_settings_section(root, "Notes", task.notes)

    # Complex sections — raw XML passthrough.
    _append_complex_section(root, "Blocks", task.blocks)
    _append_complex_section(root, "ATMs", task.atms)
    _append_complex_section(root, "DataBanks", task.databanks)
    _append_complex_section(root, "Resources", task.resources)
    _append_complex_section(root, "AutomaticPortfolioBuilder", task.automatic_portfolio_builder)
    _append_complex_section(root, "Optimization", task.optimization)
    _append_complex_section(root, "OptimizationParameters", task.optimization_parameters)
    _append_complex_section(root, "WalkForward", task.walk_forward)
    _append_complex_section(root, "Databanks", task.databanks_section)
    _append_complex_section(root, "PortfolioSettings", task.portfolio_settings)
    _append_complex_section(root, "Rankings", task.rankings_section)
    _append_complex_section(root, "CrossChecks", task.cross_checks_section)
    _append_complex_section(root, "RetesterData", task.retester_data)

    # Unknown sections — raw XML passthrough.
    for u in task.unknown_sections:
        try:
            el = ElementTree.fromstring(u.raw_xml)
            root.append(el)
        except ElementTree.ParseError:
            pass  # skip unparseable raw sections

    raw = ElementTree.tostring(root, encoding="unicode")
    return raw.encode("utf-8")


def _append_settings_section(
    parent: ElementTree.Element,
    tag: str,
    section: SettingsSection | None,
) -> None:
    """Append a simple key-value section element if the section is set."""
    if section is None:
        return
    el = ElementTree.SubElement(parent, tag)
    for key, value in section.settings.items():
        ElementTree.SubElement(el, "Setting", attrib={"key": key, "value": value})


def _append_complex_section(
    parent: ElementTree.Element,
    tag: str,
    config: (
        BlockConfig
        | AtmConfig
        | DataBankConfig
        | ResourceConfig
        | AutomaticPortfolioBuilderConfig
        | OptimizationConfig
        | OptimizationParametersConfig
        | WalkForwardConfig
        | DatabanksConfig
        | RankingsConfig
        | CrossChecksConfig
        | RetesterDataConfig
        | None
    ),
) -> None:
    """Append a complex section via raw XML passthrough."""
    if config is None or not config.raw_xml:
        return
    try:
        el = ElementTree.fromstring(config.raw_xml)
        parent.append(el)
    except ElementTree.ParseError:
        pass
