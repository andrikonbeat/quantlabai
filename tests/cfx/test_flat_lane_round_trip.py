"""Round-trip coverage for the flat lane of ``SettingsSection`` (REQ-FLAT-1..6).

``fix-flat-lane-settings-projection`` inverted the flat-lane codec: the reader
flattens a section's *children* with an empty prefix, one shared predicate
decides lane membership for both ``<Data>`` lanes, and the writer groups
``Tag@attr`` keys back into one element per tag. The migration proved that
against the expectations it invalidated; this file pins the **behaviour**, so a
later codec edit fails here instead of surfacing as a corrupted retester CFX.

Every test drives the real ``CfxReader``/``CfxWriter`` pair over a real archive
on disk: the observable is the XML a campaign would load, never internal shape.
"""

import inspect
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from quantlab.cfx import reader
from quantlab.cfx.models import (
    AddTimeframeInstruction,
    BuildTask,
    CfxArchive,
    CfxConfig,
    SettingsSection,
)
from quantlab.cfx.patcher import CfxPatcher
from quantlab.cfx.reader import CfxReader
from quantlab.cfx.writer import CfxWriter
from quantlab.phase4.templates import CfxTemplateBuilder

CONFIG_VERSION = "141.2219"
TASK_FILE = "Build-Task1.xml"
RETESTER_TASK_FILE = "Retester-Task1.xml"

#: The REQ-FLAT-3 five-key ``<Data>``: two ``Symbol`` attributes plus timeframe
#: and the date range. Under the pre-inversion codec these four children
#: collapsed to one ``Setting@key``/``Setting@value`` pair — destroying the
#: symbol, the timeframe and both dates.
FIVE_KEY_XML = (
    '<Symbol symbol="EURUSD" name="Euro/USD" /><Timeframe1 value="H1" />'
    '<FromDate value="2015.01.01" /><ToDate value="2024.12.31" />'
)
FIVE_KEY_SETTINGS = {
    "Symbol@symbol": "EURUSD",
    "Symbol@name": "Euro/USD",
    "Timeframe1@value": "H1",
    "FromDate@value": "2015.01.01",
    "ToDate@value": "2024.12.31",
}


def _archive(task: BuildTask, name: str = TASK_FILE) -> CfxArchive:
    return CfxArchive(
        config=CfxConfig(task=task, schema_version=CONFIG_VERSION),
        task_files={name: task},
    )


def _data_task(settings: dict[str, str]) -> BuildTask:
    task = BuildTask()
    task.data = SettingsSection(name="Data", settings=settings)
    return task


def _settings_archive(task_xml: str, name: str = TASK_FILE) -> bytes:
    """Wrap a ``<Settings>`` document in the single-task CFX ZIP shape."""
    config = f'<Task type="Build" version="{CONFIG_VERSION}" taskXMLFile="{name}"/>'
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config.xml", config)
        zf.writestr(name, task_xml)
    return buf.getvalue()


def _read(task_xml: str, tmp_path: Path, name: str = TASK_FILE) -> BuildTask:
    """Read a single-task CFX from disk and return its BuildTask."""
    cfx = tmp_path / "probe.cfx"
    cfx.write_bytes(_settings_archive(task_xml, name))
    return CfxReader.read(cfx).config.task


def _task_entry(cfx: Path, name: str = TASK_FILE) -> str:
    with zipfile.ZipFile(cfx) as zf:
        return zf.read(name).decode("utf-8")


def _task_xml(task: BuildTask, name: str = TASK_FILE) -> ElementTree.Element:
    """Serialise a BuildTask through the real writer; return its parsed root."""
    raw = CfxWriter.to_bytes(_archive(task, name))
    with zipfile.ZipFile(BytesIO(raw), "r") as zf:
        return ElementTree.fromstring(zf.read(name).decode("utf-8"))


def _cycle(task_xml: str, dest: Path) -> str:
    """Write ``task_xml`` as a CFX, read it back, write again; return pass two."""
    task = _read(task_xml, dest.parent)
    CfxWriter.write(_archive(task), dest)
    CfxWriter.write(CfxReader.read(dest), dest)
    return _task_entry(dest)


