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

# Realistic AutomaticRetest block as emitted by the adaptive retest builder:
# every element below carries inner content that the typed models do NOT model
# (<Methods>, <Param1>/<Param2>, <OptimizeExitTypes>, matrix settings). These
# must survive a from_xml() -> to_xml() round-trip verbatim.
_AUTOMATIC_RETEST_FULL_XML = """<CrossChecks use="false">
  <RetestWithHigherPrecision use="false">
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
  <MonteCarloManipulation use="false">
    <Settings>
      <Methods>
        <Method use="true" type="RandomizeSpread"><Params /></Method>
      </Methods>
      <NumberOfSimulations>100</NumberOfSimulations>
    </Settings>
    <AcceptanceSettings><Conditions /></AcceptanceSettings>
  </MonteCarloManipulation>
  <RetestOnAdditionalMarkets use="false">
    <Settings><Setups /></Settings>
    <AcceptanceSettings><Conditions /></AcceptanceSettings>
  </RetestOnAdditionalMarkets>
  <WalkForwardOptimization use="false">
    <Settings>
      <WalkForward type="1" period="20" optimization="15">
        <Param1 value="18" /><Param2 value="10" />
      </WalkForward>
      <OptimizePeriods>true</OptimizePeriods>
      <OptimizeExitTypes>true</OptimizeExitTypes>
    </Settings>
    <AcceptanceSettings>
      <Conditions CrossCheck="WalkForwardOptimization" thresholdPct="50" />
    </AcceptanceSettings>
  </WalkForwardOptimization>
  <WalkForwardMatrix use="false">
    <Settings><Matrix><Rows>2</Rows><Columns>3</Columns></Matrix></Settings>
    <AcceptanceSettings><Conditions /></AcceptanceSettings>
  </WalkForwardMatrix>
</CrossChecks>"""

_BAD_XML = "this is not xml at all <<<"

# Maps an AutomaticRetest XML tag to the typed sub-model field that owns it.
# Used to assert no element is serialized from two paths at once.
_FIELD_FOR_TAG = {
    "RetestWithHigherPrecision": "retest_with_higher_precision",
    "MonteCarloRetest": "monte_carlo_retest",
    "MonteCarloManipulation": "monte_carlo_manipulation",
    "RetestOnAdditionalMarkets": "retest_on_additional_markets",
    "WalkForwardOptimization": "walk_forward_optimization",
    "WalkForwardMatrix": "walk_forward_matrix",
}


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


_WHATIF_XML = """<CrossChecks use="true">
  <WhatIf use="false">
    <Settings>
      <Methods>
        <Method use="true" type="ByDays">
          <Params>
            <Param key="Monday" type="Boolean">true</Param>
            <Param key="Tuesday" type="Boolean">false</Param>
          </Params>
        </Method>
        <Method use="true" type="ExcludeTradesWithBiggestPl">
          <Params>
            <Param key="Trades" type="Integer">2</Param>
          </Params>
        </Method>
      </Methods>
    </Settings>
    <AcceptanceSettings><Conditions /></AcceptanceSettings>
  </WhatIf>
</CrossChecks>"""


_MULTI_TAB_XML = """<CrossChecks use="true" evaluateAll="true">
  <MonteCarloRetest use="true">
    <Settings>
      <Methods>
        <Method use="true" type="RandomizeHistoryData">
          <Params><Param key="ProbabilityUp" type="Integer">30</Param></Params>
        </Method>
        <Method use="true" type="RandomizeSpread">
          <Params><Param key="Min" type="Double">1.0</Param><Param key="Max" type="Double">5.0</Param></Params>
        </Method>
      </Methods>
      <NumberOfSimulations>10</NumberOfSimulations>
    </Settings>
    <AcceptanceSettings><Conditions /></AcceptanceSettings>
  </MonteCarloRetest>
  <WhatIf use="false">
    <Settings>
      <Methods>
        <Method use="true" type="ByDays">
          <Params>
            <Param key="Monday" type="Boolean">true</Param>
            <Param key="Tuesday" type="Boolean">false</Param>
          </Params>
        </Method>
        <Method use="true" type="ExcludeTradesWithBiggestPl">
          <Params><Param key="Trades" type="Integer">2</Param></Params>
        </Method>
      </Methods>
    </Settings>
    <AcceptanceSettings><Conditions /></AcceptanceSettings>
  </WhatIf>
</CrossChecks>"""


