"""Golden round-trip for the advanced-rankings / data-range-parts feature.

`retester-advanced-rankings.cfx` is a minimal extraction of a real SQX
144/2953 Retester project: the `<Data>` and `<Rankings>` blocks are copied
**verbatim** from

    user/projects/Retester/project.cfx
    → config.xml → Project/Tasks/Task[@name="Retest"]/Settings

with the surrounding 37 KB of `<Options>`, `<RiskMoneyManagement>`,
`<CrossChecks>` and `<Databanks>` content removed. The real file is
`<Project ... version="127.129">`, below `CfxReader`'s supported floor of
130.0, and embeds `<Settings>` inline instead of referencing
`taskXMLFile`; both are reduced here so the fixture exercises the
reader/writer contract rather than the version gate or the inline-parse
branch. The two blocks under test are byte-identical to SQX's own output.

What this pins:

* **Attribute fidelity.** The spec's acceptance criterion is that a
  re-serialised CFX loses no attribute. Each of the three real
  `<Column-Value>` elements carries twelve attributes; a single dropped or
  renamed one must fail here.
* **Native-dialect preservation.** SQX wraps the filter in
  `<Left-Side valueType="column">` and pairs it with `<Comparator>` and
  `<Right-Side><Numeric-Value>`. Only the `<Column-Value>` is typed, so the
  other two exist in no field and survive *only* because the writer emits
  the untouched `raw_xml`. Re-rendering from the typed model would silently
  rank on nothing.
* **Idempotence.** Read → write → read → write must converge. Growth means
  the two `<Data>` lanes captured the same element and the writer merged
  both copies back.
* **Child order.** The merged `<Rankings>` keeps SQX's native order
  (`<MaxStrategies>`, `<FitnessCriteria>`, `<ConditionsType>`,
  `<Conditions>`, `<AutomaticDismissal>`, `<StopCondition>`).
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

from quantlab.cfx.reader import CfxReader
from quantlab.cfx.writer import CfxWriter

FIXTURE = Path(__file__).parent / "fixtures" / "retester-advanced-rankings.cfx"

# The three ranked columns of the real SQX Retester, in source order. Rank
# order *is* the ranking, so a reordered list is a different strategy
# selection, not a cosmetic difference.
EXPECTED_COLUMNS = ["AvgTradesPerMonth", "ProfitFactor", "ReturnDDRatio"]

# The full `<Column-Value>` attribute set SQX writes. Only `column`, `format`
# and `class` differ between the three filters; the other nine are constants in
# the export, which is itself the finding — a defaulting reader cannot tell a
# correct constant from a hard-coded one.
EXPECTED_COLUMN_ATTRS_COMMON = {
    "columnType": "0",
    "resultType": "main",
    "direction": "0",
    "sampleType": "127",
    "plType": "10",
    "confidenceLevel": "50",
    "market": "1",
    "subresult": "30",
    "pctRatio": "0",
}

# The `<Column-Value>` of the ProfitFactor filter, exactly as SQX writes it.
EXPECTED_PROFIT_FACTOR_COLUMN = {
    "column": "ProfitFactor",
    "format": "Decimal2",
    "class": "ProfitFactor",
    **EXPECTED_COLUMN_ATTRS_COMMON,
    "name": None,
}

# Per-filter variation across the three ranked columns, keyed by column name.
EXPECTED_COLUMN_VARIANTS = {
    "AvgTradesPerMonth": {"column": "AvgTradesPerMonth", "format": "Integer", "class": "AvgTradesPerMonth"},
    "ProfitFactor": {"column": "ProfitFactor", "format": "Decimal2", "class": "ProfitFactor"},
    "ReturnDDRatio": {"column": "ReturnDDRatio", "format": "Decimal2", "class": "ReturnDDRatio"},
}

# SQX's own child order inside `<Rankings>`, verbatim from the export.
EXPECTED_RANKINGS_CHILD_ORDER = [
    "MaxStrategies",
    "FitnessCriteria",
    "ConditionsType",
    "Conditions",
    "AutomaticDismissal",
    "StopCondition",
]

# The real `<Data>` holds only the two sub-ranges QuantLab has no typed
# field for, so both must travel through the `raw_xml` bridge.
EXPECTED_DATA_CHILDREN = ["Setups", "OutOfSample"]


def _task_xml(cfx: Path) -> str:
    with zipfile.ZipFile(cfx) as zf:
        return zf.read("Build-Task1.xml").decode("utf-8")


def _settings(cfx: Path) -> ElementTree.Element:
    return ElementTree.fromstring(_task_xml(cfx))


def _read_task(cfx: Path, tmp_path: Path, name: str):
    """Read ``cfx`` and return its Retest BuildTask.

    The fixture is copied first: the tests that round-trip it write in place,
    and a shared repo fixture must not be mutated by a test run.
    """
    work = tmp_path / name
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cfx, work)
    archive = CfxReader.read(work)
    return next(iter(archive.config.tasks.values()))


def _round_trip(source: Path, dest: Path) -> Path:
    """Read ``source``, write it to ``dest``, read ``dest`` and write it again."""
    archive = CfxReader.read(source)
    CfxWriter.write(archive, dest)
    CfxWriter.write(CfxReader.read(dest), dest)
    return dest



class TestFixtureIsRealSqxEvidence:
    """Guard the fixture itself. A silently regenerated or hand-edited fixture
    would make every assertion below vacuous, so the two blocks under test
    are compared against the real SQX export they were extracted from."""

    def test_rankings_block_matches_the_real_sqx_export(self) -> None:
        with zipfile.ZipFile(FIXTURE) as zf:
            rankings = ElementTree.fromstring(
                zf.read("Build-Task1.xml").decode("utf-8")
            ).find("Rankings")

        assert rankings is not None
        assert [child.tag for child in rankings] == EXPECTED_RANKINGS_CHILD_ORDER
        assert rankings.get("type") == "never"
        assert rankings.findtext("MaxStrategies") == "1000"
        assert rankings.findtext("ConditionsType") == "1"
        assert rankings.find("FitnessCriteria/Settings/Ranking").get("type") == (
            "ReturnDDRatio"
        )
        assert [c.tag for c in rankings.find("AutomaticDismissal")] == [
            f"Problem" for _ in range(10)
        ]
        assert rankings.find("StopCondition").get("restartCount") == "5"

    def test_data_block_matches_the_real_sqx_export(self) -> None:
        with zipfile.ZipFile(FIXTURE) as zf:
            data = ElementTree.fromstring(
                zf.read("Build-Task1.xml").decode("utf-8")
            ).find("Data")

        assert data is not None
        assert [child.tag for child in data] == EXPECTED_DATA_CHILDREN
        setup = data.find("Setups/Setup")
        assert setup.get("dateFrom") == "2003.5.5"
        assert setup.get("dateTo") == "2018.08.30"
        assert setup.find("Chart").get("symbol") == "GBPUSD_M1_dukas"
        assert setup.find("Chart").get("timeframe") == "H1"
        assert setup.find("Chart").get("spread") == "3"
        assert data.find("OutOfSample").get("showGraph") == "false"

    def test_conditions_use_the_native_left_side_dialect(self) -> None:
        """The fixture must keep SQX's ``<Left-Side>`` wrapper. Replacing it with
        QuantLab's direct ``<Column-Value>`` child would make the reader's
        two-dialect handling untested against real evidence.
        """
        with zipfile.ZipFile(FIXTURE) as zf:
            conditions = ElementTree.fromstring(
                zf.read("Build-Task1.xml").decode("utf-8")
            ).find("Rankings/Conditions")

        assert conditions is not None
        found = conditions.findall("Condition")
        assert len(found) == 3
        for condition in found:
            left_side = condition.find("Left-Side")
            assert left_side is not None
            assert left_side.get("valueType") == "column"
            assert len(left_side.findall("Column-Value")) == 1
            assert condition.find("Comparator").get("value") == ">"
            assert condition.find("Right-Side").get("valueType") == "numeric"
            assert condition.find("Right-Side/Numeric-Value").get("value")

    def test_fixture_carries_no_typed_data_range_elements(self) -> None:
        """SQX's real ``<Data>`` has no ``<IST>``/``<OOSEvery>`` children — those
        element names are a QuantLab convention (see ``models.py``), not
        transcribed SQX output. Pinning this keeps the golden honest about
        what it can and cannot prove.
        """
        with zipfile.ZipFile(FIXTURE) as zf:
            data = ElementTree.fromstring(
                zf.read("Build-Task1.xml").decode("utf-8")
            ).find("Data")

        assert [child.tag for child in data] == EXPECTED_DATA_CHILDREN


class TestReaderAgainstRealSqxCfx:
    def test_every_rankings_condition_is_recovered(self, tmp_path: Path) -> None:
        task = _read_task(FIXTURE, tmp_path, "read.cfx")

        assert task.advanced_rankings is not None
        assert [c.column_values[0].column for c in task.advanced_rankings.conditions] == (
            EXPECTED_COLUMNS
        )

    def test_column_attribute_fidelity_is_exact(self, tmp_path: Path) -> None:
        """The spec's acceptance criterion is CFX fidelity. Asserting the whole
        alias-keyed mapping means a renamed, defaulted or dropped attribute
        fails rather than silently changing which strategies rank.
        """
        task = _read_task(FIXTURE, tmp_path, "read.cfx")

        profit_factor = task.advanced_rankings.conditions[1]
        (column,) = profit_factor.column_values
        assert column.model_dump(by_alias=True) == EXPECTED_PROFIT_FACTOR_COLUMN

    def test_integer_and_decimal_formats_are_distinguished(self, tmp_path: Path) -> None:
        """SQX writes ``format="Integer"`` for AvgTradesPerMonth and
        ``format="Decimal2"`` for the two ratios. Collapsing them would change
        how SQX parses the comparison value.
        """
        task = _read_task(FIXTURE, tmp_path, "read.cfx")

        formats = [c.column_values[0].format for c in task.advanced_rankings.conditions]
        assert formats == ["Integer", "Decimal2", "Decimal2"]

    def test_all_conditions_are_enabled(self, tmp_path: Path) -> None:
        task = _read_task(FIXTURE, tmp_path, "read.cfx")

        assert [c.use for c in task.advanced_rankings.conditions] == [True, True, True]

    def test_data_range_parts_preserve_the_sqx_subranges(self, tmp_path: Path) -> None:
        """Spec scenario "Unknown range passthrough". ``<Setups>`` and
        ``<OutOfSample>`` have no typed field; losing them would drop the date
        range and the out-of-sample switch from the user's project.
        """
        task = _read_task(FIXTURE, tmp_path, "read.cfx")

        parts = task.data_range_parts
        assert parts is not None
        assert '<Setups>' in parts.raw_xml
        assert 'dateFrom="2003.5.5"' in parts.raw_xml
        assert 'dateTo="2018.08.30"' in parts.raw_xml
        assert '<OutOfSample showGraph="false" />' in parts.raw_xml
        # Nothing typed is present in the real file, and inventing values would
        # misrepresent it.
        assert parts.ist is None
        assert parts.oos_every is None
        assert parts.validation_ratio is None

    def test_untyped_rankings_content_survives_in_raw_xml(self, tmp_path: Path) -> None:
        """``<Comparator>`` and ``<Right-Side>`` have no typed field. They exist
        in the writer's source *only* as untouched raw XML, which is why the
        writer must never re-render ``<Rankings>`` from the typed model.
        """
        task = _read_task(FIXTURE, tmp_path, "read.cfx")

        raw = task.rankings_section.raw_xml
        assert '<Left-Side valueType="column">' in raw
        assert '<Comparator value="&gt;" />' in raw
        assert '<Right-Side valueType="numeric">' in raw
        assert '<Numeric-Value value="1.3" />' in raw
        assert 'restartCount="5"' in raw


class TestGoldenRoundTrip:
    def test_round_trip_is_byte_stable(self, tmp_path: Path) -> None:
        """Read → write → read → write must converge on the first pass. A second
        pass that differs means the writer is not idempotent, which is exactly
        the failure mode a golden exists to catch.
        """
        first = _round_trip(FIXTURE, tmp_path / "rt1.cfx")
        second = _round_trip(first, tmp_path / "rt2.cfx")

        assert _task_xml(second) == _task_xml(first)

    def test_round_trip_preserves_the_rankings_child_order(
        self, tmp_path: Path
    ) -> None:
        """SQX reads ``<Rankings>`` positionally. The writer must keep the native
        order and must not split the section into two ``<Rankings>`` elements —
        that is what a non-merging flat/complex lane produces.
        """
        out = _round_trip(FIXTURE, tmp_path / "rt.cfx")

        settings = _settings(out)
        assert settings.findall("Rankings") == settings.findall("Rankings")
        assert len(settings.findall("Rankings")) == 1
        (rankings,) = settings.findall("Rankings")
        assert [child.tag for child in rankings] == EXPECTED_RANKINGS_CHILD_ORDER
        assert rankings.get("type") == "never"

    def test_round_trip_preserves_a_single_data_element(self, tmp_path: Path) -> None:
        """The ``<Data>`` split between the flat key-value lane and the typed
        sub-range lane is the growth risk: emitting both produces two siblings.
        """
        out = _round_trip(FIXTURE, tmp_path / "rt.cfx")

        settings = _settings(out)
        assert len(settings.findall("Data")) == 1
        (data,) = settings.findall("Data")
        assert [child.tag for child in data] == EXPECTED_DATA_CHILDREN

    def test_round_trip_loses_no_condition_attribute(self, tmp_path: Path) -> None:
        """Every attribute of every ``<Column-Value>`` must survive the cycle.
        Compared element-by-element so a failure names the specific filter.
        """
        out = _round_trip(FIXTURE, tmp_path / "rt.cfx")

        columns = _settings(out).findall("Rankings/Conditions/Condition/Left-Side/Column-Value")
        assert len(columns) == 3
        for column, expected_column in zip(columns, EXPECTED_COLUMNS, strict=True):
            assert dict(column.attrib) == (
                EXPECTED_COLUMN_VARIANTS[expected_column]
                | EXPECTED_COLUMN_ATTRS_COMMON
            )

    def test_round_trip_loses_no_comparator_or_threshold(self, tmp_path: Path) -> None:
        """The numeric thresholds are the ranking's actual criteria. Dropping
        ``<Right-Side>`` leaves SQX ranking on an unconstrained filter.
        """
        out = _round_trip(FIXTURE, tmp_path / "rt.cfx")

        conditions = _settings(out).findall("Rankings/Conditions/Condition")
        assert len(conditions) == 3
        assert [c.find("Comparator").get("value") for c in conditions] == [">"] * 3
        assert [c.find("Right-Side/Numeric-Value").get("value") for c in conditions] == [
            "2",
            "1.3",
            "4",
        ]

    def test_round_trip_preserves_the_data_setup_window(self, tmp_path: Path) -> None:
        out = _round_trip(FIXTURE, tmp_path / "rt.cfx")

        setup = _settings(out).find("Data/Setups/Setup")
        assert setup.get("dateFrom") == "2003.5.5"
        assert setup.get("dateTo") == "2018.08.30"
        assert setup.get("engine") == "MetaTrader4"
        assert setup.find("Chart").get("spread") == "3"

    def test_rereading_a_round_tripped_file_keeps_the_typed_lanes(
        self, tmp_path: Path
    ) -> None:
        """The point of the typed lanes: a file QuantLab wrote can be read back
        into the same typed state, so a later agent can reason about the
        ranking without re-parsing XML.
        """
        out = _round_trip(FIXTURE, tmp_path / "rt.cfx")

        task = _read_task(out, tmp_path, "reread.cfx")
        assert task.advanced_rankings is not None
        assert [c.column_values[0].column for c in task.advanced_rankings.conditions] == (
            EXPECTED_COLUMNS
        )
        assert task.data_range_parts is not None
        assert 'dateFrom="2003.5.5"' in task.data_range_parts.raw_xml

    def test_project_shape_is_preserved(self, tmp_path: Path) -> None:
        out = _round_trip(FIXTURE, tmp_path / "rt.cfx")

        archive = CfxReader.read(out)
        assert archive.config.name == "Retester"
        assert list(archive.config.tasks) == ["Build-Task1.xml"]


class TestFixtureIsNotMutated:
    def test_round_trip_does_not_touch_the_committed_fixture(
        self, tmp_path: Path
    ) -> None:
        """A test that rewrote the shared fixture would make every later run
        compare the golden against itself.
        """
        before = FIXTURE.read_bytes()

        _round_trip(FIXTURE, tmp_path / "rt.cfx")

        assert FIXTURE.read_bytes() == before


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
