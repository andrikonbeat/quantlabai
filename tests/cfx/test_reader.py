"""Tests for CfxReader — version gate, type detection, traversal defense."""

import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from quantlab.cfx.errors import (
    CfxCorruptError,
    CfxNotFoundError,
    CfxParseError,
    VersionError,
)
from quantlab.cfx.reader import CfxReader

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# These two samples are git-ignored (``.gitignore`` excludes ``*.cfx``); on a
# fresh clone they only exist when the pinned StrategyQuant install is linked
# into ``tests/cfx/fixtures/``. Install it to run the type-detection nodes.
NQ_CFD_H1 = FIXTURES / "NQ_CFD_H1.cfx"
NQ_MULTI_TIMEFRAME = FIXTURES / "NQ_MULTI_TIMEFRAME.cfx"


# ── Fixture helpers ──────────────────────────────────────────────────


def _make_zip(files: dict[str, str]) -> bytes:
    """Create an in-memory ZIP archive from a dict of filename → XML."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content.encode("utf-8"))
    return buf.getvalue()


def _write_zip(path: Path, files: dict[str, str]) -> None:
    path.write_bytes(_make_zip(files))


# ── Tests ────────────────────────────────────────────────────────────


class TestFileNotFound:
    def test_missing_file_raises_notfound(self):
        with pytest.raises(CfxNotFoundError):
            CfxReader.read("/nonexistent/path.cfx")


class TestTraversalDefense:
    def test_rejects_absolute_path(self, tmp_path: Path):
        cfx = tmp_path / "attack.cfx"
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("/etc/passwd", "pwned")
        cfx.write_bytes(buf.getvalue())

        with pytest.raises(CfxCorruptError, match="traversal"):
            CfxReader.read(cfx)

    def test_rejects_parent_path(self, tmp_path: Path):
        cfx = tmp_path / "attack.cfx"
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("../escape.xml", "<Task/>")
        cfx.write_bytes(buf.getvalue())

        with pytest.raises(CfxCorruptError, match="traversal"):
            CfxReader.read(cfx)

    def test_rejects_nested_parent_path(self, tmp_path: Path):
        cfx = tmp_path / "attack.cfx"
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("foo/../../bar.xml", "<Task/>")
        cfx.write_bytes(buf.getvalue())

        with pytest.raises(CfxCorruptError, match="traversal"):
            CfxReader.read(cfx)


class TestVersionGate:
    def test_too_low_version_raises(self, tmp_path: Path):
        cfx = tmp_path / "old.cfx"
        _write_zip(cfx, {
            "config.xml": '<Task type="Build" version="100.0" taskXMLFile="task.xml"/>',
        })

        with pytest.raises(VersionError, match="Unsupported"):
            CfxReader.read(cfx)

    def test_too_high_version_raises(self, tmp_path: Path):
        cfx = tmp_path / "new.cfx"
        _write_zip(cfx, {
            "config.xml": '<Task type="Build" version="200.0" taskXMLFile="task.xml"/>',
        })

        with pytest.raises(VersionError, match="Unsupported"):
            CfxReader.read(cfx)

    def test_acceptable_version_passes(self, tmp_path: Path):
        cfx = tmp_path / "ok.cfx"
        _write_zip(cfx, {
            "config.xml": '<Task type="Build" version="141.2219" taskXMLFile="task.xml"/>',
            "task.xml": "<Settings/>",
        })

        archive = CfxReader.read(cfx)
        assert archive.config.schema_version == "141.2219"


class TestTypeDetection:
    @pytest.mark.skipif(
        not NQ_CFD_H1.is_file(),
        reason=f"pinned SQX sample absent at {NQ_CFD_H1}; install StrategyQuant "
        "and link its user/settings/Configs samples into tests/cfx/fixtures/",
    )
    def test_single_task_detected_as_config(self):
        archive = CfxReader.read(NQ_CFD_H1)
        assert archive.config.task_type == "config"

    @pytest.mark.skipif(
        not NQ_MULTI_TIMEFRAME.is_file(),
        reason=f"pinned SQX sample absent at {NQ_MULTI_TIMEFRAME}; install "
        "StrategyQuant and link the multi-timeframe project into "
        "tests/cfx/fixtures/",
    )
    def test_multi_file_detected_as_project(self):
        archive = CfxReader.read(NQ_MULTI_TIMEFRAME)
        assert archive.config.task_type == "project"


class TestCorruptAndMissing:
    def test_bad_zip_raises_corrupt(self, tmp_path: Path):
        cfx = tmp_path / "bad.cfx"
        cfx.write_text("not a zip file")

        with pytest.raises(CfxCorruptError, match="CFX archive"):
            CfxReader.read(cfx)

    def test_missing_config_xml_raises_parse_error(self, tmp_path: Path):
        cfx = tmp_path / "empty.cfx"
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("random.xml", "<foo/>")
        cfx.write_bytes(buf.getvalue())

        with pytest.raises(CfxParseError, match="config.xml"):
            CfxReader.read(cfx)

    def test_invalid_xml_raises_corrupt(self, tmp_path: Path):
        cfx = tmp_path / "badxml.cfx"
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("config.xml", "<Task><unclosed>")
        cfx.write_bytes(buf.getvalue())

        with pytest.raises(CfxCorruptError, match="Invalid XML"):
            CfxReader.read(cfx)
