"""Mixed simple + advanced ranking compatibility (task 4.3).

The spec requires that a project carrying both the pre-existing flat ranking
path (``AddRankingConditionInstruction`` → ``Criterion*`` settings) and the new
nested path (``AddAdvancedRankingConditionInstruction`` → ``<Conditions>``)
produces **both** blocks. ``design.md`` also forbids changing the simple path,
so these tests exist to prove the two lanes coexist rather than to reshape
either one.

Three things are pinned here, and each one was a live defect or a mutation
survivor before it had a test:

1. **Neither lane may silently vanish.** The flat applier is guarded by
   ``if self._task.rankings``, so on a task that never seeded that lane the
   simple condition was dropped without a word. The phase4 retester template
   is exactly such a task, so the mixed scenario lost the simple half.
2. **The merge stays lossless in both directions.** ``<Rankings>`` must remain a
   single element carrying the advanced block *and* the flat settings.
3. **The merge stays stable.** Emitting both lanes and reading them back must
   converge; growth means the two lanes captured the same element.

Idempotence is asserted on the ``<Rankings>``/``<Data>`` subtrees rather than on
the whole file so a divergence is attributed to the lane under test rather than
to an unrelated section. Building these tasks without an ``<Options>`` section
keeps that lane out of the comparison entirely.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from quantlab.cfx import (
    BuildTask,
    CfxArchive,
    CfxConfig,
    CfxPatcher,
    CfxReader,
    SettingsSection,
)
from quantlab.cfx.models import (
    AdvancedRankingCondition,
    ColumnValue,
    DataRangeParts,
)
from quantlab.cfx.writer import CfxWriter


def _archive(**task_fields) -> CfxArchive:
    """A minimal archive. No ``<Options>`` section, for the reason above."""
    return CfxArchive(
        config=CfxConfig(task=BuildTask(**task_fields), schema_version="141.2219")
    )


def _pf_column() -> AdvancedRankingCondition:
    return AdvancedRankingCondition(
        use=True,
        column_values=[
            ColumnValue(column="ProfitFactor", format="Decimal2", class_="ProfitFactor")
        ],
    )


def _write(archive: CfxArchive, tmp_path: Path, name: str) -> Path:
    out = tmp_path / name
    CfxWriter.write(archive, out)
    return out


def _settings(cfx: Path) -> ElementTree.Element:
    with zipfile.ZipFile(cfx) as zf:
        return ElementTree.fromstring(zf.read("Build-Task1.xml"))


def _round_trip(source: Path, dest: Path) -> Path:
    """Read ``source``, write it, then read and write once more."""
    CfxWriter.write(CfxReader.read(source), dest)
    CfxWriter.write(CfxReader.read(dest), dest)
    return dest


class TestNeitherLaneIsDropped:
    def test_simple_condition_survives_next_to_an_advanced_one(
        self, tmp_path: Path
    ) -> None:
        """GIVEN a task that never seeded the flat lane
        WHEN a simple and an advanced ranking condition are both added
        THEN both are emitted. The flat applier used to be guarded by
        ``if self._task.rankings``, so on the phase4 retester template — which
        seeds only the complex lane — the simple half was discarded silently.
        """
        archive = _archive()
        patcher = CfxPatcher(archive)
        patcher.add_ranking_condition("ProfitFactor", ">", 1.3)
        patcher.add_advanced_ranking_condition(_pf_column())

        root = _settings(_write(archive, tmp_path, "mixed.cfx")).find("Rankings")

        (criterion,) = root.findall("Criterion1")
        assert criterion.get("metric") == "ProfitFactor"
        assert criterion.get("operator") == ">"
        assert criterion.get("value") == "1.3"
        assert root.find("Conditions/Condition/Column-Value") is not None

    def test_simple_condition_is_kept_when_the_flat_lane_exists(
        self, tmp_path: Path
    ) -> None:
        """Triangulation: the pre-seeded case already worked, so this pins that
        the fix did not regress it.
        """
        archive = _archive(rankings=SettingsSection(name="Rankings", settings={}))
        patcher = CfxPatcher(archive)
        patcher.add_ranking_condition("Sharpe", ">", 2.0)
        patcher.add_advanced_ranking_condition(_pf_column())

        root = _settings(_write(archive, tmp_path, "mixed2.cfx")).find("Rankings")

        assert root.find("Criterion1").get("metric") == "Sharpe"
        assert root.find("Conditions") is not None


class TestMergeIsLossless:
    def test_both_lanes_share_one_rankings_element(self, tmp_path: Path) -> None:
        """Two sibling ``<Rankings>`` elements are what a non-merging writer
        produces; the SQX ``<Settings>`` schema admits one.
        """
        archive = _archive(rankings=SettingsSection(name="Rankings", settings={}))
        patcher = CfxPatcher(archive)
        patcher.add_ranking_condition("ProfitFactor", ">", 1.3)
        patcher.add_advanced_ranking_condition(_pf_column())

        settings = _settings(_write(archive, tmp_path, "one.cfx"))

        assert len(settings.findall("Rankings")) == 1

    def test_flat_settings_land_after_the_verified_native_prefix(
        self, tmp_path: Path
    ) -> None:
        """Pin *where* the flat lane goes, because there is no native answer.

