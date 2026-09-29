"""Tests for advanced ranking filter rendering in the custom-project renderers.

Covers the renderer half of task 3.5 of
``data-range-parts-and-ranking-filters``: a Retest task must be able to carry
nested SQX ``<Rankings><Conditions>`` filters, and the renderer's output must
stay byte-identical to the patcher's so the two paths cannot drift.
"""

from xml.etree import ElementTree

from quantlab.cfx.models import (
    AdvancedRankingCondition,
    ColumnValue,
    SetAdvancedRankingsInstruction,
)
from quantlab.cfx.patcher import CfxPatcher, build_advanced_rankings_xml
from quantlab.cfx.models import BuildTask, CfxArchive, CfxConfig
from quantlab.customproject.models import CustomProjectTask
from quantlab.customproject.renderers import render_advanced_rankings, render_retest


def _condition(column: str = "NetProfit") -> AdvancedRankingCondition:
    return AdvancedRankingCondition(
        column_values=[ColumnValue(column=column, format="Decimal2PL", class_=column)]
    )


def _parse(raw_xml: str) -> ElementTree.Element:
    return ElementTree.fromstring(raw_xml)


class TestRenderAdvancedRankings:
    def test_conditions_are_nested_under_a_single_rankings_element(self) -> None:
        section = render_advanced_rankings([_condition(), _condition("Sharpe")])

        root = _parse(section.raw_xml)
        assert root.tag == "Rankings"
        assert [c.tag for c in root] == ["Conditions"]
        conditions = root.findall("./Conditions/Condition")
        assert len(conditions) == 2
        assert [c.find("Column-Value").get("column") for c in conditions] == [
            "NetProfit",
            "Sharpe",
        ]

    def test_extra_elements_precede_the_conditions_block(self) -> None:
        """SQX writes <MinTrades>/<ConfidenceLevel> before <Conditions>; a caller
        that supplies them must not have them appended after the filters.
        """
        section = render_advanced_rankings(
            [_condition()],
            extra_elements='  <MinTrades value="30"/>\n  <ConfidenceLevel value="0.95"/>',
        )

        assert [c.tag for c in _parse(section.raw_xml)] == [
            "MinTrades",
            "ConfidenceLevel",
            "Conditions",
        ]

    def test_empty_condition_list_still_yields_a_conditions_block(self) -> None:
        section = render_advanced_rankings([])

        root = _parse(section.raw_xml)
        assert [c.tag for c in root] == ["Conditions"]
        assert len(root.find("Conditions")) == 0

    def test_output_is_byte_identical_to_the_patcher_renderer(self) -> None:
        """Anti-duplication guard: the retester XML is verified SQX evidence in
        test_patcher.py. A second implementation that drifted would ship a
        ranking block SQX rejects while every other test still passed.
        """
        conditions = [_condition(), _condition("Sharpe")]

        assert render_advanced_rankings(conditions).raw_xml == build_advanced_rankings_xml(
            conditions
        )


class TestRenderRetestWithAdvancedRankings:
    def _task(self, **kwargs) -> CustomProjectTask:
        base = {
            "type": "Retest",
            "name": "Retest-1",
            "source_databank": "EURUSD_H1",
        }
        base.update(kwargs)
        return CustomProjectTask(**base)

    def test_filters_produce_a_rankings_section(self) -> None:
        bt = render_retest(self._task(advanced_ranking_filters=[_condition()]))

        assert bt.rankings_section is not None
        assert "<Conditions>" in bt.rankings_section.raw_xml
        assert 'column="NetProfit"' in bt.rankings_section.raw_xml

    def test_task_without_filters_is_unchanged(self) -> None:
        """A Retest task that never mentions filters must not gain a Rankings
        section it did not have before.
        """
        bt = render_retest(self._task())

        assert bt.rankings_section is None

    def test_task_with_empty_filter_list_is_unchanged(self) -> None:
        bt = render_retest(self._task(advanced_ranking_filters=[]))

        assert bt.rankings_section is None

    def test_patcher_and_renderer_agree_end_to_end(self) -> None:
        """The two entry points into the same feature must produce the same XML,
        verified through a real CfxArchive round trip.
        """
        conditions = [_condition("NetProfit"), _condition("Sharpe")]

        rendered = render_retest(self._task(advanced_ranking_filters=conditions))

        patched_task = BuildTask()
        archive = CfxArchive(
            config=CfxConfig(task=patched_task, schema_version="141.2219"),
            task_files={"Build-Task1.xml": patched_task},
        )
        CfxPatcher(archive).apply([SetAdvancedRankingsInstruction(conditions=conditions)])

        assert rendered.rankings_section.raw_xml == patched_task.rankings_section.raw_xml
