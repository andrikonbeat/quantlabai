"""Tests for CfxWriter — UTF-8 no-decl, ZIP structure, round-trip, dry-run."""

import zipfile
from io import BytesIO
from pathlib import Path

from quantlab.cfx.models import (
    BuildTask,
    CfxArchive,
    CfxConfig,
    CfxProject,
)
from quantlab.cfx.reader import CfxReader
from quantlab.cfx.writer import CfxWriter

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _get_xml_text(zip_bytes: bytes, entry: str = "config.xml") -> str:
    """Extract and decode an XML entry from in-memory ZIP bytes."""
    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
        return zf.read(entry).decode("utf-8")


class TestDryRun:
    def test_dry_run_returns_json(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="141.2219")
        archive = CfxArchive(config=config)

        result = CfxWriter.dry_run(archive)

        assert isinstance(result, str)
        assert "schema_version" in result
        assert "141.2219" in result


class TestUtf8NoDeclaration:
    def test_output_has_no_xml_declaration(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="141.2219")
        archive = CfxArchive(config=config)

        raw = CfxWriter.to_bytes(archive)
        xml_text = _get_xml_text(raw)

        assert "<?xml" not in xml_text[:50]

    def test_output_is_valid_utf8(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="141.2219")
        archive = CfxArchive(config=config)

        raw = CfxWriter.to_bytes(archive)
        xml_text = _get_xml_text(raw)
        assert len(xml_text) > 0


class TestZipStructure:
    def test_config_writer_produces_zip_with_config_xml(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="141.2219")
        archive = CfxArchive(config=config)

        raw = CfxWriter.to_bytes(archive)

        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names

    def test_project_writer_produces_zip_with_task_xmls(self):
        task1 = BuildTask()
        project = CfxProject(
            name="Test Project",
            tasks={"Build-Task1.xml": task1},
            schema_version="141.2219",
        )
        archive = CfxArchive(config=project)

        raw = CfxWriter.to_bytes(archive)

        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names
            assert "Build-Task1.xml" in names

    def test_uses_deflate_compression(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="141.2219")
        archive = CfxArchive(config=config)

        raw = CfxWriter.to_bytes(archive)

        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            info = zf.getinfo("config.xml")
            assert info.compress_type == zipfile.ZIP_DEFLATED


class TestRoundTrip:
    def test_read_write_config_preserves_version(self, tmp_path: Path):
        original = CfxReader.read(FIXTURES / "NQ_CFD_H1.cfx")

        out = tmp_path / "roundtrip.cfx"
        CfxWriter.write(original, out)

        re_read = CfxReader.read(out)
        assert re_read.config.schema_version == original.config.schema_version

    def test_write_project_then_read_preserves_version(self, tmp_path: Path):
        original = CfxReader.read(FIXTURES / "Builder.cfx")
        assert original.config.task_type == "project"

        out = tmp_path / "project_rt.cfx"
        CfxWriter.write(original, out)

        re_read = CfxReader.read(out)
        assert re_read.config.schema_version == original.config.schema_version
