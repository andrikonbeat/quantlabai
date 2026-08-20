"""Tests for CfxReader CrossChecks dialect detection and CfxWriter round-trip.

Strict TDD — tests verify reader populates typed CrossChecks fields and
writer serializes them back to XML preserving known elements + raw_xml extras.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from quantlab.cfx.models import (
    CrossChecksConfig,
    CrossChecksGeneric,
)
from quantlab.cfx.reader import CfxReader
from quantlab.cfx.writer import CfxWriter

_GENERIC_XML = """<CrossChecks>
  <MonteCarlo enabled="true" runs="200" percentile="99"/>
  <WalkForward enabled="false" cycles="10"/>
  <ConfidenceLevel value="0.99"/>
</CrossChecks>"""

_AUTOMATIC_RETEST_XML = """<CrossChecks use="true">
  <RetestWithHigherPrecision use="true">
    <Settings><Precision>4</Precision><Spread>2</Spread></Settings>
    <AcceptanceSettings><Conditions /></AcceptanceSettings>
  </RetestWithHigherPrecision>
  <MonteCarloRetest use="false">
    <Settings>
      <Methods>
        <Method use="true" type="RandomizeHistoryData">
          <Params><Param key="Probability" type="Integer">20</Param></Params>
        </Method>
      </Methods>
      <NumberOfSimulations>100</NumberOfSimulations>
    </Settings>
    <AcceptanceSettings><Conditions /></AcceptanceSettings>
  </MonteCarloRetest>
  <WalkForwardOptimization use="false">
    <Settings>
      <WalkForward type="1" period="20" optimization="15">
        <Param1 value="18" /><Param2 value="10" />
      </WalkForward>
      <OptimizePeriods>true</OptimizePeriods>
    </Settings>
    <AcceptanceSettings>
      <Conditions CrossCheck="WalkForwardOptimization" thresholdPct="50" />
    </AcceptanceSettings>
  </WalkForwardOptimization>
</CrossChecks>"""

_UNKNOWN_ELEMENT_XML = """<CrossChecks>
  <MonteCarlo enabled="true" runs="100" percentile="95"/>
  <FutureElement someAttr="value">unknown content</FutureElement>
