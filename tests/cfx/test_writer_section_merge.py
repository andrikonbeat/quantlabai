"""Tests for the CfxWriter section merge and the advanced-ranking dom helpers.

Covers task 3.1 of ``data-range-parts-and-ranking-filters``: the writer must
emit exactly one ``<Rankings>`` / ``<Data>`` element per ``<Settings>`` root
while preserving both the flat ``<Setting>`` lane and the complex raw-XML lane.
"""

import zipfile
from io import BytesIO
from xml.etree import ElementTree

from quantlab.cfx.models import (
    AdvancedRankingCondition,
    BuildTask,
    CfxArchive,
    CfxConfig,
    ColumnValue,
    DataRangeParts,
    SetAdvancedRankingsInstruction,
    SettingsSection,
)
from quantlab.cfx.patcher import CfxPatcher
from quantlab.cfx.writer import CfxWriter


def _archive(task) -> CfxArchive:
    """Wrap a BuildTask in the single-task archive shape the writer serialises."""
    return CfxArchive(
        config=CfxConfig(task=task, schema_version="141.2219"),
        task_files={"Build-Task1.xml": task},
    )


def _task_xml(task, name: str = "Build-Task1.xml") -> ElementTree.Element:
    """Serialise a BuildTask through the real writer and return its parsed root."""
    raw = CfxWriter.to_bytes(_archive(task))
    with zipfile.ZipFile(BytesIO(raw), "r") as zf:
        return ElementTree.fromstring(zf.read(name).decode("utf-8"))


def _condition() -> AdvancedRankingCondition:
    return AdvancedRankingCondition(
        column_values=[ColumnValue(column="NetProfit", format="Decimal2", class_="NetProfit")],
    )


def _flat_rankings_task() -> BuildTask:
    """A task on the pre-existing simple path: one flat ``Criterion1@*`` criterion."""
    task = BuildTask()
    task.rankings = SettingsSection(name="Rankings", settings={})
    CfxPatcher(_archive(task)).add_ranking_condition("sharpe", ">", 1.0)
    return task


def _mixed_task() -> BuildTask:
    """A task carrying the flat criteria lane AND the advanced conditions lane."""
    task = _flat_rankings_task()
    CfxPatcher(_archive(task)).apply(
        [SetAdvancedRankingsInstruction(conditions=[_condition()])]
    )
    return task


class TestRankingsSectionMerge:
    def test_flat_and_complex_rankings_emit_a_single_element(self) -> None:
        """GIVEN the flat Criterion settings lane AND the advanced <Conditions> lane
        WHEN the task is serialised
        THEN exactly one <Rankings> element is emitted, because the SQX <Settings>
        schema admits a single <Rankings> child.
        """
        root = _task_xml(_mixed_task())

        assert [child.tag for child in root].count("Rankings") == 1

    def test_merge_keeps_both_lanes_inside_the_single_element(self) -> None:
        """Merging must not silently drop either lane: the flat criteria and the
        nested advanced conditions both have to survive in the same element.
        """
        root = _task_xml(_mixed_task())

        (rankings,) = [c for c in root if c.tag == "Rankings"]
        child_tags = [child.tag for child in rankings]

        assert "Conditions" in child_tags, "advanced lane was dropped by the merge"
        flat_settings = [c for c in rankings if c.tag == "Setting"]
        assert [s.get("key") for s in flat_settings] == [
            "Criterion1@metric",
            "Criterion1@operator",
            "Criterion1@value",
        ]
        assert [s.get("value") for s in flat_settings] == ["sharpe", ">", "1"]

    def test_complex_children_are_nested_not_flattened(self) -> None:
        """The advanced lane must keep its own nesting: <Condition> and
        <Column-Value> stay descendants of <Conditions>.
        """
        root = _task_xml(_mixed_task())

        (rankings,) = [c for c in root if c.tag == "Rankings"]
        (conditions,) = [c for c in rankings if c.tag == "Conditions"]
        (condition,) = [c for c in conditions if c.tag == "Condition"]
        (column_value,) = [c for c in condition if c.tag == "Column-Value"]

        assert condition.get("use") == "true"
        assert column_value.get("column") == "NetProfit"
        assert column_value.get("format") == "Decimal2"
        assert column_value.get("class") == "NetProfit"

    def test_settings_lane_alone_still_emits_one_element(self) -> None:
        """Regression guard for the pre-existing simple path: with no complex lane
        the writer keeps emitting the flat <Rankings> it always did.
        """
        root = _task_xml(_flat_rankings_task())

        (rankings,) = [c for c in root if c.tag == "Rankings"]
        assert [c.tag for c in rankings] == ["Setting", "Setting", "Setting"]

    def test_complex_lane_alone_still_emits_one_element(self) -> None:
        """The advanced-only path (no flat criteria) is unchanged: one element."""
        build_task = BuildTask()
        CfxPatcher(_archive(build_task)).apply(
            [SetAdvancedRankingsInstruction(conditions=[_condition()])]
        )

        root = _task_xml(build_task)

        assert [c.tag for c in root].count("Rankings") == 1


