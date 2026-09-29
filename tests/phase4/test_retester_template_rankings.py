"""Advanced ranking filter and data range part placeholders on the Retester
template (task 3.5 of ``data-range-parts-and-ranking-filters``).

``CfxTemplateBuilder._build_retester_task`` hard-coded a two-line Rankings block
and a databank-only Data section, so a retest could not be narrowed by nested
SQX ranking filters or by an explicit IS/OOS split. These tests pin the two new
optional placeholders and — just as important — that leaving them unset
reproduces the previous XML byte for byte.
"""

import io
import zipfile
from xml.etree import ElementTree

from quantlab.cfx.models import AdvancedRankingCondition, ColumnValue, DataRangeParts
from quantlab.phase4.templates import CfxTemplateBuilder


def _condition(column: str = "NetProfit") -> AdvancedRankingCondition:
    return AdvancedRankingCondition(
        column_values=[ColumnValue(column=column, format="Decimal2PL", class_=column)]
    )


def _task(**kwargs) -> "object":
    return CfxTemplateBuilder._build_retester_task(
        strategy_id="test_retest", databanks=["EURUSD_H1"], **kwargs
    )


def _task_xml(**kwargs) -> ElementTree.Element:
    """The task XML as the writer would serialise it."""
    from quantlab.cfx.writer import _serialise_task

    return ElementTree.fromstring(_serialise_task(_task(**kwargs)))


def _archive_root(**kwargs) -> ElementTree.Element:
    """The task XML read back out of a real CFX archive."""
    cfx_bytes = CfxTemplateBuilder.build_retester_cfx(
        strategy_id="test_retest", databanks=["EURUSD_H1"], **kwargs
    )
    with zipfile.ZipFile(io.BytesIO(cfx_bytes)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("Retester-Task1.xml"))
        return ElementTree.fromstring(zf.read(name))


class TestAdvancedRankingPlaceholder:
    def test_no_filters_keeps_the_previous_rankings_block(self) -> None:
        """Regression guard: the existing callers pass neither new argument, so
        their output must not change by a single byte.
        """
        assert _task().rankings_section.raw_xml == (
            '<Rankings>\n  <MinTrades value="30"/>\n'
            '  <ConfidenceLevel value="0.95"/>\n</Rankings>'
        )

    def test_no_filters_emits_no_conditions_block(self) -> None:
        assert "Conditions" not in _task().rankings_section.raw_xml

    def test_filters_extend_the_rankings_block(self) -> None:
        section = _task(advanced_ranking_filters=[_condition()]).rankings_section

        assert 'column="NetProfit"' in section.raw_xml
        assert "<Conditions>" in section.raw_xml

    def test_conditions_follow_min_trades_and_confidence_level(self) -> None:
        """SQX writes <MinTrades>/<ConfidenceLevel> ahead of <Conditions>;
        appending the filters after the closing tag would break the dialect.
        """
        root = _task_xml(advanced_ranking_filters=[_condition()])

        (rankings,) = [c for c in root if c.tag == "Rankings"]
        assert [c.tag for c in rankings] == ["MinTrades", "ConfidenceLevel", "Conditions"]

    def test_multiple_filters_produce_multiple_conditions(self) -> None:
        root = _task_xml(advanced_ranking_filters=[_condition("NetProfit"), _condition("Sharpe")])

        conditions = root.findall("./Rankings/Conditions/Condition")
        assert [c.find("Column-Value").get("column") for c in conditions] == [
            "NetProfit",
            "Sharpe",
        ]

    def test_a_single_rankings_element_is_emitted(self) -> None:
        root = _task_xml(advanced_ranking_filters=[_condition()])

        assert len([c for c in root if c.tag == "Rankings"]) == 1


class TestDataRangePartsPlaceholder:
    def test_no_parts_leaves_data_range_parts_unset(self) -> None:
        assert _task().data_range_parts is None

    def test_parts_are_attached_to_the_task(self) -> None:
        task = _task(data_range_parts=DataRangeParts(ist="0.1", oos_every="0.2"))

        assert task.data_range_parts is not None
        assert task.data_range_parts.ist == "0.1"

    def test_typed_parts_reach_the_data_section(self) -> None:
        root = _task_xml(data_range_parts=DataRangeParts(ist="0.1", oos_every="0.2"))

        (data,) = [c for c in root if c.tag == "Data"]
        assert [c.tag for c in data] == ["Setting", "IST", "OOSEvery"]
        assert data.find("IST").get("value") == "0.1"

    def test_a_single_data_element_is_emitted(self) -> None:
        root = _task_xml(data_range_parts=DataRangeParts(ist="0.1"))

        assert len([c for c in root if c.tag == "Data"]) == 1


class TestBuildRetesterCfxThreadsBothPlaceholders:
    def test_archive_contains_the_filters_and_the_parts(self) -> None:
        root = _archive_root(
            advanced_ranking_filters=[_condition("Sharpe")],
            data_range_parts=DataRangeParts(ist="0.15", validation_ratio=0.3),
        )

        assert 'column="Sharpe"' in ElementTree.tostring(root, encoding="unicode")
        assert root.find("./Rankings/Conditions/Condition/Column-Value") is not None
        assert root.find("./Data/IST").get("value") == "0.15"
        assert root.find("./Data/ValidationRatio").get("value") == "0.3"

    def test_archive_without_placeholders_is_unchanged(self) -> None:
        root = _archive_root()

        assert root.find("./Rankings/Conditions") is None
        assert root.find("./Data/IST") is None