# ── Serialization fix tests ──────────────────────────────────────────

class TestCrossChecksSerializationFix:
    """Generic MonteCarlo round-trip uses runs, not simulations."""

    def test_generic_monte_carlo_uses_runs_attribute(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_GENERIC_XML)
        xml = config.to_xml()

        assert 'runs="200"' in xml
        assert "simulations" not in xml


# ── WhatIf round-trip tests ──────────────────────────────────────────

class TestWhatIfRoundTrip:
    """WhatIf check type parses and serializes typed method params."""

    def test_whatif_method_params_roundtrip(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_WHATIF_XML)
        assert config.dialect == "automatic_retest"
        assert config.automatic_retest is not None
        assert config.automatic_retest.what_if is not None
        assert config.automatic_retest.what_if.use is False
        assert len(config.automatic_retest.what_if.methods) == 2

        xml = config.to_xml()
        reparsed = CrossChecksConfig.from_xml(xml)
        assert reparsed.automatic_retest is not None
        assert reparsed.automatic_retest.what_if is not None
        assert reparsed.automatic_retest.what_if.use is False
        assert len(reparsed.automatic_retest.what_if.methods) == 2


# ── MonteCarloRetest method tests ────────────────────────────────────

class TestMonteCarloMethods:
    """MonteCarloRetest methods list parses typed params from CFX evidence."""

    def test_mc_method_params_parsed(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_XML)
        assert config.automatic_retest is not None
        assert config.automatic_retest.monte_carlo_retest is not None
        assert config.automatic_retest.monte_carlo_retest.methods is not None
        assert len(config.automatic_retest.monte_carlo_retest.methods) == 1
        method = config.automatic_retest.monte_carlo_retest.methods[0]
        assert method.use is True
        assert method.type == "RandomizeHistoryData"
        assert method.params["Probability"] == 20

    def test_mc_methods_survive_full_roundtrip(self):
        """REQ task 4.3: from_xml() → to_xml() → from_xml() keeps method params."""
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_MULTI_TAB_XML)
        reparsed = CrossChecksConfig.from_xml(config.to_xml())

        first = reparsed.automatic_retest
        second = config.automatic_retest
        assert first is not None and second is not None
        # WhatIf methods survive with their param values and types.
        assert first.what_if is not None
        assert [m.type for m in first.what_if.methods] == [
            m.type for m in second.what_if.methods
        ]
        assert first.what_if.methods[0].params["Monday"] is True
        assert first.what_if.methods[0].params["Tuesday"] is False
        assert first.what_if.methods[1].params["Trades"] == 2
        # MonteCarloRetest methods survive too (6 real methods in SQX evidence).
        assert first.monte_carlo_retest is not None
        assert first.monte_carlo_retest.methods is not None
        assert [m.type for m in first.monte_carlo_retest.methods] == [
            m.type for m in second.monte_carlo_retest.methods
        ]
        spread = next(
            m
            for m in first.monte_carlo_retest.methods
            if m.type == "RandomizeSpread"
        )
        assert spread.params["Max"] == 5.0
        assert first.monte_carlo_retest.number_of_simulations == 10


# ── Summary contract tests ──────────────────────────────────────────

