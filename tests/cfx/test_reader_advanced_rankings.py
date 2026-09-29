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