</CrossChecks>"""


def _make_cfx_with_crosschecks(crosschecks_xml: str) -> bytes:
    """Create an in-memory .cfx with CrossChecks in the task XML."""
    task_xml = f"<Settings>{crosschecks_xml}</Settings>"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config.xml", '<Task type="Build" version="141.2219" taskXMLFile="Build-Task1.xml"/>')
        zf.writestr("Build-Task1.xml", task_xml.encode("utf-8"))
    return buf.getvalue()


class TestReaderCrossChecksDialectDetection:
    """Reader detects Generic vs AutomaticRetest and populates typed fields."""

    def test_generic_dialect_populates_typed_fields(self, tmp_path: Path):
        """GIVEN a CFX with Generic CrossChecks XML
        WHEN CfxReader reads it
        THEN cross_checks_section has dialect='generic' and typed fields populated.
        """
        cfx = tmp_path / "generic.cfx"
        cfx.write_bytes(_make_cfx_with_crosschecks(_GENERIC_XML))

        archive = CfxReader.read(cfx)
        task = archive.config.task
        cc = task.cross_checks_section

        assert cc is not None
        assert cc.dialect == "generic"
        assert cc.generic is not None
        assert cc.generic.mc_enabled is True
        assert cc.generic.mc_runs == 200
        assert cc.generic.mc_percentile == 99
        assert cc.generic.wf_enabled is False
        assert cc.generic.wf_cycles == 10
        assert cc.generic.confidence_level == 0.99
        assert cc.automatic_retest is None

    def test_automatic_retest_dialect_populates_typed_fields(self, tmp_path: Path):
        """GIVEN a CFX with AutomaticRetest CrossChecks XML
        WHEN CfxReader reads it
        THEN cross_checks_section has dialect='automatic_retest' and typed fields populated.
        """
        cfx = tmp_path / "auto_retest.cfx"
        cfx.write_bytes(_make_cfx_with_crosschecks(_AUTOMATIC_RETEST_XML))

        archive = CfxReader.read(cfx)
        task = archive.config.task
        cc = task.cross_checks_section

        assert cc is not None
        assert cc.dialect == "automatic_retest"
        assert cc.automatic_retest is not None
        assert cc.automatic_retest.use is True
        assert cc.automatic_retest.retest_with_higher_precision is not None
        assert cc.automatic_retest.retest_with_higher_precision.use is True
        assert cc.automatic_retest.monte_carlo_retest is not None
        assert cc.automatic_retest.monte_carlo_retest.use is False
        assert cc.automatic_retest.walk_forward_optimization is not None
        assert cc.generic is None

    def test_unknown_elements_remain_in_raw_xml(self, tmp_path: Path):
        """GIVEN a CFX with Generic CrossChecks + unknown <FutureElement>
        WHEN CfxReader reads it
        THEN typed fields are populated AND FutureElement survives in raw_xml.
        """
        cfx = tmp_path / "unknown.cfx"
        cfx.write_bytes(_make_cfx_with_crosschecks(_UNKNOWN_ELEMENT_XML))

        archive = CfxReader.read(cfx)
        cc = archive.config.task.cross_checks_section

        assert cc is not None
        assert cc.dialect == "generic"
        assert cc.generic is not None
        assert cc.generic.mc_enabled is True
        assert "FutureElement" in cc.raw_xml
        assert "someAttr" in cc.raw_xml


class TestWriterCrossChecksRoundTrip:
    """Writer serializes typed CrossChecks and round-trip preserves fields."""

    def test_generic_roundtrip_via_cfx_archive(self, tmp_path: Path):
        """GIVEN a CFX with Generic CrossChecks
        WHEN CfxWriter writes and CfxReader re-reads
        THEN typed fields survive round-trip.
        """
        # Read original
        original_cfx = tmp_path / "generic.cfx"
        original_cfx.write_bytes(_make_cfx_with_crosschecks(_GENERIC_XML))
        archive = CfxReader.read(original_cfx)

        # Write back
        output_cfx = tmp_path / "generic_rt.cfx"
        CfxWriter.write(archive, output_cfx)

        # Re-read
        re_read = CfxReader.read(output_cfx)
        cc = re_read.config.task.cross_checks_section

        assert cc is not None
        assert cc.dialect == "generic"
        assert cc.generic is not None
        assert cc.generic.mc_enabled is True
        assert cc.generic.mc_runs == 200
        assert cc.generic.mc_percentile == 99
        assert cc.generic.wf_enabled is False
        assert cc.generic.wf_cycles == 10
        assert cc.generic.confidence_level == 0.99

    def test_automatic_retest_roundtrip_via_cfx_archive(self, tmp_path: Path):
        """GIVEN a CFX with AutomaticRetest CrossChecks
        WHEN CfxWriter writes and CfxReader re-reads
        THEN typed fields survive round-trip.
        """
        original_cfx = tmp_path / "auto.cfx"
        original_cfx.write_bytes(_make_cfx_with_crosschecks(_AUTOMATIC_RETEST_XML))
        archive = CfxReader.read(original_cfx)

        output_cfx = tmp_path / "auto_rt.cfx"
        CfxWriter.write(archive, output_cfx)

        re_read = CfxReader.read(output_cfx)
        cc = re_read.config.task.cross_checks_section

        assert cc is not None
        assert cc.dialect == "automatic_retest"
        assert cc.automatic_retest is not None
        assert cc.automatic_retest.use is True
        assert cc.automatic_retest.retest_with_higher_precision is not None
        assert cc.automatic_retest.retest_with_higher_precision.use is True
        assert cc.automatic_retest.monte_carlo_retest is not None
        assert cc.automatic_retest.monte_carlo_retest.use is False
        assert cc.automatic_retest.walk_forward_optimization is not None


class TestWriterSetCrosschecksTyped:
    """CfxWriter.set_crosschecks builds typed CrossChecksGeneric."""

    def test_set_crosschecks_creates_typed_generic(self, tmp_path: Path):
        """GIVEN a BuildTask
        WHEN CfxWriter.set_crosschecks is called
        THEN cross_checks_section has dialect='generic' and typed CrossChecksGeneric.
        """
        from quantlab.cfx.models import BuildTask, CfxArchive, CfxConfig

        task = BuildTask()
        task = CfxWriter.set_crosschecks(
            task,
            mc_enabled=True,
            wf_enabled=False,
            mc_runs=300,
            mc_percentile=99,
            wf_cycles=15,
            confidence_level=0.99,
        )

        cc = task.cross_checks_section
        assert cc is not None
        assert cc.dialect == "generic"
        assert cc.generic is not None
        assert cc.generic.mc_enabled is True
        assert cc.generic.mc_runs == 300
        assert cc.generic.mc_percentile == 99
        assert cc.generic.wf_enabled is False
        assert cc.generic.wf_cycles == 15
        assert cc.generic.confidence_level == 0.99

    def test_set_crosschecks_roundtrip_produces_valid_cfx(self, tmp_path: Path):
        """GIVEN a BuildTask with set_crosschecks typed model
        WHEN written to CFX and re-read
        THEN typed fields are preserved.
        """
        from quantlab.cfx.models import BuildTask, CfxArchive, CfxConfig

        task = BuildTask()
        task = CfxWriter.set_crosschecks(
            task,
            mc_enabled=True,
            wf_enabled=True,
            mc_runs=500,
        )

        config = CfxConfig(task=task, schema_version="141.2219")
        archive = CfxArchive(config=config)

        output = tmp_path / "set_cc.cfx"
        CfxWriter.write(archive, output)

        re_read = CfxReader.read(output)
        cc = re_read.config.task.cross_checks_section

        assert cc is not None
        assert cc.dialect == "generic"
        assert cc.generic is not None
        assert cc.generic.mc_enabled is True
        assert cc.generic.mc_runs == 500
        assert cc.generic.wf_enabled is True
