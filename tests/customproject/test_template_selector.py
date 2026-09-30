"""Slice B: TemplateSelector — deterministic template choice per PortfolioState.

Spec requirement "Adaptive CustomProject Templates":

- Template selection MUST be a static rule table keyed by ``PortfolioState``
  and MUST be deterministic — the same state always yields byte-identical
  output, so a campaign can be reproduced from its guardian state.

Strict TDD: written first — RED until Slice B lands.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from quantlab.customproject.templates import (
    STATE_TEMPLATE_MAP,
    CampaignTemplate,
    DeepRobustnessTemplate,
    QuickValidationTemplate,
    StandardResearchTemplate,
    TemplateSelector,
)
from quantlab.guardian.models import PortfolioState


def _canonical(project) -> str:
    """Byte-stable serialisation of a CustomProject dataclass tree."""
    return json.dumps(asdict(project), sort_keys=True)


class TestRuleTable:
    """The static rule table is total and explicit."""

    def test_every_portfolio_state_has_a_rule(self) -> None:
        assert set(STATE_TEMPLATE_MAP) == set(PortfolioState)

    def test_every_rule_targets_a_campaign_template(self) -> None:
        for state, template in STATE_TEMPLATE_MAP.items():
            assert isinstance(state, PortfolioState)
            assert issubclass(template, CampaignTemplate)

    def test_escalation_is_monotonic_in_portfolio_stress(self) -> None:
        """A healthier portfolio never needs more verification than a sick one."""
        assert (
            STATE_TEMPLATE_MAP[PortfolioState.NORMAL]
            is StandardResearchTemplate
        )
        assert (
            STATE_TEMPLATE_MAP[PortfolioState.VIGILANCE]
            is QuickValidationTemplate
        )
        for stressed in (
            PortfolioState.RECOVERY,
            PortfolioState.DEFENSIVE,
            PortfolioState.QUARANTINE,
        ):
            assert STATE_TEMPLATE_MAP[stressed] is DeepRobustnessTemplate


class TestSelect:
    """``select`` is a pure lookup with no hidden state."""

    @pytest.mark.parametrize("state", list(PortfolioState))
    def test_select_returns_mapped_template(self, state: PortfolioState) -> None:
        assert TemplateSelector.select(state) is STATE_TEMPLATE_MAP[state]

    def test_select_is_repeatable(self) -> None:
        """GIVEN the same state
        WHEN selected repeatedly
        THEN the same template class is returned.
        """
        selected = [TemplateSelector.select(PortfolioState.DEFENSIVE) for _ in range(5)]

        assert len(set(selected)) == 1

    def test_select_rejects_unknown_state(self) -> None:
        """Fail closed: an unrecognised state never silently defaults."""
        with pytest.raises(ValueError):
            TemplateSelector.select("NORMAL")  # type: ignore[arg-type]

    def test_select_rejects_none(self) -> None:
        with pytest.raises(ValueError):
            TemplateSelector.select(None)  # type: ignore[arg-type]

    def test_template_name_matches_selection(self) -> None:
        for state, template in STATE_TEMPLATE_MAP.items():
            assert TemplateSelector.template_name(state) == template.build().template_name


class TestDeterminism:
    """Same state in, byte-identical project out."""

    @pytest.mark.parametrize("state", list(PortfolioState))
    def test_build_is_byte_identical_across_calls(self, state: PortfolioState) -> None:
        """GIVEN a PortfolioState
        WHEN the template is built twice
        THEN both projects serialise to the same bytes.
        """
        template = TemplateSelector.select(state)

        first = _canonical(TemplateSelector.select_project(state))
        second = _canonical(TemplateSelector.select_project(state))
        repeated = _canonical(template.build())

        assert first == second
        assert first == repeated

    def test_distinct_states_can_still_collide(self) -> None:
        """DEFENSIVE and QUARANTINE share a rule — same state, same bytes."""
        defensive = _canonical(TemplateSelector.select_project(PortfolioState.DEFENSIVE))
        quarantine = _canonical(TemplateSelector.select_project(PortfolioState.QUARANTINE))

        assert defensive == quarantine

    def test_healthier_states_differ_from_stressed_ones(self) -> None:
        normal = _canonical(TemplateSelector.select_project(PortfolioState.NORMAL))
        defensive = _canonical(TemplateSelector.select_project(PortfolioState.DEFENSIVE))

        assert normal != defensive

    def test_selection_is_stateless_across_instances(self) -> None:
        """Two selector instances agree — the table is module state, not instance state."""
        first = TemplateSelector()
        second = TemplateSelector()

        assert first.select(PortfolioState.QUARANTINE) is second.select(
            PortfolioState.QUARANTINE
        )