class TestSummaryContract:
    """summary() returns both JSON dict and human-readable text."""

    def test_summary_returns_json_and_text(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_XML)
        summary = config.summary()

        assert "json" in summary
        assert "text" in summary
        assert isinstance(summary["json"], dict)
        assert isinstance(summary["text"], str)
        assert summary["json"]["dialect"] == "automatic_retest"
        assert "enabled_tabs" in summary["json"]
        assert "typed_values" in summary["json"]


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

    def test_generic_children_preserved_verbatim(self):
        """Generic children must not be rewritten by the serializer.

        to_xml() previously re-synthesized recognized children, which converted
        <ConfidenceLevel>0.95</ConfidenceLevel> (child form) into
        <ConfidenceLevel value="0.95"/> (attribute form) and normalized
        self-closing spacing. Both are lossy rewrites of the source dialect.
        """
        from quantlab.cfx.models import CrossChecksConfig

        source = (
            "<CrossChecks>"
            '<MonteCarlo enabled="true" runs="200" percentile="99" />'
            '<WalkForward enabled="false" cycles="10" />'
            "<ConfidenceLevel>0.95</ConfidenceLevel>"
            "</CrossChecks>"
        )

        xml = CrossChecksConfig.from_xml(source).to_xml()

        assert '<MonteCarlo enabled="true" runs="200" percentile="99" />' in xml
        assert "<ConfidenceLevel>0.95</ConfidenceLevel>" in xml
        assert 'value="0.95"' not in xml

    def test_generic_verbatim_still_parses_typed(self):
        from quantlab.cfx.models import CrossChecksConfig

        source = (
            "<CrossChecks>"
            '<MonteCarlo enabled="true" runs="200" percentile="99" />'
            '<WalkForward enabled="false" cycles="10" />'
            "<ConfidenceLevel>0.99</ConfidenceLevel>"
            "</CrossChecks>"
        )

        reparsed = CrossChecksConfig.from_xml(CrossChecksConfig.from_xml(source).to_xml())

        assert reparsed.generic.mc_runs == 200
        assert reparsed.generic.wf_cycles == 10
        assert reparsed.generic.confidence_level == 0.99

    def test_parser_accepts_simulations_attribute_spelling(self):
        """renderers.py historically emitted simulations=; keep reading it."""
        from quantlab.cfx.models import CrossChecksConfig

        legacy = (
            '<CrossChecks><MonteCarlo enabled="true" simulations="500" '
            'percentile="99"/></CrossChecks>'
        )

        config = CrossChecksConfig.from_xml(legacy)

        assert config.generic.mc_runs == 500
        assert config.generic.mc_percentile == 99

    def test_roundtrip_preserves_monte_carlo_runs(self):
        """to_xml() must emit the attribute name the parser reads back.

        Regression: to_xml() wrote simulations= while _parse_generic read runs=,
        so a serialized config silently reverted mc_runs to the default.
        """
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_GENERIC_XML)
        xml = config.to_xml()

        assert 'runs="200"' in xml
        assert "simulations=" not in xml
        assert CrossChecksConfig.from_xml(xml).generic.mc_runs == 200

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


