"""Tests for the CFX archive factory — file I/O layer (updated for cfx-editor models)."""

import zipfile
from pathlib import Path

import pytest

from quantlab.dsl.models import ResearchConfig, Strategy
from quantlab.translate.cfx import CfxArchive, CfxResult


class TestCfxArchiveFactory:
    """Tests for ``CfxArchiveFactory.from_model()`` — file I/O layer."""

    def _minimal_config(self, campaign: str, market: str, timeframe: str) -> ResearchConfig:
        """Create a minimal valid config with required strategy."""
        return ResearchConfig(
            campaign=campaign,
            market=market,
            timeframe=timeframe,
            strategies=[Strategy(name="DefaultStrat", direction="LONG")],
        )

    def test_valid_output_file_created(self, tmp_path: Path) -> None:
        """Normal mode creates a .cfx ZIP file."""
        config = self._minimal_config("ZipTest", "EURUSD", "H1")

        result = CfxArchive.from_model(config, output_dir=str(tmp_path / "output"))

        assert isinstance(result, CfxResult)
        assert result.xml_content is not None
        assert result.path is not None
        assert result.path.suffix == ".cfx"
        assert result.path.exists()

        # Verify it's a valid ZIP with config.xml + Build-Task1.xml
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names
            assert "Build-Task1.xml" in names

            # config.xml should have Task root
            config_xml = zf.read("config.xml").decode("utf-8")
            assert "Task" in config_xml
            assert "taskXMLFile" in config_xml

    def test_dry_run_returns_json_without_zip(self, tmp_path: Path) -> None:
        """Dry-run mode returns model JSON, writes to _output/."""
        config = self._minimal_config("DryRunTest", "EURUSD", "H1")

        result = CfxArchive.from_model(config, dry_run=True)

        assert isinstance(result, CfxResult)
        assert result.xml_content is not None
        assert result.path is not None
        assert result.path.name.endswith(".cfx.json")
        # In dry-run, it's JSON (model dump), NOT a ZIP
        content = result.path.read_text(encoding="utf-8")
        assert "schema_version" in content
        assert "config" in content

    def test_dry_run_no_file_written_to_output_dir(self, tmp_path: Path) -> None:
        """Dry-run files go to _output/, not the specified output dir."""
        config = self._minimal_config("DryDirCheck", "EURUSD", "H1")
        output_dir = tmp_path / "output"

        result = CfxArchive.from_model(
            config, dry_run=True, output_dir=str(output_dir)
        )

        # File should NOT be in output/
        assert not (output_dir / "DryDirCheck.cfx.json").exists()
        # File SHOULD be in _output/
        dry_dir = tmp_path / "_output"
        assert result.path is not None
        assert dry_dir in result.path.parents

    def test_multiple_archives_unique_files(self, tmp_path: Path) -> None:
        """Multiple calls produce separate files."""
        config_a = self._minimal_config("CampaignA", "EURUSD", "H1")
        config_b = self._minimal_config("CampaignB", "BTCUSD", "D1")

        result_a = CfxArchive.from_model(config_a, output_dir=str(tmp_path / "output"))
        result_b = CfxArchive.from_model(config_b, output_dir=str(tmp_path / "output"))

        assert result_a.path is not None
        assert result_b.path is not None
        assert result_a.path.name != result_b.path.name
        assert result_a.path.exists()
        assert result_b.path.exists()

    def test_campaign_name_with_spaces_safe_filename(self, tmp_path: Path) -> None:
        """Campaign names with spaces/special chars are sanitised."""
        config = self._minimal_config("My Campaign: Test #1", "EURUSD", "H1")

        result = CfxArchive.from_model(config, output_dir=str(tmp_path / "output"))

        assert result.path is not None
        assert " " not in result.path.name
        assert ":" not in result.path.name

    def test_config_xml_content_matches_archive(self, tmp_path: Path) -> None:
        """The xml_content in result matches config.xml in the archive."""
        config = self._minimal_config("RoundTripCheck", "GBPUSD", "M15")

        result = CfxArchive.from_model(config, output_dir=str(tmp_path / "output"))

        with zipfile.ZipFile(result.path, "r") as zf:
            stored = zf.read("config.xml").decode("utf-8")

        assert stored == result.xml_content


class TestCfxArchiveFactoryEdgeCases:
    """Edge cases for the factory."""

    def test_dry_run_creates_output_dir(self, tmp_path: Path) -> None:
        """Dry-run creates _output/ directory if it doesn't exist."""
        config = ResearchConfig(
            campaign="NewDir",
            market="EURUSD",
            timeframe="H1",
            strategies=[Strategy(name="S1", direction="LONG")],
        )
        # Ensure _output doesn't exist
        assert not (tmp_path / "_output").exists()

        result = CfxArchive.from_model(config, dry_run=True, output_dir=str(tmp_path / "custom"))

        assert (tmp_path / "_output").exists()
        assert result.path is not None
        assert result.path.parent == tmp_path / "_output"

    def test_normal_mode_creates_output_dir(self, tmp_path: Path) -> None:
        """Normal mode creates output directory if it doesn't exist."""
        config = ResearchConfig(
            campaign="NewDir",
            market="EURUSD",
            timeframe="H1",
            strategies=[Strategy(name="S1", direction="LONG")],
        )
        out_dir = tmp_path / "new_output"
        assert not out_dir.exists()

        result = CfxArchive.from_model(config, output_dir=str(out_dir))

        assert out_dir.exists()
        assert result.path is not None
        assert result.path.parent == out_dir