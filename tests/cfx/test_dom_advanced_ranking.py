"""Tests for the advanced-ranking / data-range-parts helpers in ``cfx.dom``.

Covers task 3.1 of ``data-range-parts-and-ranking-filters``: the domain layer
must expose chainable wrappers over the new ``CfxPatcher`` instructions so the
DSL wiring in the translator has a stable public entry point.
"""

from quantlab.cfx.dom import add_advanced_ranking_condition, set_data_range_parts
from quantlab.cfx.models import (
    AdvancedRankingCondition,
    BuildTask,
    CfxArchive,
    CfxConfig,
    ColumnValue,
    DataRangeParts,
)


def _archive() -> CfxArchive:
    """Wrap a fresh BuildTask in the single-task archive shape."""
    return CfxArchive(
        config=CfxConfig(task=BuildTask(), schema_version="141.2219"),
        task_files={"Build-Task1.xml": BuildTask()},
    )


def _condition(column: str) -> AdvancedRankingCondition:
    return AdvancedRankingCondition(
        column_values=[ColumnValue(column=column, format="Decimal2", class_=column)],
    )


class TestAdvancedRankingDomHelpers:
    def test_add_advanced_ranking_condition_returns_the_same_archive(self) -> None:
        """The dom helper is a chainable mutation wrapper over CfxPatcher."""
        archive = _archive()

        result = add_advanced_ranking_condition(archive, _condition("NetProfit"))

        assert result is archive
        assert archive.config.task.rankings_section is not None
        assert "<Column-Value" in archive.config.task.rankings_section.raw_xml

    def test_add_advanced_ranking_condition_appends_a_second_condition(self) -> None:
        """Two calls yield two <Condition> children under one <Conditions> block."""
        archive = _archive()
        add_advanced_ranking_condition(archive, _condition("NetProfit"))
        add_advanced_ranking_condition(
            archive,
            AdvancedRankingCondition(
                column_values=[ColumnValue(column="Sharpe", format="Decimal2", class_="Sharpe")],
            ),
        )

        raw_xml = archive.config.task.rankings_section.raw_xml
        assert raw_xml.count("<Condition ") == 2
        assert raw_xml.count("<Conditions>") == 1

    def test_set_data_range_parts_stores_the_typed_model(self) -> None:
        """The dom helper stores the typed model, not a pre-rendered blob, so the
        typed fields stay queryable downstream.
        """
        archive = _archive()
        parts = DataRangeParts(ist="2020.01.01-2021.12.31", test_ratio=0.1)

        result = set_data_range_parts(archive, parts)

        assert result is archive
        stored = archive.config.task.data_range_parts
        assert stored is not None
        assert stored.ist == "2020.01.01-2021.12.31"
        assert stored.test_ratio == 0.1
        assert stored.raw_xml == ""
