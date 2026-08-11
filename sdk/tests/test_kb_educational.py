"""RED tests for the SQX KB educational generator (parameter-educational-table spec).

Covers: row-per-parameter table in the REQ-205 shape, empty-KB placeholder,
15-field dataset schema, deterministic byte-identical regeneration, and
template-missing flagging for parameters absent from ``tpl_build.xml``.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from quantlab.knowledge.kb.educational import (
    EducationalRecord,
    TPL_KEY_MAP,
    build_educational_dataset,
    build_educational_table,
    parse_tpl_build,
)
from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.teaching import TABLE_HEADERS

FIXTURE_TPL = Path(__file__).parent / "fixtures" / "tpl_build_mini.xml"


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


def make_param(
    name: str,
    *,
    tab: str = "Trading options",
    section: str = "Trading rules",
    status: str = "verified",
    sqx_name: str | None = None,
    evidence_ref: str | None = "Configs/example.cfx",
) -> KbParameter:
    """Build a minimal valid KbParameter for dataset/table tests."""
    return KbParameter(
        name=name,
        sqx_name=sqx_name or name,
        tab=tab,  # type: ignore[arg-type]
        section=section,
        type="Integer",
        default=10,
        range="1-100",
        what_it_does=f"{name} controls a trading behavior",
        how_it_works_in_sqx=f"{name} is applied to the builder",
        quant_trading_role="Tuning this changes risk/reward",
        status=status,  # type: ignore[arg-type]
        evidence_ref=evidence_ref,
    )


@pytest.fixture
def tpl() -> Path:
    """The committed tpl_build_mini.xml fixture (T-2.2, AD-9 drift-proof)."""
    return FIXTURE_TPL


@pytest.fixture
def params() -> list[KbParameter]:
    """Two seeded params: one template-backed, one not."""
    return [
        make_param("Maximum Trades Per Day", sqx_name="MaximumTradesPerDay"),
        make_param("Custom Doc Only", sqx_name="CustomDocOnly"),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# T-2.1 RED — table generation
# ──────────────────────────────────────────────────────────────────────────────


class TestTableGeneration:
    def _records(self, params: list[KbParameter]) -> list[EducationalRecord]:
        return build_educational_dataset(params, tpl={}, tpl_key_map={})

    def test_req205_headers(self, params: list[KbParameter]) -> None:
        table = build_educational_table(self._records(params))
        assert all(header in table for header in TABLE_HEADERS)

    def test_one_row_per_parameter(self, params: list[KbParameter]) -> None:
        table = build_educational_table(self._records(params))
        for param in params:
            assert param.name in table

    def test_empty_kb_yields_placeholder_not_error(self) -> None:
        table = build_educational_table([])
        assert "No KB parameters to teach." in table

    def test_template_values_drive_chosen_config_cell(self, tpl: Path, params: list[KbParameter]) -> None:
        tpl_data = parse_tpl_build(tpl)
        records = build_educational_dataset(params, tpl=tpl_data, tpl_key_map=TPL_KEY_MAP)
        record = next(r for r in records if r.name == "Maximum Trades Per Day")
        # Template has MaximumTradesPerDay=3; chosen config must reflect it.
        assert "3" in (record.chosen_config or "")
        assert record.template_status == "matched"

    def test_absent_parameter_flagged_template_missing(self, tpl: Path, params: list[KbParameter]) -> None:
        tpl_data = parse_tpl_build(tpl)
        records = build_educational_dataset(params, tpl=tpl_data, tpl_key_map=TPL_KEY_MAP)
        record = next(r for r in records if r.name == "Custom Doc Only")
        assert record.template_status == "template-missing"
        assert record.status == "verified"  # KB status retained


# ──────────────────────────────────────────────────────────────────────────────
# T-2.1 RED — shared dataset (15-field schema)
# ──────────────────────────────────────────────────────────────────────────────


class TestSharedDataset:
    REQUIRED_FIELDS = {
        "name",
        "sqx_name",
        "tab",
        "section",
        "type",
        "default",
        "range",
        "what_it_does",
        "how_it_works_in_sqx",
        "quant_trading_role",
        "small_account_recommendation",
        "why_choose",
        "when_choose",
        "status",
        "evidence_ref",
    }

    def test_dataset_emitted_per_parameter(self, tpl: Path, params: list[KbParameter]) -> None:
        tpl_data = parse_tpl_build(tpl)
        records = build_educational_dataset(params, tpl=tpl_data, tpl_key_map=TPL_KEY_MAP)
        assert len(records) == len(params)

    def test_dataset_is_schema_loadable(self, tpl: Path, params: list[KbParameter]) -> None:
        tpl_data = parse_tpl_build(tpl)
        records = build_educational_dataset(params, tpl=tpl_data, tpl_key_map=TPL_KEY_MAP)
        for record in records:
            dumped = record.model_dump()
            for field in self.REQUIRED_FIELDS:
                assert field in dumped, f"missing field {field} in {record.name}"
        # Re-parse one record from its dumped form to prove schema stability.
        reparsed = EducationalRecord.model_validate(records[0].model_dump())
        assert reparsed.name == records[0].name

    def test_no_required_field_empty_for_verified(self, tpl: Path, params: list[KbParameter]) -> None:
        tpl_data = parse_tpl_build(tpl)
        records = build_educational_dataset(params, tpl=tpl_data, tpl_key_map=TPL_KEY_MAP)
        for record in records:
            dumped = record.model_dump()
            for field in ("name", "sqx_name", "tab", "section", "what_it_does"):
                assert dumped.get(field), f"empty required field {field} in {record.name}"


# ──────────────────────────────────────────────────────────────────────────────
# T-2.1 RED — deterministic regeneration
# ──────────────────────────────────────────────────────────────────────────────


class TestDeterministicRegeneration:
    def test_rerun_produces_identical_output(self, tpl: Path, params: list[KbParameter]) -> None:
        tpl_data = parse_tpl_build(tpl)
        first = build_educational_table(build_educational_dataset(params, tpl=tpl_data, tpl_key_map=TPL_KEY_MAP))
        second = build_educational_table(build_educational_dataset(params, tpl=tpl_data, tpl_key_map=TPL_KEY_MAP))
        assert first == second

    def test_parse_tpl_deterministic(self, tpl: Path) -> None:
        assert parse_tpl_build(tpl) == parse_tpl_build(tpl)

    def test_no_input_mutation(self, tpl: Path, params: list[KbParameter]) -> None:
        before = [p.model_dump() for p in params]
        tpl_data = parse_tpl_build(tpl)
        build_educational_dataset(params, tpl=tpl_data, tpl_key_map=TPL_KEY_MAP)
        after = [p.model_dump() for p in params]
        assert before == after


# ──────────────────────────────────────────────────────────────────────────────
# T-2.3 RED — parse_tpl_build + TPL_KEY_MAP
# ──────────────────────────────────────────────────────────────────────────────


class TestParseTplBuild:
    def test_scalar_builder_tags_collected(self, tpl: Path) -> None:
        data = parse_tpl_build(tpl)
        assert "MaximumTradesPerDay" in data
        assert data["MaximumTradesPerDay"]["default"] == "3"

    def test_param_tags_collected(self, tpl: Path) -> None:
        data = parse_tpl_build(tpl)
        assert "Size" in data
        assert data["Size"]["className"] == "FixedSize"

    def test_unmapped_returns_empty(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.xml"
        empty.write_text("<Task><Settings /></Task>", encoding="utf-8")
        assert parse_tpl_build(empty) == {}

    def test_tpl_key_map_shape(self) -> None:
        assert isinstance(TPL_KEY_MAP, dict)
        assert len(TPL_KEY_MAP) > 0


# ──────────────────────────────────────────────────────────────────────────────
# T-2.2 RED — committed drift-proof fixtures + conftest.make_cfx()
# ──────────────────────────────────────────────────────────────────────────────

CONFIG_FIXTURE = Path(__file__).parent / "fixtures" / "config_mini.xml"


class TestCommittedFixtures:
    """T-2.2: committed mini fixtures parses (AD-9, drift-proof evidence)."""

    def test_committed_tpl_fixture_parses(self) -> None:
        data = parse_tpl_build(FIXTURE_TPL)
        assert data["MaximumTradesPerDay"]["default"] == "3"
        assert data["Size"]["className"] == "FixedSize"

    def test_committed_config_fixture_is_well_formed_xml(self) -> None:
        import xml.etree.ElementTree as ET

        tree = ET.parse(CONFIG_FIXTURE)
        root = tree.getroot()
        assert root.tag  # non-empty root tag proves a real document

    def test_make_cfx_builds_parseable_zip(
        self, tmp_path: Path, make_cfx: object
    ) -> None:
        import zipfile
        import xml.etree.ElementTree as ET

        cfx_path = make_cfx(tmp_path, name="config_mini.cfx")
        assert cfx_path.suffix == ".cfx"
        assert zipfile.is_zipfile(cfx_path)
        with zipfile.ZipFile(cfx_path) as zf:
            member = next(name for name in zf.namelist() if name.endswith(".xml"))
            assert ET.fromstring(zf.read(member)).tag  # member XML is well-formed


# ──────────────────────────────────────────────────────────────────────────────
# T-2.7 RED — educational dataset loader (lazy, silent fallback)
# ──────────────────────────────────────────────────────────────────────────────


def _dataset_record(
    name: str,
    tab: str,
    *,
    what_it_does: str = "controls a trading behavior",
    quant_role: str = "Tuning this changes risk/reward",
) -> dict[str, object]:
    """A minimal well-formed educational dataset record (dict shape = YAML)."""
    return {
        "name": name,
        "sqx_name": name,
        "tab": tab,
        "section": "Trading rules",
        "type": "Integer",
        "default": 5,
        "range": "1-100",
        "what_it_does": what_it_does,
        "how_it_works_in_sqx": "applied to the builder",
        "quant_trading_role": quant_role,
        "small_account_recommendation": None,
        "why_choose": None,
        "when_choose": None,
        "status": "verified",
        "evidence_ref": "Configs/example.cfx",
        "chosen_config": "5",
        "template_status": "matched",
    }


class TestEducationalDatasetLoader:
    """T-2.7: load_educational_dataset reads the lake YAML at runtime."""

    def test_loads_dataset_yaml_from_lake(self, tmp_path: Path) -> None:
        from quantlab.knowledge.kb.educational import load_educational_dataset

        import yaml

        edu = (
            tmp_path
            / "structured"
            / "sqx-kb"
            / "144.2953"
            / "educational"
        )
        edu.mkdir(parents=True)
        (edu / "educational-dataset.yaml").write_text(
            yaml.safe_dump([_dataset_record("Maximum Trades Per Day", "Trading options")], sort_keys=False),
            encoding="utf-8",
        )
        loaded = load_educational_dataset(tmp_path, sqx_version="144.2953")
        assert len(loaded) == 1
        assert loaded[0].name == "Maximum Trades Per Day"
        assert loaded[0].tab == "Trading options"

    def test_missing_dataset_yaml_returns_empty(self, tmp_path: Path) -> None:
        from quantlab.knowledge.kb.educational import load_educational_dataset

        assert load_educational_dataset(tmp_path, sqx_version="144.2953") == []
