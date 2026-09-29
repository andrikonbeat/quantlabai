"""CfxReader wiring for the advanced-rankings and data-range-parts typed lanes.

Phase 1b/2b/3b of ``data-range-parts-and-ranking-filters`` taught the patcher,
the writer, the DSL and the phase4 template to *emit* nested
``<Rankings><Conditions>`` blocks and typed ``<Data>`` sub-ranges, but
``CfxReader`` still stopped at the raw-XML bridge: reading a CFX back gave a
task whose ``data_range_parts`` and advanced conditions were unreachable. A
golden round-trip cannot be proven while the reader is blind on the write side.

These tests pin the reader half of the contract:

* real SQX nests ``<Column-Value>`` under ``<Left-Side valueType="column">``,
  while QuantLab's own renderer writes it as a direct child — both dialects
  must parse;
* typed ``<Data>`` sub-ranges land in their typed fields and every unmodelled
  sibling is parked verbatim in ``raw_xml`` (the spec's "unknown range
  passthrough" scenario);
* a section that carries nothing typed stays ``None``, so the pre-existing
  simple lanes are untouched.
"""

import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from quantlab.cfx.models import CfxArchive, CfxConfig
from quantlab.cfx.reader import CfxReader

CONFIG_VERSION = "141.2219"


def _archive_bytes(task_xml: str) -> bytes:
    """Wrap a ``<Settings>`` document in the single-task CFX ZIP shape."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "config.xml",
            f'<Task type="Build" version="{CONFIG_VERSION}" taskXMLFile="Build-Task1.xml"/>',
        )
        zf.writestr("Build-Task1.xml", task_xml)
    return buf.getvalue()


def _read_task(task_xml: str, tmp_path: Path):
    """Read a single-task CFX and return its BuildTask."""
    cfx = tmp_path / "probe.cfx"
    cfx.write_bytes(_archive_bytes(task_xml))
    return CfxReader.read(cfx).config.task


# A verbatim slice of the real SQX 144/2953 Retester dialect: the column filter
# is wrapped in <Left-Side>, compared with <Comparator> and closed by a
# <Right-Side><Numeric-Value> triple.
SQX_CONDITIONS = """<Rankings type="never">
  <MaxStrategies>1000</MaxStrategies>
  <ConditionsType>1</ConditionsType>
  <Conditions>
    <Condition use="true">
      <Left-Side valueType="column">
        <Column-Value column="ProfitFactor" columnType="0" format="Decimal2" resultType="main" direction="0" sampleType="127" plType="10" confidenceLevel="50" market="1" subresult="30" pctRatio="0" class="ProfitFactor" />
      </Left-Side>
      <Comparator value="&gt;" />
      <Right-Side valueType="numeric">
        <Numeric-Value value="1.3" />
      </Right-Side>
    </Condition>
  </Conditions>
  <StopCondition type="databank-full" passedStrategies="1000" />
