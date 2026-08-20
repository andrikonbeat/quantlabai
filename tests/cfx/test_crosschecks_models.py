"""Tests for typed CrossChecks models (Generic + AutomaticRetest dialects).

Strict TDD — RED phase: tests reference classes/methods that do not exist yet
in quantlab.cfx.models. Expected failures: ImportError / AttributeError.
"""

from __future__ import annotations

import pytest


# ── Generic dialect helpers ──────────────────────────────────────────

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

_BAD_XML = "this is not xml at all <<<"


# ── Generic model tests ──────────────────────────────────────────────

class TestCrossChecksGenericDefaults:
    """CrossChecksGeneric model defaults."""

    def test_default_values(self):
        from quantlab.cfx.models import CrossChecksGeneric

        model = CrossChecksGeneric()

        assert model.mc_enabled is False
        assert model.mc_runs == 100
        assert model.mc_percentile == 95
        assert model.wf_enabled is False
        assert model.wf_cycles == 5
        assert model.confidence_level == 0.95


# ── AutomaticRetest model tests ──────────────────────────────────────

class TestCrossChecksAutomaticRetestDefaults:
    """CrossChecksAutomaticRetest model defaults."""

    def test_default_values(self):
        from quantlab.cfx.models import (
            CrossChecksAutomaticRetest,
            MonteCarloRetest,
            RetestWithHigherPrecision,
            WalkForwardOptimization,
        )

        model = CrossChecksAutomaticRetest()

        assert model.use is True
        assert model.retest_with_higher_precision is None
        assert model.monte_carlo_retest is None
        assert model.monte_carlo_manipulation is None
        assert model.retest_on_additional_markets is None
        assert model.walk_forward_optimization is None
        assert model.walk_forward_matrix is None
        assert model.opt_profile_sys_param_permutation is None


# ── CrossChecksConfig dialect container tests ─────────────────────────

class TestCrossChecksConfigFromXml:
    """CrossChecksConfig.from_xml() dialect detection and typed population."""

    def test_generic_dialect_populates_typed_fields(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_GENERIC_XML)

        assert config.dialect == "generic"
        assert config.generic is not None
        assert config.generic.mc_enabled is True
        assert config.generic.mc_runs == 200
        assert config.generic.mc_percentile == 99
        assert config.generic.wf_enabled is False
        assert config.generic.wf_cycles == 10
        assert config.generic.confidence_level == 0.99
        assert config.automatic_retest is None

    def test_automatic_retest_dialect_populates_typed_fields(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_XML)

        assert config.dialect == "automatic_retest"
        assert config.automatic_retest is not None
        assert config.automatic_retest.use is True
        assert config.automatic_retest.retest_with_higher_precision is not None
        assert config.automatic_retest.retest_with_higher_precision.use is True
        assert config.automatic_retest.monte_carlo_retest is not None
        assert config.automatic_retest.monte_carlo_retest.use is False
        assert config.automatic_retest.walk_forward_optimization is not None
        assert config.generic is None


class TestCrossChecksConfigToXml:
    """CrossChecksConfig.to_xml() round-trip serialization."""

    def test_generic_roundtrip(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_GENERIC_XML)
        xml = config.to_xml()

        # Re-parse and verify fields survive round-trip
        reparsed = CrossChecksConfig.from_xml(xml)
        assert reparsed.dialect == "generic"
        assert reparsed.generic is not None
        assert reparsed.generic.mc_enabled is True
        assert reparsed.generic.mc_runs == 200
        assert reparsed.generic.mc_percentile == 99
        assert reparsed.generic.wf_enabled is False
        assert reparsed.generic.wf_cycles == 10
        assert reparsed.generic.confidence_level == 0.99

    def test_automatic_retest_roundtrip(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_XML)
        xml = config.to_xml()

        reparsed = CrossChecksConfig.from_xml(xml)
        assert reparsed.dialect == "automatic_retest"
        assert reparsed.automatic_retest is not None
        assert reparsed.automatic_retest.use is True
        assert reparsed.automatic_retest.retest_with_higher_precision is not None
        assert reparsed.automatic_retest.retest_with_higher_precision.use is True
        assert reparsed.automatic_retest.monte_carlo_retest is not None
        assert reparsed.automatic_retest.walk_forward_optimization is not None


class TestCrossChecksConfigRawXmlFallback:
    """Unknown/unrecognized elements and unparsable XML fallback."""

    def test_unknown_elements_remain_in_raw_xml(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_UNKNOWN_ELEMENT_XML)

        assert config.dialect == "generic"
        assert config.generic is not None
        assert config.generic.mc_enabled is True
        # Unknown <FutureElement> must survive in raw_xml
        assert "FutureElement" in config.raw_xml
        assert "someAttr" in config.raw_xml

    def test_unparsable_xml_falls_back_to_raw_xml(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_BAD_XML)

        assert config.dialect is None
        assert config.generic is None
        assert config.automatic_retest is None
        assert config.raw_xml == _BAD_XML

    def test_backward_compat_raw_xml_only(self):
        from quantlab.cfx.models import CrossChecksConfig

        raw = "<CrossChecks><MonteCarlo enabled='true'/></CrossChecks>"
        config = CrossChecksConfig(raw_xml=raw)

        assert config.raw_xml == raw
        assert config.dialect is None or config.dialect == ""
        assert config.generic is None
        assert config.automatic_retest is None


class TestCrossChecksConfigSummary:
    """summary() returns readable parameter overview."""

    def test_generic_summary(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_GENERIC_XML)
        summary = config.summary()

        assert summary["dialect"] == "generic"
        assert "generic" in summary
        assert summary["generic"]["mc_enabled"] is True
        assert summary["generic"]["mc_runs"] == 200

    def test_automatic_retest_summary(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_XML)
        summary = config.summary()

        assert summary["dialect"] == "automatic_retest"
        assert "automatic_retest" in summary
        assert summary["automatic_retest"]["use"] is True

    def test_empty_config_summary(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig()
        summary = config.summary()

        assert summary["dialect"] in (None, "")
        assert summary.get("generic") is None or summary.get("generic") == {}
        assert summary.get("automatic_retest") is None or summary.get("automatic_retest") == {}
