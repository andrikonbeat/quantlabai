"""Tests for the translator's advanced ranking / data range parts mapping.

Covers task 3.4 of ``data-range-parts-and-ranking-filters``: the DSL fields
added in d19e693 must reach the CFX archive, and the advanced ranking spec's
simple-compatibility requirement must hold — a campaign using both
``criteria`` and ``advanced_ranking_filters`` has to produce one ``<Rankings>``
element carrying both lanes.
"""

from xml.etree import ElementTree

import pytest

from quantlab.cfx.writer import _serialise_task
from quantlab.dsl.models import (
    AcceptanceCriterion,
    AdvancedRankingFilter,
    ColumnValueFilter,
    DataRangePartsDSL,
    Market,
    ResearchConfig,
    Timeframe,
)
from quantlab.tools.exceptions import TranslationError
from quantlab.translate.translator import generate_cfx_archive


def _config(**overrides) -> ResearchConfig:
    base: dict = {
        "campaign": "advanced",
        "market": Market.EURUSD,
        "timeframe": Timeframe.H1,
        "strategies": [{"name": "s1"}],
    }
    base.update(overrides)
    return ResearchConfig(**base)


def _filter(column: str = "NetProfit", **overrides) -> AdvancedRankingFilter:
    payload = {
        "column_values": [
            ColumnValueFilter(column=column, format="Decimal2PL", class_name=column)
        ]
    }
    payload.update(overrides)
    return AdvancedRankingFilter(**payload)


def _root(config: ResearchConfig) -> ElementTree.Element:
    archive = generate_cfx_archive(config)
    return ElementTree.fromstring(_serialise_task(archive.config.task))


def _rankings(root: ElementTree.Element) -> list[ElementTree.Element]:
    return [c for c in root if c.tag == "Rankings"]


class TestAdvancedRankingMapping:
    def test_filter_reaches_the_task_as_a_typed_conditions_block(self) -> None:
        """GIVEN a campaign with one advanced filter
        WHEN translated
        THEN the task carries a Rankings section with a nested <Conditions> block.
        """
        archive = generate_cfx_archive(_config(advanced_ranking_filters=[_filter()]))

        section = archive.config.task.rankings_section
        assert section is not None
        assert "<Conditions>" in section.raw_xml
        assert 'column="NetProfit"' in section.raw_xml

    def test_every_filter_attribute_reaches_the_xml(self) -> None:
        """Non-default attribute values must survive the DSL → model → XML path;
        a silent default would produce a filter that does not mean what the
        campaign asked for.
        """
        archive = generate_cfx_archive(
            _config(
                advanced_ranking_filters=[
                    _filter(
                        result_type="main",
                        sample_type="127",
                        pct_ratio="10",
                        confidence_level="95",
                        class_name="Advanced",
                        name="Main",
                    )
                ]
            )
        )

        xml = archive.config.task.rankings_section.raw_xml

        assert 'pctRatio="10"' in xml
        assert 'confidenceLevel="95"' in xml
        assert 'class="Advanced"' in xml
        assert 'name="Main"' in xml

    def test_multiple_filters_produce_multiple_conditions(self) -> None:
        archive = generate_cfx_archive(
            _config(advanced_ranking_filters=[_filter("NetProfit"), _filter("Sharpe")])
        )

        xml = archive.config.task.rankings_section.raw_xml

        assert xml.count("<Condition ") == 2
        assert xml.count("<Conditions>") == 1

    def test_nested_column_filter_attributes_reach_the_xml(self) -> None:
        """The nested ColumnValue needs its own coverage: its attributes are
        mapped by a different function than the condition's, and a silently
        defaulted column filter would change what the campaign actually ranks on.
        """
        archive = generate_cfx_archive(
            _config(
                advanced_ranking_filters=[
                    _filter(
                        column_values=[
                            ColumnValueFilter(
                                column="Sharpe",
                                column_type="1",
                                format="Decimal4",
                                result_type="custom",
                                direction="7",
                                sample_type="12",
                                pl_type="11",
                                confidence_level="90",
                                market="2",
                                subresult="31",
                                pct_ratio="5",
                                class_name="Ratio",
                                name="Sharpe ratio",
                            )
                        ]
                    )
                ]
            )
        )

        xml = archive.config.task.rankings_section.raw_xml

        assert 'column="Sharpe"' in xml
        assert 'columnType="1"' in xml
        assert 'format="Decimal4"' in xml
        assert 'resultType="custom"' in xml
        assert 'direction="7"' in xml
        assert 'sampleType="12"' in xml
        assert 'plType="11"' in xml
        assert 'confidenceLevel="90"' in xml
        assert 'market="2"' in xml
        assert 'subresult="31"' in xml
        assert 'pctRatio="5"' in xml
        assert 'class="Ratio"' in xml
        assert 'name="Sharpe ratio"' in xml

    def test_filter_without_column_values_is_rejected(self) -> None:
        """A <Condition> with no <Column-Value> child is meaningless in SQX; fail
        loudly at translation time instead of emitting an empty condition.
        """
        with pytest.raises(TranslationError, match="column"):
            generate_cfx_archive(
                _config(advanced_ranking_filters=[AdvancedRankingFilter()])
            )


