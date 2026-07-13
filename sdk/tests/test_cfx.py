"""Tests for the CFX archive writer — XML-to-ZIP packaging."""

import zipfile
from pathlib import Path

import pytest

from quantlab.dsl.models import ResearchConfig
from quantlab.translate.cfx import CfxArchive, CfxResult


class TestCfxArchive:
    """Tests for ``CfxArchive.from_model()``."""

    def test_valid_output_file_created(self, tmp_path: Path) -> None:
        """GIVEN translated XML content
        WHEN the system packages it as .cfx
        THEN a valid ZIP file with .cfx extension is created containing
        one XML entry.
        """
        config = ResearchConfig(
            campaign="ZipTest",
            market="EURUSD",
            timeframe="H1",
        )

        result = CfxArchive.from_model(config, output_dir=str(tmp_path / "output"))

        assert isinstance(result, CfxResult)
        assert result.xml_content is not None
        assert result.path is not None
        assert result.path.suffix == ".cfx"
        assert result.path.exists()

        # Verify it's a valid ZIP containing one XML file
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()
            assert len(names) == 1
            assert names[0].endswith(".cfx")
            # Read back the XML
            xml_in_zip = zf.read(names[0]).decode("utf-8")
            assert "StrategyQuantX" in xml_in_zip

    def test_dry_run_returns_xml_without_zip(self, tmp_path: Path) -> None:
        """GIVEN a translated research model in dry-run mode
        WHEN the system is invoked with dry_run flag
        THEN the generated XML string is returned and the artifact is
        written as a raw XML file (not zipped).
        """
        config = ResearchConfig(
            campaign="DryRunTest",
            market="EURUSD",
            timeframe="H1",
        )

        result = CfxArchive.from_model(config, dry_run=True)

        assert isinstance(result, CfxResult)
        assert result.xml_content is not None
        assert "StrategyQuantX" in result.xml_content
        assert result.path is not None
        assert result.path.name.endswith(".cfx.xml")
        # In dry-run, it's a raw XML file, NOT a ZIP
        content = result.path.read_text(encoding="utf-8")
        assert "StrategyQuantX" in content

    def test_dry_run_no_file_written_to_output_dir(self, tmp_path: Path) -> None:
        """In dry-run mode, files go to _output/, not output/."""
        config = ResearchConfig(
            campaign="DryDirCheck",
            market="EURUSD",
            timeframe="H1",
        )
        output_dir = tmp_path / "output"

        result = CfxArchive.from_model(
            config, dry_run=True, output_dir=str(output_dir)
        )

        # The file should NOT be in output/
        assert not (output_dir / "DryDirCheck.cfx.xml").exists()
        # It should be in _output/
        dry_dir = tmp_path / "_output"
        assert result.path is not None
        assert dry_dir in result.path.parents

    def test_multiple_archives_unique_files(self, tmp_path: Path) -> None:
        """Multiple calls produce separate files."""
        config_a = ResearchConfig(campaign="CampaignA", market="EURUSD", timeframe="H1")
        config_b = ResearchConfig(campaign="CampaignB", market="BTCUSD", timeframe="D1")

        result_a = CfxArchive.from_model(config_a, output_dir=str(tmp_path / "output"))
        result_b = CfxArchive.from_model(config_b, output_dir=str(tmp_path / "output"))

        assert result_a.path is not None
        assert result_b.path is not None
        assert result_a.path.name != result_b.path.name
        assert result_a.path.exists()
        assert result_b.path.exists()

    def test_campaign_name_with_spaces_safe_filename(self, tmp_path: Path) -> None:
        """Campaign names with spaces are sanitised for filenames."""
        config = ResearchConfig(
            campaign="My Campaign: Test #1",
            market="EURUSD",
            timeframe="H1",
        )

        result = CfxArchive.from_model(config, output_dir=str(tmp_path / "output"))

        assert result.path is not None
        assert " " not in result.path.name

    def test_xml_content_round_trip(self, tmp_path: Path) -> None:
        """The XML content in the result matches what's in the archive."""
        config = ResearchConfig(
            campaign="RoundTripCheck",
            market="GBPUSD",
            timeframe="M15",
        )

        result = CfxArchive.from_model(config, output_dir=str(tmp_path / "output"))

        # Read the XML from the ZIP and compare
        with zipfile.ZipFile(result.path, "r") as zf:
            stored = zf.read(zf.namelist()[0]).decode("utf-8")

        assert stored == result.xml_content