class TestCrossChecksRawXmlFidelity:
    """Unmodeled AutomaticRetest content must survive a typed round-trip.

    The typed models intentionally do not model <Methods>, <Param1>/<Param2>
    or <OptimizeExitTypes> yet. Those elements must be carried through
    verbatim via each sub-model's raw_xml field so to_xml() cannot silently
    drop or corrupt them.
    """

    def test_methods_content_survives_roundtrip(self):
        from quantlab.cfx.models import CrossChecksConfig

        xml = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_FULL_XML).to_xml()

        assert "RandomizeHistoryData" in xml
        assert 'key="Probability"' in xml
        assert "RandomizeSpread" in xml

    def test_walkforward_params_and_exit_types_survive(self):
        from quantlab.cfx.models import CrossChecksConfig

        xml = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_FULL_XML).to_xml()

        assert 'value="18"' in xml
        assert 'value="10"' in xml
        assert "OptimizeExitTypes" in xml

    def test_matrix_content_survives(self):
        from quantlab.cfx.models import CrossChecksConfig

        xml = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_FULL_XML).to_xml()

        assert "<Rows>2</Rows>" in xml
        assert "<Columns>3</Columns>" in xml

    def test_typed_access_still_available(self):
        """raw_xml passthrough must not cost typed field access."""
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_FULL_XML)
        ar = config.automatic_retest

        assert config.dialect == "automatic_retest"
        assert ar.use is False
        assert ar.retest_with_higher_precision.precision == 4
        assert ar.retest_with_higher_precision.spread == 2
        assert ar.monte_carlo_retest.number_of_simulations == 100
        assert ar.monte_carlo_manipulation is not None
        assert ar.retest_on_additional_markets is not None
        assert ar.walk_forward_optimization.walk_forward_type == "1"
        assert ar.walk_forward_optimization.period == "20"
        assert ar.walk_forward_optimization.optimize_periods is True
        assert ar.walk_forward_matrix is not None

    def test_no_duplicate_elements(self):
        """Typed children must not also leak into the top-level raw_xml.

        auto_tags routing decides this: any recognized child kept in both its
        typed sub-model and raw_xml would serialize twice.
        """
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_FULL_XML)
        ar = config.automatic_retest

        for tag in (
            "RetestWithHigherPrecision",
            "MonteCarloRetest",
            "MonteCarloManipulation",
            "RetestOnAdditionalMarkets",
            "WalkForwardOptimization",
            "WalkForwardMatrix",
        ):
            # 1 when only the typed path emitted it.
            typed = getattr(ar, _FIELD_FOR_TAG[tag]) is not None
            in_raw = f"<{tag}" in config.raw_xml
            assert not (typed and in_raw), f"{tag} serialized from both paths"
            assert not in_raw, f"{tag} leaked into raw_xml"

    def test_parsed_walk_forward_matrix_exposes_raw_xml(self):
        """WalkForwardMatrix is raw_xml-backed, so raw_xml must be populated."""
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_FULL_XML)
        ar = config.automatic_retest

        assert ar.walk_forward_matrix.raw_xml.strip().startswith("<WalkForwardMatrix")


class TestCrossChecksConfigSummaryFlat:
    """summary() keeps the pre-``json``/``text`` flat contract.

    These assertions read ``dialect``/``generic``/``automatic_retest`` off the
    top level of ``summary()``. They are the complement of
    ``TestCrossChecksConfigSummary``, which reads the nested ``json``/``text``
    envelope off the same superset mapping; the flat view is split into its
    own class so neither set of assertions shadows the other.
    """

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


class TestCrossChecksConfigSummary:
    """summary() returns readable parameter overview."""

    def test_generic_summary(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_GENERIC_XML)
        summary = config.summary()

        assert "json" in summary
        assert "text" in summary
        assert summary["json"]["dialect"] == "generic"
        assert "generic" in summary["json"]
        assert summary["json"]["generic"]["mc_enabled"] is True
        assert summary["json"]["generic"]["mc_runs"] == 200

    def test_automatic_retest_summary(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig.from_xml(_AUTOMATIC_RETEST_XML)
        summary = config.summary()

        assert "json" in summary
        assert "text" in summary
        assert summary["json"]["dialect"] == "automatic_retest"
        assert "automatic_retest" in summary["json"]
        assert summary["json"]["automatic_retest"]["use"] is True

    def test_empty_config_summary(self):
        from quantlab.cfx.models import CrossChecksConfig

        config = CrossChecksConfig()
        summary = config.summary()

        assert "json" in summary
        assert "text" in summary
        assert summary["json"]["dialect"] in (None, "")
        assert summary["json"].get("generic") is None or summary["json"].get("generic") == {}
        assert summary["json"].get("automatic_retest") is None or summary["json"].get("automatic_retest") == {}