class TestDataRangePartsEmission:
    def test_typed_parts_merge_into_the_existing_data_section(self) -> None:
        """GIVEN a flat <Data> SettingsSection AND typed DataRangeParts
        WHEN the task is serialised
        THEN one <Data> element holds the <Setting> entries and the typed
        sub-range elements together.
        """
        build_task = BuildTask()
        build_task.data = SettingsSection(name="Data", settings={"EURUSD_H1": "true"})
        build_task.data_range_parts = DataRangeParts(ist="2020.01.01-2022.12.31", oos_1="2023.01.01-2023.12.31")

        root = _task_xml(build_task)

        assert [c.tag for c in root].count("Data") == 1
        (data,) = [c for c in root if c.tag == "Data"]
        assert [c.get("value") for c in data if c.tag == "IST"] == ["2020.01.01-2022.12.31"]
        assert [c.get("value") for c in data if c.tag == "OOS1"] == ["2023.01.01-2023.12.31"]
        assert [c.get("key") for c in data if c.tag == "Setting"] == ["EURUSD_H1"]

    def test_typed_parts_alone_emit_a_data_element(self) -> None:
        """With no flat <Data> lane the typed parts still reach the output."""
        build_task = BuildTask()
        build_task.data_range_parts = DataRangeParts(validation_ratio=0.2, test_ratio=0.1)

        root = _task_xml(build_task)

        (data,) = [c for c in root if c.tag == "Data"]
        assert [c.get("value") for c in data if c.tag == "ValidationRatio"] == ["0.2"]
        assert [c.get("value") for c in data if c.tag == "TestRatio"] == ["0.1"]

    def test_absent_parts_emit_no_extra_data_element(self) -> None:
        """A task with only a flat <Data> lane is untouched by the new code path."""
        build_task = BuildTask()
        build_task.data = SettingsSection(name="Data", settings={"EURUSD_H1": "true"})

        root = _task_xml(build_task)

        (data,) = [c for c in root if c.tag == "Data"]
        assert [c.tag for c in data] == ["Setting"]

    def test_raw_xml_bridge_is_preserved_verbatim(self) -> None:
        """GIVEN an unknown sub-range parked in raw_xml
        WHEN serialised, THEN that content is emitted alongside the typed fields.
        """
        build_task = BuildTask()
        build_task.data_range_parts = DataRangeParts(
            isc="2022.01.01-2022.06.30",
            raw_xml='<ProprietaryRange value="x" />',
        )

        root = _task_xml(build_task)

        (data,) = [c for c in root if c.tag == "Data"]
        assert [c.tag for c in data] == ["ISC", "ProprietaryRange"]

    def test_raw_xml_only_with_several_siblings_stays_in_one_data_element(self) -> None:
        """raw_xml may hold several sibling elements with no <Data> wrapper of its
        own; they must be re-wrapped rather than dropped by the XML parser.
        """
        build_task = BuildTask()
        build_task.data_range_parts = DataRangeParts(
            raw_xml='<Alpha value="1" />\n<Beta value="2" />',
        )

        root = _task_xml(build_task)

        (data,) = [c for c in root if c.tag == "Data"]
        assert [(c.tag, c.get("value")) for c in data] == [("Alpha", "1"), ("Beta", "2")]

    def test_raw_xml_only_with_a_single_element_is_not_dropped(self) -> None:
        """A raw_xml block holding exactly one element has no children of its own,
        so it must not be mistaken for the empty <Data /> placeholder that
        DataRangeParts.to_xml() emits when nothing at all is set.
        """
        build_task = BuildTask()
        build_task.data_range_parts = DataRangeParts(raw_xml='<ProprietaryRange value="x" />')

        root = _task_xml(build_task)

        (data,) = [c for c in root if c.tag == "Data"]
        assert [(c.tag, c.get("value")) for c in data] == [("ProprietaryRange", "x")]

    def test_empty_parts_object_emits_no_data_element(self) -> None:
        """A DataRangeParts with nothing set must not create a placeholder
        <Data /> in the output — the writer skips the empty element.
        """
        build_task = BuildTask()
        build_task.data_range_parts = DataRangeParts()

        root = _task_xml(build_task)

        assert [c.tag for c in root].count("Data") == 0
