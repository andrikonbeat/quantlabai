"""CFX archive reader — opens .cfx ZIP archives and returns typed CfxArchive.

Supports both single-task config archives (<Task> root) and multi-file
projects (<Project> root). Validates ZIP paths against directory traversal
attacks and enforces a supported schema version range.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from quantlab.cfx.errors import (
    CfxCorruptError,
    CfxNotFoundError,
    CfxParseError,
    VersionError,
)
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
    RawXmlSection,
    RankingsConfig,
    ResourceConfig,
    RetesterDataConfig,
    SettingsSection,
    WalkForwardConfig,
)

# Minimum schema version accepted — based on SQX 144.2953 real-world files.
_MIN_VERSION = "130.0"
_MAX_VERSION = "146.0"

# Elements that should be parsed as simple key-value settings sections.
_SETTINGS_SECTIONS = frozenset({
    "Options",
    "RiskMoneyManagement",
    "WhatToBuild",
    "Data",
    "PartsToImprove",
    "Notes",
})

# Elements that are parsed as typed complex sections.
_COMPLEX_SECTIONS = frozenset({
    "Blocks",
    "ATMs",
    "DataBanks",
    "Resources",
    # Phase 4 complex sections
    "AutomaticPortfolioBuilder",
    "PortfolioSettings",
    "Optimization",
    "OptimizationParameters",
    "WalkForward",
    "Databanks",
    "Rankings",
    "CrossChecks",
    "RetesterData",
})


class CfxReader:
    """Reads .cfx archives and returns typed CfxArchive models."""

    @staticmethod
    def read(path: str | Path) -> CfxArchive:
        """Open a .cfx ZIP archive and parse it into a CfxArchive model.

        Args:
            path: Filesystem path to the .cfx file.

        Returns:
            A CfxArchive populated with the parsed contents.

        Raises:
            CfxNotFoundError: The file does not exist.
            CfxCorruptError: The file is not a valid ZIP or contains
                invalid XML.
            CfxParseError: The XML structure does not match the CFX
                schema.
            VersionError: The schema version is not supported.
        """
        path = Path(path)

        if not path.exists():
            raise CfxNotFoundError(f"CFX file not found: {path}")

        try:
            zf = zipfile.ZipFile(path, "r")
        except zipfile.BadZipFile as exc:
            raise CfxCorruptError(f"Not a valid CFX archive: {path}") from exc

        # ── ZIP traversal defense ────────────────────────────────
        _validate_zip_paths(zf)

        # ── Determine type & parse ───────────────────────────────
        names = zf.namelist()
        task_files = [n for n in names if n.endswith(".xml")]

        if not task_files:
            raise CfxParseError("CFX archive contains no XML files")

        # Read config.xml (single-task archives have it inline; projects
        # always have it).
        raw_config = _read_entry(zf, "config.xml", task_files)

        root = _parse_xml(raw_config, filename="config.xml")
        _validate_schema_version(root)

        if root.tag == "Task":
            return CfxReader._parse_config(zf, root, path)
        elif root.tag == "Project":
            return CfxReader._parse_project(zf, root, task_files, path)
        else:
            raise CfxParseError(
                f"Unexpected root element <{root.tag}> in config.xml"
            )

    # ── Phase 4: Portfolio / Optimizer / Retester CFX Readers ─────────

    @staticmethod
    def read_portfolio_cfx(path: str | Path) -> CfxArchive:
        """Read a Portfolio Master CFX archive.

        Args:
            path: Path to .cfx file.

        Returns:
            CfxArchive with Portfolio Master task.
        """
        return CfxReader.read(path)

    @staticmethod
    def read_optimizer_cfx(path: str | Path) -> CfxArchive:
        """Read an Optimizer CFX archive.

        Args:
            path: Path to .cfx file.

        Returns:
            CfxArchive with Optimizer task.
        """
        return CfxReader.read(path)

    @staticmethod
    def read_retester_cfx(path: str | Path) -> CfxArchive:
        """Read a Retester CFX archive.

        Args:
            path: Path to .cfx file.

        Returns:
            CfxArchive with Retester task.
        """
        return CfxReader.read(path)

    # ── Single-file Config ───────────────────────────────────────

    @staticmethod
    def _parse_config(
        zf: zipfile.ZipFile,
        root: ElementTree.Element,
        path: Path,
    ) -> CfxArchive:
        version = root.get("version", "0")
        task_xml_file = root.get("taskXMLFile", "")

        # Settings may be inline inside the <Task> element or in a
        # separate XML file referenced by taskXMLFile.
        settings_el = root.find("Settings")
        if settings_el is not None:
            task = _parse_settings_element_tree(settings_el)
        elif task_xml_file:
            task = _parse_settings_xml(zf, task_xml_file)
        else:
            task = BuildTask()

        config = CfxConfig(task=task, schema_version=version)
        return CfxArchive(config=config, task_files={task_xml_file: task} if task_xml_file else {})

    # ── Multi-file Project ───────────────────────────────────────

    @staticmethod
    def _parse_project(
        zf: zipfile.ZipFile,
        root: ElementTree.Element,
        task_files: list[str],
        path: Path,
    ) -> CfxArchive:
        version = root.get("version", "0")
        name = root.get("name", "")

        tasks_el = root.find("Tasks")
        task_mapping: dict[str, BuildTask] = {}

        if tasks_el is not None:
            for task_el in tasks_el.findall("Task"):
                xml_file = task_el.get("taskXMLFile", "")
                if xml_file and xml_file in task_files:
                    task = _parse_settings_xml(zf, xml_file)
                    task_mapping[xml_file] = task

        project = CfxProject(name=name, tasks=task_mapping, schema_version=version)
        return CfxArchive(config=project, task_files=task_mapping)


# ── Helpers ──────────────────────────────────────────────────────────


def _validate_zip_paths(zf: zipfile.ZipFile) -> None:
    """Reject ZIP entries containing path traversal or absolute paths."""
    for name in zf.namelist():
        # Normalise to POSIX separators for consistent checking.
        normalised = name.replace("\\", "/")
        if normalised.startswith("/") or normalised.startswith(".."):
            raise CfxCorruptError(
                f"Path traversal detected in archive entry: {name!r}"
            )
        # Deeply nested ".." also rejected.
        parts = normalised.split("/")
        for part in parts:
            if part == "..":
                raise CfxCorruptError(
                    f"Path traversal detected in archive entry: {name!r}"
                )


def _read_entry(
    zf: zipfile.ZipFile, name: str, available: list[str]
) -> str:
    """Read an XML entry, raising CfxCorruptError on failure."""
    if name not in available:
        raise CfxParseError(f"Required entry {name!r} not found in archive")
    try:
        return zf.read(name).decode("utf-8")
    except (KeyError, UnicodeDecodeError) as exc:
        raise CfxCorruptError(f"Failed to read {name!r}: {exc}") from exc


def _parse_xml(raw: str, *, filename: str = "") -> ElementTree.Element:
    """Parse raw XML, raising CfxCorruptError on parse failure."""
    try:
        return ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        ctx = f" in {filename}" if filename else ""
        raise CfxCorruptError(f"Invalid XML{ctx}: {exc}") from exc


def _validate_schema_version(root: ElementTree.Element) -> None:
    """Raise VersionError if the schema version is outside the supported range."""
    version = root.get("version")
    if version is None and root.tag == "Task":
        version = root.get("version", "0")
    if version is None:
        raise CfxParseError("Missing version attribute on root element")

    # Simple tuple-based comparison on dotted version strings.
    try:
        parts = [int(x) for x in version.split(".")]
        min_parts = [int(x) for x in _MIN_VERSION.split(".")]
        max_parts = [int(x) for x in _MAX_VERSION.split(".")]
    except ValueError as exc:
        raise CfxParseError(f"Invalid version format: {version!r}") from exc

    min_ver = tuple(parts[:2])
    min_allowed = tuple(min_parts[:2])
    max_allowed = tuple(max_parts[:2])

    if min_ver < min_allowed or min_ver > max_allowed:
        raise VersionError(
            f"Unsupported CFX schema version {version} "
            f"(supported: {_MIN_VERSION} – {_MAX_VERSION})"
        )


def _parse_settings_xml(
    zf: zipfile.ZipFile, filename: str
) -> BuildTask:
    """Parse a task-XML file (e.g. Build-Task1.xml) into a BuildTask model."""
    names = zf.namelist()
    raw = _read_entry(zf, filename, names)
    root = _parse_xml(raw, filename=filename)

    if root.tag != "Settings":
        raise CfxParseError(
            f"Expected <Settings> root in {filename!r}, got <{root.tag}>"
        )

    return _parse_settings_element_tree(root)


def _parse_settings_element_tree(root: ElementTree.Element) -> BuildTask:
    """Parse a <Settings> ElementTree element into a BuildTask model."""
    sections: dict[str, SettingsSection | None] = {}
    complex_sections: dict[
        str,
        BlockConfig
        | AtmConfig
        | DataBankConfig
        | ResourceConfig
        | AutomaticPortfolioBuilderConfig
        | PortfolioSettingsConfig
        | OptimizationConfig
        | OptimizationParametersConfig
        | WalkForwardConfig
        | DatabanksConfig
        | RankingsConfig
        | CrossChecksConfig
        | RetesterDataConfig
        | None,
    ] = {}
    unknown: list[RawXmlSection] = []

    for child in root:
        tag = child.tag
        if tag in _SETTINGS_SECTIONS:
            settings = _parse_settings_element(child)
            sections[tag] = settings
        elif tag in _COMPLEX_SECTIONS:
            raw_xml = ElementTree.tostring(child, encoding="unicode")
            complex_sections[tag] = _make_complex_section(tag, raw_xml)
        else:
            raw_xml = ElementTree.tostring(child, encoding="unicode")
            unknown.append(RawXmlSection(name=tag, raw_xml=raw_xml))

    return BuildTask(
        options=sections.get("Options"),
        what_to_build=sections.get("WhatToBuild"),
        risk_money_mgmt=sections.get("RiskMoneyManagement"),
        data=sections.get("Data"),
        rankings=sections.get("Rankings"),
        parts_to_improve=sections.get("PartsToImprove"),
        cross_checks=sections.get("CrossChecks"),
        notes=sections.get("Notes"),
        blocks=complex_sections.get("Blocks"),
        atms=complex_sections.get("ATMs"),
        databanks=complex_sections.get("DataBanks"),
        resources=complex_sections.get("Resources"),
        automatic_portfolio_builder=complex_sections.get("AutomaticPortfolioBuilder"),
        portfolio_settings=complex_sections.get("PortfolioSettings"),
        optimization=complex_sections.get("Optimization"),
        optimization_parameters=complex_sections.get("OptimizationParameters"),
        walk_forward=complex_sections.get("WalkForward"),
        databanks_section=complex_sections.get("Databanks"),
        rankings_section=complex_sections.get("Rankings"),
        cross_checks_section=complex_sections.get("CrossChecks"),
        retester_data=complex_sections.get("RetesterData"),
        unknown_sections=unknown,
    )


def _parse_settings_element(el: ElementTree.Element) -> SettingsSection:
    """Convert an ElementTree element to a flat key-value SettingsSection."""
    settings: dict[str, str] = {}
    _flatten_element(el, settings, prefix="")
    return SettingsSection(name=el.tag, settings=settings)


def _flatten_element(
    el: ElementTree.Element,
    acc: dict[str, str],
    prefix: str,
) -> None:
    """Recursively flatten an XML element tree into key-value pairs."""
    tag = el.tag
    full_key = f"{prefix}.{tag}" if prefix else tag

    # Include attributes.
    for attr_key, attr_val in el.attrib.items():
        acc[f"{full_key}@{attr_key}"] = attr_val

    # Include text content for leaf elements.
    text = (el.text or "").strip()
    if text and len(el) == 0:
        acc[full_key] = text

    # Recurse into children.
    for child in el:
        _flatten_element(child, acc, full_key)


def _make_complex_section(
    tag: str, raw_xml: str
) -> (
    BlockConfig
    | AtmConfig
    | DataBankConfig
    | ResourceConfig
    | AutomaticPortfolioBuilderConfig
    | PortfolioSettingsConfig
    | OptimizationConfig
    | OptimizationParametersConfig
    | WalkForwardConfig
    | DatabanksConfig
    | RankingsConfig
    | CrossChecksConfig
    | RetesterDataConfig
):
    """Create the appropriate typed config model for a complex section."""
    mapping = {
        "Blocks": BlockConfig,
        "ATMs": AtmConfig,
        "DataBanks": DataBankConfig,
        "Resources": ResourceConfig,
        "AutomaticPortfolioBuilder": AutomaticPortfolioBuilderConfig,
        "PortfolioSettings": PortfolioSettingsConfig,
        "Optimization": OptimizationConfig,
        "OptimizationParameters": OptimizationParametersConfig,
        "WalkForward": WalkForwardConfig,
        "Databanks": DatabanksConfig,
        "Rankings": RankingsConfig,
        "CrossChecks": CrossChecksConfig,
        "RetesterData": RetesterDataConfig,
    }
    cls = mapping.get(tag)
    if cls is None:
        raise CfxParseError(f"Unknown complex section: {tag}")
    return cls(raw_xml=raw_xml)
