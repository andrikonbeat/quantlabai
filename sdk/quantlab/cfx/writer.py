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

from quantlab.cfx.models import (
    AtmConfig,
    BlockConfig,
    BuildTask,
    CfxArchive,
    CfxConfig,
    CfxProject,
    DataBankConfig,
    ResourceConfig,
    SettingsSection,
)


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
                _write_config_archive(zf, config)
            elif isinstance(config, CfxProject):
                _write_project_archive(zf, config)
            else:
                raise TypeError(f"Unknown config type: {type(config).__name__}")

        return buf


# ── XML serialisation helpers ────────────────────────────────────────


def _xml_to_bytes(element: ElementTree.Element) -> bytes:
    """Serialise an ElementTree element to UTF-8 bytes WITHOUT an XML declaration."""
    raw = ElementTree.tostring(element, encoding="unicode")
    return raw.encode("utf-8")


# ── Config archive writer (single-task) ──────────────────────────────


def _write_config_archive(zf: zipfile.ZipFile, config: CfxConfig) -> None:
    """Write config.xml + task file for a single-task CFX archive."""
    task_root = ElementTree.Element(
        "Task",
        attrib={
            "type": "Build",
            "name": "Build strategies",
            "active": "true",
            "version": config.schema_version,
            "taskXMLFile": "Build-Task1.xml",
        },
    )
    zf.writestr("config.xml", _xml_to_bytes(task_root))
    zf.writestr("Build-Task1.xml", _serialise_task(config.task))


# ── Project archive writer (multi-file) ──────────────────────────────


def _write_project_archive(zf: zipfile.ZipFile, project: CfxProject) -> None:
    """Write config.xml + task XML files for a multi-file project."""
    tasks_el = ElementTree.Element("Tasks")

    for filename in project.tasks:
        ElementTree.SubElement(
            tasks_el,
            "Task",
            attrib={
                "type": "Build",
                "name": filename.replace(".xml", ""),
                "active": "true",
                "version": project.schema_version,
                "taskXMLFile": filename,
            },
        )

    project_root = ElementTree.Element(
        "Project",
        attrib={
            "name": project.name,
            "version": project.schema_version,
        },
    )
    project_root.append(tasks_el)
    zf.writestr("config.xml", _xml_to_bytes(project_root))

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
    config: BlockConfig | AtmConfig | DataBankConfig | ResourceConfig | None,
) -> None:
    """Append a complex section via raw XML passthrough."""
    if config is None or not config.raw_xml:
        return
    try:
        el = ElementTree.fromstring(config.raw_xml)
        parent.append(el)
    except ElementTree.ParseError:
        pass