</Rankings>"""


class TestAdvancedRankingsParsing:
    def test_sqx_left_side_wrapped_column_value_is_parsed(self, tmp_path: Path) -> None:
        """GIVEN a real SQX <Condition> that wraps the column filter in <Left-Side>
        WHEN the archive is read
        THEN the column filter still reaches the typed lane. Missing the
        wrapper is how a reader silently returns zero conditions for every real
        SQX Retester CFX.
        """
        task = _read_task(f"<Settings>{SQX_CONDITIONS}</Settings>", tmp_path)

        assert task.advanced_rankings is not None
        (condition,) = task.advanced_rankings.conditions
        (column,) = condition.column_values
        assert column.column == "ProfitFactor"
        assert column.format == "Decimal2"
        assert column.class_ == "ProfitFactor"

    def test_direct_column_value_child_is_parsed(self, tmp_path: Path) -> None:
        """GIVEN a <Column-Value> written as a direct <Condition> child — the shape
        QuantLab's own ``build_conditions_xml`` emits
        WHEN the archive is read
        THEN it parses identically, so a QuantLab-authored CFX round-trips.
        """
        task = _read_task(
            "<Settings><Rankings><Conditions>"
            '<Condition use="true">'
            '<Column-Value column="NetProfit" format="Decimal2PL" class="NetProfit" />'
            "</Condition>"
            "</Conditions></Rankings></Settings>",
            tmp_path,
        )

        (condition,) = task.advanced_rankings.conditions
        assert [cv.column for cv in condition.column_values] == ["NetProfit"]

    def test_every_column_attribute_is_captured(self, tmp_path: Path) -> None:
        """The golden's <Column-Value> carries thirteen attributes; the spec's
        acceptance criterion is CFX fidelity, so a single dropped attribute
        must fail here.
        """
        task = _read_task(f"<Settings>{SQX_CONDITIONS}</Settings>", tmp_path)

        (column,) = task.advanced_rankings.conditions[0].column_values
        assert column.model_dump(by_alias=True) == {
            "column": "ProfitFactor",
            "columnType": "0",
            "format": "Decimal2",
            "resultType": "main",
            "direction": "0",
            "sampleType": "127",
            "plType": "10",
            "confidenceLevel": "50",
            "market": "1",
            "subresult": "30",
            "pctRatio": "0",
            "class": "ProfitFactor",
            "name": None,
        }

    def test_condition_attributes_and_use_flag(self, tmp_path: Path) -> None:
        """GIVEN <Condition use="false"> with explicit filter attributes
        WHEN read
        THEN ``use`` is a real bool and the attributes override the defaults,
        so a disabled ranking filter cannot be re-emitted as enabled.
        """
        task = _read_task(
            "<Settings><Rankings><Conditions>"
            '<Condition use="false" resultType="secondary" sampleType="42" class="Custom" name="gate">'
            '<Column-Value column="Sharpe" format="Decimal2" class="Sharpe" />'
            "</Condition>"
            "</Conditions></Rankings></Settings>",
            tmp_path,
        )

        (condition,) = task.advanced_rankings.conditions
        assert condition.use is False
        assert condition.result_type == "secondary"
        assert condition.sample_type == "42"
        assert condition.class_ == "Custom"
        assert condition.name == "gate"

    def test_numeric_use_flag_spelling(self, tmp_path: Path) -> None:
        """``use="1"`` is a legal XML boolean spelling. A reader that only
        accepts "true" would flip the filter off on a foreign file.
        """
        task = _read_task(
            "<Settings><Rankings><Conditions>"
            '<Condition use="1">'
            '<Column-Value column="Drawdown" format="Decimal2" class="Drawdown" />'
            "</Condition>"
            "</Conditions></Rankings></Settings>",
            tmp_path,
        )

        assert task.advanced_rankings.conditions[0].use is True

    def test_multiple_conditions_keep_source_order(self, tmp_path: Path) -> None:
        """Rank order is the ranking: a reordered list would rank strategies on
        a different criterion.
        """
        task = _read_task(
            "<Settings><Rankings><Conditions>"
            '<Condition use="true"><Left-Side><Column-Value column="A" format="Integer" class="A" /></Left-Side></Condition>'
            '<Condition use="true"><Left-Side><Column-Value column="B" format="Integer" class="B" /></Left-Side></Condition>'
            '<Condition use="true"><Left-Side><Column-Value column="C" format="Integer" class="C" /></Left-Side></Condition>'
            "</Conditions></Rankings></Settings>",
            tmp_path,
        )

        assert [c.column_values[0].column for c in task.advanced_rankings.conditions] == [
            "A",
            "B",
            "C",
        ]

    def test_rankings_raw_xml_stays_the_verbatim_writer_source(
        self, tmp_path: Path
    ) -> None:
        """The typed lane is for querying; the writer emits ``raw_xml``. If the
        reader rewrote it, the <Comparator>/<Right-Side> content that has no
        typed field would be dropped on the next write.
        """
        task = _read_task(f"<Settings>{SQX_CONDITIONS}</Settings>", tmp_path)

        assert task.rankings_section is not None
        assert task.rankings_section.raw_xml == SQX_CONDITIONS
        assert task.advanced_rankings.raw_xml == SQX_CONDITIONS

    def test_typed_lane_does_not_lose_the_unmodelled_condition_content(
        self, tmp_path: Path
    ) -> None:
        """The same guarantee expressed as a content assertion: the comparator
        and the numeric threshold live in no typed field, so they survive only
        if ``raw_xml`` is the untouched source element.
        """
        task = _read_task(f"<Settings>{SQX_CONDITIONS}</Settings>", tmp_path)

        raw = task.advanced_rankings.raw_xml
        assert '<Comparator value="&gt;" />' in raw
        assert '<Numeric-Value value="1.3" />' in raw
        assert '<Left-Side valueType="column">' in raw

    def test_empty_conditions_block_reports_no_typed_lane(self, tmp_path: Path) -> None:
        """GIVEN a ``<Conditions>`` block that carries no ``<Condition>``
        WHEN read
        THEN there is nothing to query, so the typed lane stays ``None`` rather
        than reporting an empty list that a caller could mistake for "the user
        configured no filters".
        """
        task = _read_task(
            "<Settings><Rankings><Conditions /></Rankings></Settings>", tmp_path
        )

        assert task.advanced_rankings is None
        assert task.rankings_section is not None
        assert "<Conditions />" in task.rankings_section.raw_xml

    def test_rankings_without_conditions_leaves_the_typed_lane_unset(
        self, tmp_path: Path
    ) -> None:
        """Regression guard for the pre-existing simple path: a ``<Rankings>``
        holding only flat settings has no advanced lane to report, and must not
        be reported as an empty one.
        """
        task = _read_task(
            '<Settings><Rankings><Setting key="Criterion1@metric" value="sharpe" /></Rankings></Settings>',
            tmp_path,
        )

        assert task.advanced_rankings is None
        assert task.rankings_section is not None
        assert "Criterion1@metric" in task.rankings_section.raw_xml

    def test_absent_rankings_section_leaves_the_typed_lane_unset(
        self, tmp_path: Path
    ) -> None:
        task = _read_task("<Settings><Options /></Settings>", tmp_path)

        assert task.advanced_rankings is None
        assert task.rankings_section is None


class TestDataRangePartsParsing:
    def test_typed_subranges_land_in_their_fields(self, tmp_path: Path) -> None:
        """GIVEN the typed sub-range elements the model declares
        WHEN read
        THEN each one populates its named field, so a caller can inspect the
        split without re-parsing XML.
        """
        task = _read_task(
            "<Settings><Data>"
            '<IST value="0.5" /><OOSEvery value="0.25" /><ValidationRatio value="0.2" />'
            '<DateFrom value="2020.01.01" /><DateTo value="2023.12.31" />'
            "</Data></Settings>",
            tmp_path,
        )

        parts = task.data_range_parts
        assert parts is not None
        assert parts.ist == "0.5"
        assert parts.oos_every == "0.25"
        assert parts.date_from == "2020.01.01"
        assert parts.date_to == "2023.12.31"

    def test_split_ratios_stay_floats_and_distinct(self, tmp_path: Path) -> None:
        """The spec forbids reinterpreting the split ratios as a training ratio,
        so both must survive as independent floats.
        """
        task = _read_task(
            "<Settings><Data>"
            '<ValidationRatio value="0.2" /><TestRatio value="0.1" />'
            "</Data></Settings>",
            tmp_path,
        )

        parts = task.data_range_parts
        assert parts.validation_ratio == 0.2
        assert parts.test_ratio == 0.1

    def test_unknown_subranges_are_parked_in_raw_xml(self, tmp_path: Path) -> None:
        """Spec scenario "Unknown range passthrough": the real SQX <Data> holds
        <Setups>/<OutOfSample>, which have no typed field. They must survive
        verbatim or a read/write cycle would silently drop the date range and
        the out-of-sample switch.
        """
        task = _read_task(
            "<Settings><Data>"
            '<IST value="0.5" />'
            '<Setups><Setup dateFrom="2003.5.5" dateTo="2018.08.30" /></Setups>'
            '<OutOfSample showGraph="false" />'
            "</Data></Settings>",
            tmp_path,
        )

        parts = task.data_range_parts
        assert parts.ist == "0.5"
        assert 'dateFrom="2003.5.5"' in parts.raw_xml
        assert 'dateTo="2018.08.30"' in parts.raw_xml
        assert "<OutOfSample" in parts.raw_xml
        assert "<Setups>" in parts.raw_xml

    def test_typed_and_raw_lanes_round_trip_through_to_xml(
        self, tmp_path: Path
    ) -> None:
        """The bridge is bidirectional: what the reader recovered must
        re-serialise to the same element set, or the reader would be a lossy
        step in the middle of the round trip.
        """
        source = (
            '<IST value="0.5" />'
            '<OutOfSample showGraph="false" />'
        )
        task = _read_task(f"<Settings><Data>{source}</Data></Settings>", tmp_path)

        rendered = task.data_range_parts.to_xml()
        assert '<IST value="0.5" />' in rendered
        assert '<OutOfSample showGraph="false" />' in rendered

    def test_data_section_without_typed_or_unknown_content(self, tmp_path: Path) -> None:
        """An empty ``<Data>`` reports an empty parts model rather than
        ``None``: the section exists, it simply configures nothing.
        """
        task = _read_task("<Settings><Data /></Settings>", tmp_path)

        assert task.data_range_parts is not None
        assert task.data_range_parts.ist is None
        assert task.data_range_parts.raw_xml == ""

    def test_absent_data_section_leaves_the_typed_lane_unset(
        self, tmp_path: Path
    ) -> None:
        task = _read_task("<Settings><Options /></Settings>", tmp_path)

        assert task.data_range_parts is None
        assert task.data is None


class TestDataLanesAreDisjoint:
    """``<Data>`` feeds two lanes: the flat ``<Setting>`` SettingsSection and the
    typed sub-range model. If the reader hands the same child to both, the
    writer merges them back and the section **grows on every cycle**.
    """

    def test_flat_lane_holds_only_setting_children(self, tmp_path: Path) -> None:
        task = _read_task(
            '<Settings><Data><Setting key="Symbol@symbol" value="EURUSD" />'
            '<IST value="0.5" /><OutOfSample showGraph="false" /></Data></Settings>',
            tmp_path,
        )

        assert task.data.settings == {
            "Setting@key": "Symbol@symbol",
            "Setting@value": "EURUSD",
        }

    def test_nested_elements_do_not_leak_into_the_flat_lane(
        self, tmp_path: Path
    ) -> None:
        """The real SQX ``<Setups><Setup dateFrom=.../></Setups>`` tree must stay
        in the passthrough lane. Flattening it into the key-value lane would
        rewrite the whole subtree as ``<Setting key="Setups.Setup@dateFrom"/>``
        on the next write, silently replacing real XML with key-value pairs.
        """
        task = _read_task(
            '<Settings><Data><Setups><Setup dateFrom="2003.5.5" /></Setups></Data></Settings>',
            tmp_path,
        )

        assert task.data.settings == {}
        assert "<Setups>" in task.data_range_parts.raw_xml

    def test_second_cycle_does_not_grow_the_data_section(self, tmp_path: Path) -> None:
        """The invariant a golden round-trip depends on: re-writing what was
        read must not add elements. Growth means the two lanes captured the
        same child, and the writer merged both copies back.

        Scoped to the typed lane and the ``<Rankings>`` complex lane, which is
        what this change owns. The flat key-value lane has a *separate*,
        pre-existing defect — the reader keys entries ``Setting@key`` and the
        writer re-emits them under that mangled key, so a real SQX ``<Setting>``
        set does not survive a cycle verbatim. Fixing that is a redesign of the
        SettingsSection projection for every section, out of scope here.
        """
        first = _round_trip(
            '<Settings><Data><Setting key="Symbol@symbol" value="EURUSD" />'
            '<IST value="0.5" /><OutOfSample showGraph="false" /></Data>'
            f"{SQX_CONDITIONS}</Settings>",
            tmp_path / "first.cfx",
        )
        second = _round_trip(
            first.decode("utf-8"), tmp_path / "second.cfx"
        )

        assert _data_element_signature(second) == _data_element_signature(first)
        assert _rankings_xml(second) == _rankings_xml(first)

    def test_flat_settings_are_not_duplicated_into_the_typed_lane(
        self, tmp_path: Path
    ) -> None:
        """Each ``<Setting>`` belongs to exactly one lane. Copying it into the
        typed model's ``raw_xml`` makes the writer emit it twice.
        """
        task = _read_task(
            '<Settings><Data><Setting key="Symbol@symbol" value="EURUSD" />'
            '<IST value="0.5" /></Data></Settings>',
            tmp_path,
        )

        assert "<Setting" not in task.data_range_parts.raw_xml
        assert task.data.settings == {
            "Setting@key": "Symbol@symbol",
            "Setting@value": "EURUSD",
        }


def _data_element_signature(task_xml: bytes) -> list[tuple[str, str | None]]:
    """The ``<Data>`` children as ``(tag, value)`` pairs, order preserved."""
    root = ElementTree.fromstring(task_xml)
    (data,) = [c for c in root if c.tag == "Data"]
    return [(c.tag, c.get("value") or c.get("key")) for c in data]


def _rankings_xml(task_xml: bytes) -> str:
    root = ElementTree.fromstring(task_xml)
    (rankings,) = [c for c in root if c.tag == "Rankings"]
    return ElementTree.tostring(rankings, encoding="unicode")


def _round_trip(task_xml: str, dest: Path) -> bytes:
    """Write ``task_xml`` as a CFX, read it back, write it again; return pass 2."""
    from quantlab.cfx.writer import CfxWriter

    task = _read_task(task_xml, dest.parent)
    archive = CfxArchive(
        config=CfxConfig(task=task, schema_version=CONFIG_VERSION),
        task_files={"Build-Task1.xml": task},
    )
    CfxWriter.write(archive, dest)
    reread = CfxReader.read(dest)
    CfxWriter.write(reread, dest)
    with zipfile.ZipFile(dest) as zf:
        return zf.read("Build-Task1.xml")