def _cycles(task_xml: str, workdir: Path, cycles: int) -> list[str]:
    """Feed every write back through the reader; return each pass's task XML."""
    passes: list[str] = []
    current = task_xml
    for index in range(cycles):
        current = _cycle(current, workdir / f"pass{index}.cfx")
        passes.append(current)
    return passes


def _data(root: ElementTree.Element) -> ElementTree.Element:
    (data,) = [c for c in root if c.tag == "Data"]
    return data


def _data_signature(task_xml: str) -> list[tuple[str, tuple[tuple[str, str], ...]]]:
    """The ``<Data>`` children as ``(tag, sorted attributes)``, order preserved."""
    data = _data(ElementTree.fromstring(task_xml))
    return [(c.tag, tuple(sorted(c.attrib.items()))) for c in data]


def _retester_cfx(tmp_path: Path) -> Path:
    """Write the template's two-databank Retester CFX and return its path."""
    cfx = tmp_path / "retester.cfx"
    cfx.write_bytes(
        CfxTemplateBuilder.build_retester_cfx(
            strategy_id="strat-1", databanks=["EURUSD_H1", "GBPUSD_H1"]
        )
    )
    return cfx


# ── REQ-FLAT-1 / REQ-FLAT-3: the flat lane is a bijection ──────────────


class TestFlatLaneRoundTrip:
    def test_five_key_data_survives_a_full_round_trip(self, tmp_path: Path) -> None:
        """REQ-FLAT-3 "Five-key Data section survives one cycle". Previously the
        five keys came back as one ``Setting@key``/``Setting@value`` pair: every
        flat entry had been re-emitted as a ``<Setting>``, so the dict overwrite
        destroyed the rest."""
        source = f"<Settings><Data>{FIVE_KEY_XML}</Data></Settings>"

        assert _read(source, tmp_path).data.settings == FIVE_KEY_SETTINGS

        rewritten = _cycle(source, tmp_path / "five.cfx")

        assert _read(rewritten, tmp_path).data.settings == FIVE_KEY_SETTINGS
        assert _data_signature(rewritten) == [
            ("Symbol", (("name", "Euro/USD"), ("symbol", "EURUSD"))),
            ("Timeframe1", (("value", "H1"),)),
            ("FromDate", (("value", "2015.01.01"),)),
            ("ToDate", (("value", "2024.12.31"),)),
        ]

    def test_five_key_data_survives_an_in_place_rewrite(
        self, tmp_path: Path
    ) -> None:
        """REQ-FLAT-3 "Data section survives an in-place rewrite" — the in-place
        rewrites a campaign performs must not disturb a ``<RetesterData>`` sibling
        sharing the same ``<Settings>`` root."""
        sibling = '<RetesterData><MonteCarloRuns value="100" /></RetesterData>'
        source = f"<Settings><Data>{FIVE_KEY_XML}</Data>{sibling}</Settings>"

        task = _read(_cycle(source, tmp_path / "in_place.cfx"), tmp_path)

        assert task.data.settings == FIVE_KEY_SETTINGS
        assert task.retester_data is not None
        assert task.retester_data.raw_xml == sibling

    def test_no_section_tag_pollutes_a_non_data_flat_section(
        self, tmp_path: Path
    ) -> None:
        """REQ-FLAT-1 "No section-prefix pollution": the section element used to be the
        flatten root, so every key carried the section tag and a producer's
        ``Tag@attr`` key was unmatchable."""
        task = _read(
            "<Settings><WhatToBuild>"
            '<Setting key="BuildType@value" value="genetic" />'
            '<StrategyType type="simple" />'
            "</WhatToBuild>"
            '<Options><MaxStrategiesCount value="1000" /></Options>'
            "</Settings>",
            tmp_path,
        )

        assert task.what_to_build.settings == {
            "BuildType@value": "genetic",
            "StrategyType@type": "simple",
        }
        assert task.options.settings == {"MaxStrategiesCount@value": "1000"}
        assert all("WhatToBuild." not in k for k in task.what_to_build.settings)

    def test_a_producer_timeframe_key_is_findable_after_a_read(
        self, tmp_path: Path
    ) -> None:
        """REQ-FLAT-1 "Producer keys become findable after a read": the patcher
        numbers a new timeframe from ``len(existing_keys) + 1``, so a
        section-prefixed key made the scan match nothing."""
        written = tmp_path / "patched.cfx"
        CfxWriter.write(_archive(_data_task({"Timeframe1@value": "H1"})), written)

        patcher = CfxPatcher(CfxReader.read(written))
        patcher.apply([AddTimeframeInstruction(timeframe="M15")])

        assert patcher.task.data.settings == {
            "Timeframe1@value": "H1",
            "Timeframe2@value": "M15",
        }


