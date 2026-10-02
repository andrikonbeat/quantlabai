"""Golden test for the phase4 Retester emission, judged against real SQX.

Task 3.5 pinned the phase4 placeholders against hand-written expectations:
that the block appears, that its child order is what we chose, and that
leaving it unset reproduces the previous XML byte for byte. Those are the
right tests for *our* output, but they cannot answer the only question a
user actually cares about — would SQX understand it?

This module judges the emission against a second oracle instead: the real
SQX 144/2953 Retester export in
``tests/cfx/fixtures/retester-advanced-rankings.cfx``, whose ``<Data>`` and
``<Rankings>`` blocks are byte-identical to SQX's own output. Two artifacts
are therefore compared that never met: what SQX writes, and what QuantLab
writes. Parity between them is evidence that QuantLab speaks SQX's dialect
rather than a dialect invented alongside it.

What parity buys specifically:

* **Attribute parity.** ``<Column-Value>`` carries twelve attributes and a
  renamed or invented one makes SQX silently drop the filter — the strategy
  ranks on nothing and the user sees no error. Asserting the emitted set
  equals SQX's set catches a rename in either direction.
* **Condition-level parity.** In the real export a ``<Condition>`` carries
  only ``use``; everything else lives on the nested ``<Column-Value>``. A
  condition-level field QuantLab emits as an explicit non-default would
  still parse, so this pins the names rather than the values.
* **Cross-oracle equivalence.** The strongest check: a phase4-emitted
  condition and the real SQX condition describing the same column must
  land on the *same typed model* when read back. Both sides are read by
  the same reader, so agreement cannot come from the reader alone.

The data-range element names (``<IST>``, ``<OOSEvery>``) are deliberately
absent from the parity assertions. Real SQX writes ``<Setups>`` and
``<OutOfSample>`` there; the typed names are a QuantLab convention with no
verified SQX export, which is exactly why ``DataRangeParts.raw_xml``
exists. Asserting parity against them would assert something no evidence
supports.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from quantlab.cfx.models import AdvancedRankingCondition, ColumnValue, DataRangeParts
from quantlab.cfx.patcher import build_conditions_xml
from quantlab.cfx.reader import CfxReader
from quantlab.phase4.templates import CfxTemplateBuilder

FIXTURE = Path(__file__).resolve().parents[1] / "cfx" / "fixtures" / "retester-advanced-rankings.cfx"


def _sqx_rankings() -> ElementTree.Element:
    """The real SQX ``<Rankings>``, straight out of the fixture."""
    with zipfile.ZipFile(FIXTURE) as zf:
        settings = ElementTree.fromstring(zf.read("Build-Task1.xml"))
    (rankings,) = settings.findall("Rankings")
    return rankings


def _sqx_condition_attributes() -> set[str]:
    """Every attribute name SQX writes on a ``<Condition>``."""
    names: set[str] = set()
    for condition in _sqx_rankings().findall("Conditions/Condition"):
        names.update(condition.attrib)
    return names


def _sqx_column_attributes() -> set[str]:
    """Every attribute name SQX writes on a ``<Column-Value>``."""
    names: set[str] = set()
    for column in _sqx_rankings().findall(
        "Conditions/Condition/Left-Side/Column-Value"
    ):
        names.update(column.attrib)
    return names


def _emitted_root(**kwargs) -> ElementTree.Element:
    """Build a real Retester CFX and return its task XML."""
    cfx_bytes = CfxTemplateBuilder.build_retester_cfx(
        strategy_id="golden_retest", databanks=["EURUSD_H1"], **kwargs
    )
    with zipfile.ZipFile(io.BytesIO(cfx_bytes)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("Retester-Task1.xml"))
        return ElementTree.fromstring(zf.read(name))


def _emitted_column_attributes(**kwargs) -> set[str]:
    (column,) = _emitted_root(**kwargs).findall("Rankings/Conditions/Condition/Column-Value")
    return set(column.attrib)


def _emitted_condition(**kwargs) -> ElementTree.Element:
    (condition,) = _emitted_root(**kwargs).findall("Rankings/Conditions/Condition")
    return condition


def _emitted_condition_attributes(**kwargs) -> set[str]:
    return set(_emitted_condition(**kwargs).attrib)


def _sqx_all_attribute_names() -> set[str]:
    """Every attribute name SQX writes anywhere in the real export.

    A deliberately *global* name set. SQX writes only ``use`` on
    ``<Condition>``, so there is no per-element set to check condition-level
    names against, and deriving one from the renderer would make the
    comparison tautological: renaming an attribute would change both sides
    and the test would pass. The export itself is the only independent
    record of which names SQX understands.
    """
    with zipfile.ZipFile(FIXTURE) as zf:
        settings = ElementTree.fromstring(zf.read("Build-Task1.xml"))
    return {name for element in settings.iter() for name in element.attrib}


def _first_task(path: Path):
    """The typed task of an archive.

    ``CfxArchive.config`` is a ``CfxConfig`` for a single-task archive and a
    ``CfxProject`` for a multi-file one, so it is not a uniform accessor.
    ``task_files`` is: both the phase4 emission and the real fixture arrive
    here as ``dict[str, TaskModel]``.
    """
    return next(iter(CfxReader.read(path).task_files.values()))


def _condition_defaults() -> dict[str, str]:
    """A default ``<Condition>`` as attribute name -> XML value.

    Derived from the renderer itself rather than restated here, so the
    assertion below cannot drift away from what is actually emitted.
    """
    rendered = build_conditions_xml([AdvancedRankingCondition()])
    (element,) = ElementTree.fromstring(rendered).findall("Condition")
    return dict(element.attrib)


def _profit_factor_filter() -> AdvancedRankingCondition:
    """The filter the real SQX Retester ranks on, reproduced in the DSL shape."""
    return AdvancedRankingCondition(
        column_values=[
            ColumnValue(column="ProfitFactor", format="Decimal2", class_="ProfitFactor")
        ]
    )


class TestAttributeParityWithRealSqx:
    def test_column_value_attributes_equal_sqx_exactly(self) -> None:
        """GIVEN the real SQX ``<Column-Value>`` attribute set
        WHEN phase4 emits a ranking filter
        THEN the emitted names are identical — none invented, none dropped.
        """
        emitted = _emitted_column_attributes(
            advanced_ranking_filters=[_profit_factor_filter()]
        )

        assert emitted == _sqx_column_attributes()

    def test_condition_attributes_equal_sqx_exactly(self) -> None:
        """SQX writes exactly one attribute on ``<Condition>`` — ``use`` — and
        leaves every other field on the nested ``<Column-Value>``. QuantLab
        emits the whole set, which is allowed but is only *equivalent* while
        each extra attribute carries the value SQX's omission implies.
        """
        emitted = _emitted_condition(advanced_ranking_filters=[_profit_factor_filter()])
        sqx = _sqx_condition_attributes()
        defaults = _condition_defaults()

        assert sqx <= set(emitted.attrib)
        for name, value in emitted.attrib.items():
            if name not in sqx:
                assert value == defaults[name], (
                    f"{name}={value!r} diverges from the default SQX implies "
                    f"({defaults[name]!r})"
                )

    def test_no_condition_attribute_is_renamed_out_from_under_sqx(self) -> None:
        """The name dimension, checked against SQX rather than against the
        renderer.

        SQX writes only ``use`` on ``<Condition>``, so there is no per-element
        oracle and the value comparison above cannot see a rename — renaming
        changes the emitted name *and* the derived default together, and the
        test passes. A name SQX never writes anywhere in the export is
        therefore discarded on import, taking the ranking constraint with it
        and leaving no diagnostic. This asserts the emitted condition names
        are a subset of the names SQX actually uses.
        """
        assert not _emitted_condition_attributes(
            advanced_ranking_filters=[_profit_factor_filter()]
        ) - _sqx_all_attribute_names()

    def test_a_non_default_condition_attribute_is_actually_emitted(self) -> None:
        """The converse guard. If the emission ever stopped writing
        ``<Condition>`` fields the test above would pass vacuously, because
        ``sqx <= set(attrib)`` reduces to ``{"use"}``.
        """
        filter_ = _profit_factor_filter()
        filter_.result_type = "custom"

        assert _emitted_condition_attributes(advanced_ranking_filters=[filter_]) - {
            "use"
        }

    def test_every_emitted_attribute_is_one_sqx_defines(self) -> None:
        """The direction that would actually break a user's retest. An
        attribute SQX does not know is discarded on import, so the ranking
        constraint vanishes with no diagnostic anywhere.
        """
        assert not _emitted_column_attributes(
            advanced_ranking_filters=[_profit_factor_filter()]
        ) - _sqx_column_attributes()

    def test_no_sqx_attribute_is_left_unmodelled(self) -> None:
        """The opposite direction: a real SQX attribute QuantLab cannot
        represent would be dropped by any re-render, so the reader must park
        it rather than silently discard it.
        """
        modelled = {f.alias or name for name, f in ColumnValue.model_fields.items()}

        assert not _sqx_column_attributes() - modelled


class TestChildOrderIsSqxConsistent:
    def test_conditions_follow_the_scalars_sqx_precedes_them_with(self) -> None:
        """SQX orders ``<Rankings>`` children MaxStrategies, FitnessCriteria,
        ConditionsType, **Conditions**, AutomaticDismissal, StopCondition —
        ``<Conditions>`` is never first. A block placed ahead of the scalars
        would be the one ordering SQX never emits.
        """
        (rankings,) = _emitted_root(
            advanced_ranking_filters=[_profit_factor_filter()]
        ).findall("Rankings")

        tags = [child.tag for child in rankings]
        assert tags.index("Conditions") > 0
        assert tags[-1] == "Conditions"

    def test_a_single_rankings_element_is_emitted(self) -> None:
        root = _emitted_root(advanced_ranking_filters=[_profit_factor_filter()])

        assert len(root.findall("Rankings")) == 1


class TestCrossOracleEquivalence:
    def test_emission_reads_back_identically_to_the_real_sqx_export(
        self, tmp_path: Path
    ) -> None:
        """The same reader parses both artifacts. If the phase4 emission and
        the real SQX export of the same filter land on different typed models,
        then QuantLab does not write what SQX writes, and no amount of
        string-level agreement on our own fixtures would have shown it.
        """
        emitted = tmp_path / "emitted.cfx"
        emitted.write_bytes(
            CfxTemplateBuilder.build_retester_cfx(
                strategy_id="golden_retest",
                databanks=["EURUSD_H1"],
                advanced_ranking_filters=[_profit_factor_filter()],
            )
        )

        from_emission = _first_task(emitted).advanced_rankings
        from_sqx = _first_task(FIXTURE).advanced_rankings

        assert from_emission is not None and from_sqx is not None
        emitted_condition = from_emission.conditions[0]
        sqx_condition = next(
            c for c in from_sqx.conditions if c.column_values[0].column == "ProfitFactor"
        )

        assert emitted_condition.model_dump(by_alias=True) == (
            sqx_condition.model_dump(by_alias=True)
        )

    def test_data_range_parts_survive_the_reader_writer_cycle(
        self, tmp_path: Path
    ) -> None:
        """Both lanes survive the cycle: the typed sub-ranges come back typed,
        and the flat lane comes back as the bare ``<Setting key= value=/>``
        elements ``build_retester_cfx`` emitted for each databank.
        """
        from quantlab.cfx.writer import CfxWriter

        source = tmp_path / "emitted.cfx"
        source.write_bytes(
            CfxTemplateBuilder.build_retester_cfx(
                strategy_id="golden_retest",
                databanks=["EURUSD_H1"],
                advanced_ranking_filters=[_profit_factor_filter()],
                data_range_parts=DataRangeParts(ist="0.15", oos_every="0.25"),
            )
        )
        destination = tmp_path / "roundtripped.cfx"
        CfxWriter.write(CfxReader.read(source), destination)

        parts = CfxReader.read(destination).config.task.data_range_parts
        assert parts is not None
        assert parts.ist == "0.15"
        assert parts.oos_every == "0.25"


class TestUnsetPlaceholdersAreInert:
    def test_no_filters_emits_no_conditions(self) -> None:
        root = _emitted_root()

        assert root.find("Rankings/Conditions") is None

    def test_no_parts_emits_no_typed_data_elements(self) -> None:
        (data,) = _emitted_root().findall("Data")

        assert data.find("IST") is None
        assert data.find("OOSEvery") is None