SQX never writes a flat criterion inside ``<Rankings>``: both real
        144/2953 exports (``Retester`` and ``Builder``) contain zero
        ``<Criterion*>`` elements and zero ``Criterion*@`` keys. So the flat
        lane is a QuantLab extension with **no SQX-defined position**, and
        "native order" is not defined for it.

        What *is* verified is the block it is merged into. SQX orders
        ``<Rankings>`` children as ``MaxStrategies``, ``FitnessCriteria``,
        ``ConditionsType``, ``Conditions``, ``AutomaticDismissal``,
        ``<StopCondition>`` — so the merge must leave that verified prefix exactly
        as it found it and append the extension. Inserting the flat lane's
        ``<Criterion1>`` element ahead of ``<Conditions>`` would rewrite the one
        part of the section SQX actually defines.
        """
        archive = _archive(rankings=SettingsSection(name="Rankings", settings={}))
        patcher = CfxPatcher(archive)
        patcher.add_ranking_condition("ProfitFactor", ">", 1.3)
        patcher.add_advanced_ranking_condition(_pf_column())

        root = _settings(_write(archive, tmp_path, "order.cfx")).find("Rankings")

        assert [child.tag for child in root] == [
            "Conditions",
            "Criterion1",
        ]

    def test_advanced_block_keeps_its_full_column_attributes(
        self, tmp_path: Path
    ) -> None:
        """The flat merge appends ``<Criterion1>``; it must not disturb the
        nested block, whose twelve attributes are the actual ranking criteria.
        """
        archive = _archive(rankings=SettingsSection(name="Rankings", settings={}))
        patcher = CfxPatcher(archive)
        patcher.add_ranking_condition("ProfitFactor", ">", 1.3)
        patcher.add_advanced_ranking_condition(_pf_column())

        root = _settings(_write(archive, tmp_path, "attrs.cfx"))
        column = root.find("Rankings/Conditions/Condition/Column-Value")

        assert dict(column.attrib) == {
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
        }

    def test_reread_recovers_the_advanced_lane(self, tmp_path: Path) -> None:
        """The point of the typed lane: a mixed file QuantLab wrote is readable
        back into typed state, so a later agent can reason about the ranking.
        """
        archive = _archive(rankings=SettingsSection(name="Rankings", settings={}))
        patcher = CfxPatcher(archive)
        patcher.add_ranking_condition("ProfitFactor", ">", 1.3)
        patcher.add_advanced_ranking_condition(_pf_column())
        source = _write(archive, tmp_path, "reread.cfx")

        task = CfxReader.read(source).config.task

        assert task.advanced_rankings is not None
        assert [
            c.column_values[0].column for c in task.advanced_rankings.conditions
        ] == ["ProfitFactor"]

    def test_repeated_simple_conditions_get_distinct_indexes(
        self, tmp_path: Path
    ) -> None:
        """Indexing is derived from the existing key prefixes, so a second
        simple condition must land on ``Criterion2`` and not overwrite
        ``Criterion1``.
        """
        archive = _archive(rankings=SettingsSection(name="Rankings", settings={}))
        patcher = CfxPatcher(archive)
        patcher.add_ranking_condition("ProfitFactor", ">", 1.3)
        patcher.add_ranking_condition("Sharpe", ">", 2.0)
        patcher.add_advanced_ranking_condition(_pf_column())

        root = _settings(_write(archive, tmp_path, "two-simple.cfx")).find("Rankings")

        assert root.find("Criterion1").get("metric") == "ProfitFactor"
        assert root.find("Criterion2").get("metric") == "Sharpe"


class TestMergeIsStable:
    def test_rankings_subtree_converges_across_cycles(self, tmp_path: Path) -> None:
        """Read → write → read → write must not grow ``<Rankings>``. A second
        pass that differs means a lane captured content the other lane already
        held.
        """
        archive = _archive(rankings=SettingsSection(name="Rankings", settings={}))
        patcher = CfxPatcher(archive)
        patcher.add_ranking_condition("ProfitFactor", ">", 1.3)
        patcher.add_advanced_ranking_condition(_pf_column())
        first = _round_trip(_write(archive, tmp_path, "p1.cfx"), tmp_path / "p2.cfx")
        second = _round_trip(first, tmp_path / "p3.cfx")

        def _rankings(cfx: Path) -> str:
            return ElementTree.tostring(_settings(cfx).find("Rankings"), encoding="unicode")

        assert _rankings(second) == _rankings(first)

    def test_data_lanes_do_not_duplicate_each_other(self, tmp_path: Path) -> None:
        """``<Data>`` carries the same two lanes. ``set_date_range`` writes flat
        ``<Setting>`` entries and ``set_data_range_parts`` writes typed
        sub-ranges; capturing the same element in both lanes duplicates it on
        the next write.
        """
        archive = _archive(data=SettingsSection(name="Data", settings={}))
        patcher = CfxPatcher(archive)
        patcher.set_date_range("2015.01.01", "2020.12.31")
        patcher.set_data_range_parts(DataRangeParts(ist="0.15", oos_every="0.25"))
        first = _round_trip(_write(archive, tmp_path, "d1.cfx"), tmp_path / "d2.cfx")

        data = _settings(first).find("Data")

        assert len(_settings(first).findall("Data")) == 1
        assert len(data.findall("IST")) == 1
        assert len(data.findall("OOSEvery")) == 1
        # The flat lane contributes exactly its own two entries and does not
        # absorb the typed sub-ranges: `set_date_range` writes
        # `FromDate@value`/`ToDate@value`, which the codec de-flattens back into
        # one `<FromDate>`/`<ToDate>` element each — never a `<Setting>` pair and
        # never a second copy of `<IST>`/`<OOSEvery>`.
        assert len(data.findall("FromDate")) == 1
        assert len(data.findall("ToDate")) == 1
        assert len(data.findall("Setting")) == 0


class TestSimpleOnlyTaskIsUnchanged:
    def test_simple_only_emission_is_byte_identical(self, tmp_path: Path) -> None:
        """``design.md`` forbids changing the simple path. With no advanced
        filter present the output must be exactly what it always was.
        """
        archive = _archive(rankings=SettingsSection(name="Rankings", settings={}))
        patcher = CfxPatcher(archive)
        patcher.add_ranking_condition("ProfitFactor", ">", 1.3)

        root = _settings(_write(archive, tmp_path, "simple.cfx")).find("Rankings")

        assert [c.tag for c in root] == ["Criterion1"]
        assert root.find("Conditions") is None
        assert archive.config.task.rankings_section is None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest_main())


def pytest_main() -> int:
    import pytest

    return pytest.main([__file__, "-q"])