# ── REQ-FLAT-2: Setting pair coalescing ───────────────────────────────


class TestSettingPairCoalescing:
    def test_legacy_pair_coalesces_into_one_setting_element(self) -> None:
        """REQ-FLAT-2 "Pair coalesces into a single element" — the literal key names an
        un-inverted reader used to emit, rejoined by the writer."""
        legacy = {"Setting@key": "EURUSD_H1", "Setting@value": "true"}

        data = _data(_task_xml(_data_task(legacy)))

        assert [c.tag for c in data] == ["Setting"]
        (setting,) = data
        assert setting.get("key") == "EURUSD_H1"
        assert setting.get("value") == "true"

    def test_the_reader_never_produces_setting_key_or_value_keys(
        self, tmp_path: Path
    ) -> None:
        """The tolerance is **write-side only**: a real ``<Setting>`` re-read must land
        as one bare entry, or every cycle re-mangles the file."""
        task = _read(
            '<Settings><Data><Setting key="EURUSD_H1" value="true" />'
            f"{FIVE_KEY_XML}</Data>"
            '<WhatToBuild><Setting key="BuildType@value" value="genetic" />'
            "</WhatToBuild></Settings>",
            tmp_path,
        )

        assert task.data.settings == {"EURUSD_H1": "true", **FIVE_KEY_SETTINGS}
        assert task.what_to_build.settings == {"BuildType@value": "genetic"}
        for section in (task.data, task.what_to_build):
            assert "Setting@key" not in section.settings
            assert "Setting@value" not in section.settings

    def test_a_real_setting_element_is_byte_stable_over_four_cycles(
        self, tmp_path: Path
    ) -> None:
        """REQ-FLAT-2 "Coalesced output is byte-stable over four cycles"."""
        passes = _cycles(
            "<Settings><Data>"
            '<Setting key="EURUSD_H1" value="true" />'
            '<Setting key="GBPUSD_H1" value="true" />'
            "</Data></Settings>",
            tmp_path,
            4,
        )

        assert len(passes) == 4
        assert len(set(passes)) == 1

    def test_the_data_signature_is_idempotent_across_four_cycles(
        self, tmp_path: Path
    ) -> None:
        """REQ-FLAT-2 "Second cycle" guard: no growth and no duplication over four
        cycles. Growth is the tell that both ``<Data>`` lanes claimed the same
        child, so the assertion spans the flat elements plus the typed ``<IST>``
        and ``<Setups>`` siblings."""
        signatures = [
            _data_signature(p)
            for p in _cycles(
                "<Settings><Data>"
                f"{FIVE_KEY_XML}"
                '<IST value="0.5" />'
                '<Setups><Setup dateFrom="2003.5.5" /></Setups>'
                "</Data>"
                '<RetesterData><MonteCarloRuns value="100" /></RetesterData>'
                "</Settings>",
                tmp_path,
                4,
            )
        ]

        assert len(signatures[0]) == 6
        assert signatures == [signatures[0]] * 4


# ── REQ-FLAT-5 / REQ-FLAT-6: emitted dialect ──────────────────────────


