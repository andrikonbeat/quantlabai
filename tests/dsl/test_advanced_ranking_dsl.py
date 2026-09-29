"""Tests for the advanced ranking / data range parts DSL models.

Covers tasks 3.2 (RED) and 3.3 (GREEN) of
``data-range-parts-and-ranking-filters``: the research DSL must be able to
express the nested SQX ``<Rankings><Conditions>`` structure and the typed
``<Data>`` sub-ranges, using the same camelCase attribute vocabulary as a real
SQX CFX export while still accepting idiomatic Python field names.
"""

import pytest

from quantlab.cfx.models import AdvancedRankingCondition, ColumnValue, DataRangeParts
from quantlab.dsl.models import (
    AdvancedRankingFilter,
    ColumnValueFilter,
    DataRangePartsDSL,
    Market,
    ResearchConfig,
    Timeframe,
)


def _normalised(model) -> set[str]:
    """Field names with the DSL ``class_name`` / CFX ``class_`` rename applied."""
    return {"class_name" if n in {"class_", "class"} else n for n in model.model_fields}


def _config(**overrides) -> ResearchConfig:
    base = {"campaign": "c", "market": Market.EURUSD, "timeframe": Timeframe.H1}
    base.update(overrides)
    return ResearchConfig(**base)


class TestColumnValueFilter:
    def test_camel_case_aliases_round_trip(self) -> None:
        """GIVEN a column filter written in the real SQX attribute vocabulary
        WHEN dumped by alias
        THEN every attribute comes back with its SQX name, not its Python name.
        """
        cv = ColumnValueFilter(
            column="NetProfit",
            columnType="0",
            format="Decimal2PL",
            resultType="main",
            plType="10",
            confidenceLevel="50",
            pctRatio="0",
            **{"class": "NetProfit"},
        )

        dumped = cv.model_dump(by_alias=True, exclude_none=True)

        assert dumped["column"] == "NetProfit"
        assert dumped["columnType"] == "0"
        assert dumped["resultType"] == "main"
        assert dumped["plType"] == "10"
        assert dumped["confidenceLevel"] == "50"
        assert dumped["pctRatio"] == "0"
        assert dumped["class"] == "NetProfit"

    def test_snake_case_construction_still_works(self) -> None:
        """populate_by_name keeps the idiomatic Python spelling usable, matching
        the CFX models established in 4be6362.
        """
        cv = ColumnValueFilter(column="Sharpe", format="Decimal2", class_name="Sharpe")

        assert cv.column_type == "0"
        assert cv.class_name == "Sharpe"
        assert cv.model_dump(by_alias=True)["class"] == "Sharpe"

    def test_optional_name_is_omitted_when_unset(self) -> None:
        """`name` is optional in a real SQX export, so it must not be emitted."""
        cv = ColumnValueFilter(column="Sharpe", format="Decimal2", class_name="Sharpe")

        assert cv.name is None
        assert "name" not in cv.model_dump(by_alias=True, exclude_none=True)

    def test_column_and_format_are_required(self) -> None:
        """SQX cannot resolve a column without its column name and display format."""
        with pytest.raises(ValueError):
            ColumnValueFilter(format="Decimal2", class_name="X")

        with pytest.raises(ValueError):
            ColumnValueFilter(column="X", class_name="X")