class TestSimpleRankingCompatibility:
    def test_simple_and_advanced_lanes_land_in_one_rankings_element(self) -> None:
        """The spec's simple-compatibility requirement: a campaign using both
        forms must produce a single <Rankings> holding both the flat criteria
        and the nested conditions.
        """
        root = _root(
            _config(
                criteria=[AcceptanceCriterion(metric="sharpe", operator=">", value=1.0)],
                advanced_ranking_filters=[_filter()],
            )
        )

        (rankings,) = _rankings(root)
        assert "Conditions" in [c.tag for c in rankings]
        assert "Setting" in [c.tag for c in rankings]

    def test_simple_only_campaign_is_unchanged(self) -> None:
        """A campaign with no advanced filters must not grow a <Conditions> block."""
        root = _root(_config(criteria=[AcceptanceCriterion(metric="sharpe", operator=">", value=1.0)]))

        (rankings,) = _rankings(root)
        assert [c.tag for c in rankings] == ["Setting", "Setting", "Setting"]
        assert rankings_section_xml(root) is None


def rankings_section_xml(root: ElementTree.Element) -> str | None:
    """The advanced conditions block, or None when the campaign has none."""
    (rankings,) = _rankings(root)
    found = [c for c in rankings if c.tag == "Conditions"]
    return ElementTree.tostring(found[0], encoding="unicode") if found else None


class TestDataRangePartsMapping:
    def test_typed_parts_reach_the_data_section(self) -> None:
        root = _root(
            _config(
                data_range_parts=DataRangePartsDSL(
                    ist="2020.01.01-2021.12.31",
                    oos_1="2022.01.01-2022.12.31",
                    validation_ratio=0.2,
                    test_ratio=0.1,
                )
            )
        )

        (data,) = [c for c in root if c.tag == "Data"]
        assert [c.get("value") for c in data if c.tag == "IST"] == ["2020.01.01-2021.12.31"]
        assert [c.get("value") for c in data if c.tag == "OOS1"] == ["2022.01.01-2022.12.31"]
        assert [c.get("value") for c in data if c.tag == "ValidationRatio"] == ["0.2"]
        assert [c.get("value") for c in data if c.tag == "TestRatio"] == ["0.1"]

    def test_raw_xml_bridge_survives_translation(self) -> None:
        """An unrecognised SQX sub-range parked in raw_xml must reach the output
        inside <Data>, not be dropped and not leak as a direct <Settings> child.
        """
        root = _root(
            _config(data_range_parts=DataRangePartsDSL(raw_xml='<ProprietaryRange value="x" />'))
        )

        (data,) = [c for c in root if c.tag == "Data"]
        assert [c.tag for c in data] == [
            "Setting",
            "Setting",
            "Setting",
            "ProprietaryRange",
        ]
        assert data.find("ProprietaryRange").get("value") == "x"

    def test_absent_parts_leave_the_data_section_untouched(self) -> None:
        """The base task's <Data> already carries Symbol/Timeframe settings; the
        new code path must add no typed sub-range element to it.
        """
        root = _root(_config())

        (data,) = [c for c in root if c.tag == "Data"]
        assert [c.tag for c in data] == ["Setting", "Setting", "Setting"]
        assert [s.get("key") for s in data] == [
            "Symbol@symbol",
            "Symbol@name",
            "Timeframe1@value",
        ]


class TestEndToEndXml:
    def test_generated_cfx_xml_contains_the_advanced_lanes(self) -> None:
        """generate_cfx_xml is the legacy string entry point and must reflect the
        same mapping, not just generate_cfx_archive.
        """
        from quantlab.translate.translator import generate_cfx_xml

        xml = generate_cfx_xml(
            _config(
                advanced_ranking_filters=[_filter()],
                data_range_parts=DataRangePartsDSL(ist="2020.01.01-2021.12.31"),
            )
        )

        assert xml.count("<Rankings>") == 1
        assert "<Conditions>" in xml
        assert "<IST" in xml