class TestEmittedDialect:
    def test_bare_keys_emit_setting_elements_that_stay_addressable(
        self, tmp_path: Path
    ) -> None:
        """REQ-FLAT-6 "Bare keys keep Setting" + "Setting elements are addressable
        by key" — the dialect the retester template depends on."""
        cfx = _retester_cfx(tmp_path)

        data = _data(ElementTree.fromstring(_task_entry(cfx, RETESTER_TASK_FILE)))

        assert [c.tag for c in data] == ["Setting", "Setting"]
        assert data.find("Setting[@key='EURUSD_H1']").get("value") == "true"
        assert data.find("Setting[@key='GBPUSD_H1']").get("value") == "true"

    def test_two_databanks_survive_a_read_write_cycle(self, tmp_path: Path) -> None:
        """REQ-FLAT-5 "Two databanks survive one cycle": previously ``GBPUSD_H1``
        overwrote ``EURUSD_H1``, so a retester template silently lost one of
        its two requested databanks."""
        cfx = _retester_cfx(tmp_path)

        archive = CfxReader.read(cfx)
        CfxWriter.write(archive, cfx)

        data = _data(ElementTree.fromstring(_task_entry(cfx, RETESTER_TASK_FILE)))

        assert archive.config.task.data.settings == {
            "EURUSD_H1": "true",
            "GBPUSD_H1": "true",
        }
        assert [c.tag for c in data] == ["Setting", "Setting"]
        assert data.find("Setting[@key='EURUSD_H1']").get("value") == "true"
        assert data.find("Setting[@key='GBPUSD_H1']").get("value") == "true"

    def test_a_tagged_key_is_never_emitted_as_a_setting_element(self) -> None:
        """REQ-FLAT-6: only ``Tag@attr`` keys change form, and they change to
        their own grouped element — never back to ``<Setting>``."""
        data = _data(
            _task_xml(
                _data_task(
                    {
                        "Symbol@symbol": "EURUSD",
                        "Symbol@name": "Euro/USD",
                        "Timeframe1@value": "H1",
                    }
                )
            )
        )

        assert [c.tag for c in data] == ["Symbol", "Timeframe1"]
        assert [c.tag for c in data if c.tag == "Setting"] == []
        assert data.find("Symbol").get("name") == "Euro/USD"


class TestWriterEdgeCases:
    def test_a_key_with_an_empty_tag_part_is_treated_as_a_bare_key(
        self, tmp_path: Path
    ) -> None:
        """A key whose ``@`` partitions to an empty tag must not become an element
        with no name — that is not well-formed XML, so the file would be
        unreadable on the next cycle. Unreachable from any producer today."""
        data = _data(_task_xml(_data_task({"@value": "orphan"})))

        assert [c.tag for c in data] == ["Setting"]
        (setting,) = data
        assert setting.get("key") == "@value"
        assert setting.get("value") == "orphan"

        rewritten = _cycle(
            '<Settings><Data><Setting key="@value" value="orphan" /></Data></Settings>',
            tmp_path / "orphan.cfx",
        )

        assert _read(rewritten, tmp_path).data.settings == {"@value": "orphan"}


# ── REQ-FLAT-4: one predicate, two lanes ──────────────────────────────


class TestFlatLanePredicateIsShared:
    def test_the_shared_predicate_decides_both_halves_of_the_test(self) -> None:
        """The rule the shared predicate encodes, at unit level: a leaf is
        admitted; a claimed tag and a nested subtree are not."""
        payload = ElementTree.fromstring(
            '<Data><Symbol symbol="EURUSD" /><IST value="0.5" />'
            '<Setups><Setup dateFrom="2003.5.5" /></Setups></Data>'
        )

        admitted = [
            c.tag
            for c in payload
            if reader._is_flat_lane_child(c, reader._DATA_OWNED_TAGS)
        ]

        assert admitted == ["Symbol"]

    def test_both_reader_lanes_call_it_and_neither_reimplements_it(self) -> None:
        """REQ-FLAT-4 "One shared predicate serves both ``<Data>`` lanes". A
        second, drifting copy of the rule reintroduces lane duplication."""
        admit = inspect.getsource(reader._parse_settings_element)
        strip = inspect.getsource(reader._parse_data_range_parts)

        assert "_is_flat_lane_child(" in admit
        assert "_is_flat_lane_child(" in strip
        for source in (admit, strip):
            assert "len(child) == 0" not in source
            assert "child.tag not in" not in source