class TestAdvancedRankingFilter:
    def test_nested_column_filters_are_preserved_in_order(self) -> None:
        """GIVEN a filter with two nested ColumnValue entries
        WHEN dumped
        THEN both survive, in declaration order — a ranking filter is an
        ordered conjunction, so order is semantic.
        """
        f = AdvancedRankingFilter(
            resultType="main",
            sampleType="127",
            pctRatio="10",
            column_values=[
                ColumnValueFilter(column="NetProfit", format="Decimal2PL", **{"class": "NetProfit"}),
                ColumnValueFilter(column="Sharpe", format="Decimal2PL", **{"class": "Sharpe"}),
            ],
        )

        dumped = f.model_dump(by_alias=True, exclude_none=True)

        assert dumped["resultType"] == "main"
        assert dumped["sampleType"] == "127"
        assert dumped["pctRatio"] == "10"
        assert [c["column"] for c in dumped["column_values"]] == ["NetProfit", "Sharpe"]

    def test_defaults_match_the_sqx_cfx_attribute_vocabulary(self) -> None:
        """The defaults must reproduce the attribute set of a real SQX export so
        a minimal filter is still a valid CFX fragment.
        """
        f = AdvancedRankingFilter()

        assert f.use is True
        assert f.result_type == "main"
        assert f.sample_type == "127"
        assert f.direction == "0"
        assert f.pct_ratio == "0"
        assert f.confidence_level == "50"
        assert f.market == "1"
        assert f.pl_type == "10"
        assert f.subresult == "30"
        assert f.class_name is None
        assert f.name is None
        assert f.column_values == []

    def test_optional_attributes_are_omitted_not_serialised_as_null(self) -> None:
        """A minimal valid condition must not carry class/name="None" text."""
        dumped = AdvancedRankingFilter().model_dump(by_alias=True, exclude_none=True)

        assert "class" not in dumped
        assert "name" not in dumped

    def test_snake_case_construction_still_works(self) -> None:
        """populate_by_name keeps the idiomatic Python spelling usable for the
        filter itself, not just for its ColumnValue children.
        """
        f = AdvancedRankingFilter(
            result_type="main",
            sample_type="127",
            pct_ratio="10",
            confidence_level="95",
            pl_type="10",
            class_name="Advanced",
            column_values=[ColumnValueFilter(column="NetProfit", format="Decimal2", class_name="NetProfit")],
        )

        dumped = f.model_dump(by_alias=True, exclude_none=True)

        assert dumped["resultType"] == "main"
        assert dumped["sampleType"] == "127"
        assert dumped["pctRatio"] == "10"
        assert dumped["confidenceLevel"] == "95"
        assert dumped["plType"] == "10"
        assert dumped["class"] == "Advanced"

    def test_field_set_matches_the_cfx_condition_model(self) -> None:
        """Drift guard: a DSL field that has no CFX counterpart (or vice versa)
        would fail at translation time, so catch it here instead.

        ``class_name`` is the DSL spelling of SQX's ``class`` attribute, which
        is a Python keyword and so is named ``class_`` in the CFX model. That
        single rename is the only tolerated difference.
        """
        assert _normalised(AdvancedRankingFilter) == _normalised(AdvancedRankingCondition)
        assert _normalised(ColumnValueFilter) == _normalised(ColumnValue)


class TestDataRangePartsDSL:
    def test_typed_segments_and_ratios_are_accepted(self) -> None:
        f = DataRangePartsDSL(
            ist="2020.01.01-2021.12.31",
            isc="2022.01.01-2022.06.30",
            oos_1="2022.07.01-2022.12.31",
            validation_ratio=0.2,
            test_ratio=0.1,
        )

        assert f.ist == "2020.01.01-2021.12.31"
        assert f.isc == "2022.01.01-2022.06.30"
        assert f.oos_1 == "2022.07.01-2022.12.31"
        assert f.validation_ratio == 0.2
        assert f.test_ratio == 0.1

    def test_unset_typed_fields_default_to_none(self) -> None:
        """Every typed field is optional: an unset field emits nothing rather
        than an empty string that would read as a real segment.
        """
        f = DataRangePartsDSL(ist="2020.01.01-2021.12.31")

        assert f.isv_10 is None
        assert f.oos_every is None
        assert f.date_to is None
        assert f.raw_xml == ""

    def test_validation_and_test_ratios_stay_distinct(self) -> None:
        """The spec forbids reinterpreting them as training ratios, so the two
        fields must never collapse into one.
        """
        f = DataRangePartsDSL(validation_ratio=0.2, test_ratio=0.1)

        assert f.validation_ratio != f.test_ratio
        dumped = f.model_dump(exclude_none=True)
        assert dumped["validation_ratio"] == 0.2
        assert dumped["test_ratio"] == 0.1

    def test_field_set_matches_the_cfx_data_range_parts_model(self) -> None:
        """Drift guard for the splat-based translator mapping: the DSL surface and
        the CFX model must expose exactly the same field names.
        """
        assert set(DataRangePartsDSL.model_fields) == set(DataRangeParts.model_fields)


class TestResearchConfigWiring:
    def test_new_fields_default_to_empty_and_are_backward_compatible(self) -> None:
        """A campaign that never mentions advanced rankings must serialise and
        validate exactly as before.
        """
        config = _config()

        assert config.advanced_ranking_filters == []
        assert config.data_range_parts is None

    def test_config_round_trips_through_dump_and_validate(self) -> None:
        """The DSL is YAML-facing, so a dumped config must re-validate cleanly
        with the filters intact.
        """
        config = _config(
            advanced_ranking_filters=[
                AdvancedRankingFilter(
                    column_values=[
                        ColumnValueFilter(column="NetProfit", format="Decimal2PL", **{"class": "NetProfit"})
                    ]
                )
            ],
            data_range_parts=DataRangePartsDSL(ist="2020.01.01-2021.12.31", test_ratio=0.1),
        )

        restored = ResearchConfig.model_validate(config.model_dump())

        assert restored.advanced_ranking_filters[0].column_values[0].column == "NetProfit"
        assert restored.data_range_parts.ist == "2020.01.01-2021.12.31"
        assert restored.data_range_parts.test_ratio == 0.1
