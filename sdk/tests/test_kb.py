"""SQX Parameter KB tests (REQ-201, REQ-202, REQ-203, REQ-206, REQ-207, REQ-208, REQ-502).

The KB is version-isolated: each parameter lives at
``structured/sqx-kb/{sqx_version}/parameters/{tab}/{param}.yaml`` with a
22-field pydantic schema. Parameters are seeded from
``doc_dev/SQX Builder Config.md`` (status ``seeded`` + evidence_ref), doc
gaps become ``needs_review`` (never inventing semantics), and verification
against real configs promotes entries to ``verified``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from quantlab.knowledge.kb.models import (
    KB_TABS,
    SQX_VERSION,
    KbParameter,
    SmallAccountRecommendation,
)
from quantlab.knowledge.kb.seeder import GAP_WHAT_IT_DOES, seed_from_doc
from quantlab.knowledge.kb.store import KbParamNotFoundError, KbStore

# ── Fixture: a small stand-in for doc_dev/SQX Builder Config.md ─────────────
# Contains one distinctive documented parameter per tab plus one explicit gap
# (ATM). Deterministic and CI-safe: never depends on the untracked real doc.

SAMPLE_DOC = """# **SQX Builder Config**

### **What to build**
### **1\\. Configuraci\\u00f3n de Salida y Tipo de Estrategia**
* **Strategy type:** Se ha seleccionado **Simple strategy [default]**.

### **Genetic options**
### **1\\. Genetic options**
* **Max \\# of Generations:** **100**.

### **Data**
### **2\\. Backtest data settings**
* **Timeframe:** **M15**.

### **Trading options**
### **1\\. Trading options**
* **Maximum Trades Per Day:** **0**.
  * Nota: el protocolo recomienda establecerlo en **1** para evitar el
    *overtrading* y comisiones excesivas en una cuenta peque\\u00f1a.

# Building blocks
* **Selecci\\u00f3n:** **188 blocks selected** de 339.

## **Money management**
* **Fixed size**: **Seleccionado**.
* **Order size**: **0.01**.

## **Cross checks (robustness)**
### **1\\. BASIC (FAST)**
* **What If simulations:** 15 simulaciones con 3 condiciones de filtrado.

## **Ranking**
### **2\\. Strategy Quality ranking**
* **Ranking Criterium:** Ret/DD Ratio **Maximize (Weight: 40)**.
* **Profit factor (IST) \\> 1.2**

### "La pesta\\u00f1a ATM claramente SQX indica que es experimental y no se como funciona"
"""


@pytest.fixture()
def sample_doc(tmp_path: Path) -> Path:
    doc = tmp_path / "SQX Builder Config.md"
    doc.write_text(SAMPLE_DOC, encoding="utf-8")
    return doc


def make_kb_dir(tmp_path: Path) -> KbStore:
    store = KbStore(root=tmp_path / "lake")
    store.initialize()
    return store


# ──────────────────────────────────────────────────────────────────────────────
# REQ-201: KB Schema
# ──────────────────────────────────────────────────────────────────────────────


class TestKbParameterModel:
    """REQ-201 schema: 22 fields, tab Literal[8], status enum, pinned version."""

    def _minimal(self, **overrides: object) -> dict:
        base: dict[str, object] = {
            "name": "Maximum Trades Per Day",
            "sqx_name": "Maximum Trades Per Day",
            "tab": "Trading options",
            "section": "1. Trading options",
            "type": "int",
            "default": 0,
            "range": None,
            "what_it_does": "Limits daily trade count; 0 means no limit.",
            "how_it_works_in_sqx": "Builder caps entries per day to the configured value.",
            "quant_trading_role": "Prevents overtrading on small accounts.",
        }
        base.update(overrides)
        return base

    def test_valid_parameter_loads_with_all_required_fields(self) -> None:
        param = KbParameter.model_validate(self._minimal())
        assert param.name == "Maximum Trades Per Day"
        assert param.tab == "Trading options"
        assert param.what_it_does.startswith("Limits daily trade count")

    def test_missing_what_it_does_fails_and_lists_field(self) -> None:
        # REQ-201 scenario: a KB YAML missing what_it_does must fail validation
        # AND name the missing field.
        data = self._minimal()
        del data["what_it_does"]
        with pytest.raises(ValidationError) as exc:
            KbParameter.model_validate(data)
        assert "what_it_does" in str(exc.value)

    def test_status_defaults_to_seeded(self) -> None:
        assert KbParameter.model_validate(self._minimal()).status == "seeded"

    def test_status_enum_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            KbParameter.model_validate(self._minimal(status="approved"))

    def test_sqx_version_defaults_to_pinned_144_2953(self) -> None:
        # WU3 uses the literal constant; WU4 swaps it for versioning.py.
        assert SQX_VERSION == "144.2953"
        assert KbParameter.model_validate(self._minimal()).sqx_version == SQX_VERSION

    def test_tab_must_be_one_of_the_eight(self) -> None:
        with pytest.raises(ValidationError):
            KbParameter.model_validate(self._minimal(tab="Other tab"))
        # Every documented tab name must be accepted.
        for tab in KB_TABS:
            assert KbParameter.model_validate(self._minimal(tab=tab)).tab == tab

    def test_kb_tabs_are_exactly_the_eight_documented(self) -> None:
        assert set(KB_TABS) == {
            "What to build",
            "Genetic options",
            "Data",
            "Trading options",
            "Building blocks",
            "Money management",
            "Cross checks",
            "Ranking",
        }

    def test_small_account_recommendation_nested_model(self) -> None:
        param = KbParameter.model_validate(
            self._minimal(
                small_account_recommendation={
                    "recommended_value": 1,
                    "default_value": 0,
                    "reason": "Avoid overtrading and commissions on a $100 account.",
                }
            )
        )
        assert param.small_account_recommendation is not None
        assert param.small_account_recommendation.recommended_value == 1
        assert param.small_account_recommendation.default_value == 0
        assert "overtrading" in param.small_account_recommendation.reason

    def test_yaml_roundtrip_preserves_all_fields(self) -> None:
        # REQ-201 scenario: a valid parameter file loads and is queryable.
        import yaml

        param = KbParameter.model_validate(
            self._minimal(
                hypothesis_relation="Daily-count caps reduce noise entries",
                related_parameters=["Stop Loss"],
                small_account_recommendation={
                    "recommended_value": 1,
                    "default_value": 0,
                    "reason": "Avoid overtrading.",
                },
            )
        )
        raw = yaml.safe_dump(param.model_dump(exclude_none=True), sort_keys=False)
        loaded = KbParameter.model_validate(yaml.safe_load(raw))
        assert loaded == param
        assert loaded.related_parameters == ["Stop Loss"]


# ──────────────────────────────────────────────────────────────────────────────
# REQ-202 / REQ-502 / REQ-208: Storage layout, query surface, invalidation
# ──────────────────────────────────────────────────────────────────────────────


class TestKbStore:
    """KbStore over the version-isolated ``structured/sqx-kb/{ver}/`` layout."""

    def _param(self, tab: str, name: str, **overrides: object) -> KbParameter:
        return KbParameter.model_validate(
            {
                "name": name,
                "sqx_name": name,
                "tab": tab,
                "section": "1. Test",
                "type": "str",
                "default": None,
                "what_it_does": f"Documented behavior of {name}.",
                "how_it_works_in_sqx": f"Mechanism of {name} in the builder.",
                "quant_trading_role": f"Role of {name} for trading.",
                **overrides,
            }
        )

    def test_seed_writes_yaml_at_expected_layout(self, tmp_path: Path) -> None:
        store = make_kb_dir(tmp_path)
        param = self._param("Ranking", "Ranking Criterium")
        count = store.seed([param])
        assert count == 1
        path = (
            tmp_path
            / "lake"
            / "structured"
            / "sqx-kb"
            / "144.2953"
            / "parameters"
            / "Ranking"
            / "Ranking Criterium.yaml"
        )
        assert path.is_file()

    def test_get_roundtrips_seeded_parameter(self, tmp_path: Path) -> None:
        store = make_kb_dir(tmp_path)
        param = self._param("Ranking", "Ranking Criterium", default="Ret/DD 40")
        store.seed([param])
        loaded = store.get("Ranking", "Ranking Criterium")
        assert loaded == param
        assert loaded.default == "Ret/DD 40"

    def test_get_unknown_parameter_raises(self, tmp_path: Path) -> None:
        store = make_kb_dir(tmp_path)
        with pytest.raises(KbParamNotFoundError) as exc:
            store.get("Ranking", "Does Not Exist")
        assert "Does Not Exist" in str(exc.value)

    def test_version_isolated_lookup(self, tmp_path: Path) -> None:
        # REQ-202/502 scenario: the 144.2953 YAML is returned, not another version.
        # Each entry's sqx_version selects its bucket; the same tab/param name
        # lives independently in each version.
        store = make_kb_dir(tmp_path)
        v144 = self._param(
            "Ranking", "Ranking Criterium", default="Ret/DD 40 (v144)", sqx_version="144.2953"
        )
        v999 = self._param(
            "Ranking", "Ranking Criterium", default="Ret/DD 60 (v999)", sqx_version="999.0"
        )
        store.seed([v144, v999])
        assert store.get("Ranking", "Ranking Criterium", sqx_version="144.2953").default == (
            "Ret/DD 40 (v144)"
        )
        assert store.get("Ranking", "Ranking Criterium", sqx_version="999.0").default == (
            "Ret/DD 60 (v999)"
        )

    def test_list_filters_by_tab(self, tmp_path: Path) -> None:
        store = make_kb_dir(tmp_path)
        store.seed(
            [
                self._param("Ranking", "Ranking Criterium"),
                self._param("Ranking", "Custom filters"),
                self._param("Data", "Timeframe"),
            ]
        )
        ranking = store.list(tab="Ranking")
        assert len(ranking) == 2
        assert {p.name for p in ranking} == {"Ranking Criterium", "Custom filters"}

    def test_list_filters_by_status(self, tmp_path: Path) -> None:
        # REQ-502 scenario: only needs_review params are returned.
        store = make_kb_dir(tmp_path)
        store.seed(
            [
                self._param("Data", "Timeframe"),
                self._param("Data", "Symbol", status="needs_review"),
            ]
        )
        store.verify("Data", "Timeframe", evidence_ref="file:///real/config.cfx")
        needs_review = store.list(status="needs_review")
        assert [p.name for p in needs_review] == ["Symbol"]
        verified = store.list(status="verified")
        assert [p.name for p in verified] == ["Timeframe"]

    def test_verify_promotes_status_and_records_evidence(self, tmp_path: Path) -> None:
        # REQ-203 scenario: matching params update to verified with evidence_ref.
        store = make_kb_dir(tmp_path)
        store.seed([self._param("Trading options", "Stop Loss")])
        updated = store.verify(
            "Trading options", "Stop Loss", evidence_ref="file:///campaigns/c1/config.cfx"
        )
        assert updated.status == "verified"
        assert updated.evidence_ref == "file:///campaigns/c1/config.cfx"
        assert store.get("Trading options", "Stop Loss").status == "verified"

    def test_verify_unknown_parameter_raises(self, tmp_path: Path) -> None:
        store = make_kb_dir(tmp_path)
        with pytest.raises(KbParamNotFoundError):
            store.verify("Ranking", "Missing", evidence_ref="file:///x.cfx")

    def test_invalidate_marks_all_params_needs_review(self, tmp_path: Path) -> None:
        # REQ-208 scenario: version drift invalidates the whole old-version KB.
        store = make_kb_dir(tmp_path)
        store.seed(
            [
                self._param("Ranking", "Ranking Criterium"),
                self._param("Data", "Timeframe"),
            ],
            sqx_version="144.2953",
        )
        store.verify("Ranking", "Ranking Criterium", evidence_ref="file:///x.cfx")
        invalidated = store.invalidate("144.2953")
        assert invalidated == 2
        assert store.get("Ranking", "Ranking Criterium").status == "needs_review"
        assert store.get("Data", "Timeframe").status == "needs_review"

    def test_status_summary_counts_by_status(self, tmp_path: Path) -> None:
        store = make_kb_dir(tmp_path)
        store.seed(
            [
                self._param("Data", "Timeframe"),
                self._param("Data", "Symbol", status="needs_review"),
            ]
        )
        store.verify("Data", "Timeframe", evidence_ref="file:///x.cfx")
        summary = store.status()
        assert summary["total"] == 2
        assert summary["verified"] == 1
        assert summary["needs_review"] == 1
        assert summary["seeded"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# REQ-203 / REQ-206: Seed and verify process
# ──────────────────────────────────────────────────────────────────────────────


class TestSeeder:
    """Seeder from doc_dev/SQX Builder Config.md."""

    def test_seed_from_doc_creates_seeded_yamls_with_evidence(self, tmp_path: Path, sample_doc: Path) -> None:
        # REQ-203 scenario: one YAML per documented parameter, status seeded.
        store = make_kb_dir(tmp_path)
        result = seed_from_doc(store, doc_path=sample_doc)
        assert result.seeded > 0
        assert result.total > 0
        assert str(sample_doc) in (result.parameters[0].evidence_ref or "")

    def test_doc_gap_becomes_needs_review_without_invented_content(
        self, tmp_path: Path, sample_doc: Path
    ) -> None:
        # REQ-203 scenario: a parameter mentioned but unexplained (ATM) becomes
        # needs_review with no invented semantics.
        store = make_kb_dir(tmp_path)
        result = seed_from_doc(store, doc_path=sample_doc)
        gap = next(p for p in result.parameters if p.name == "ATM tab")
        assert gap.status == "needs_review"
        assert gap.what_it_does == GAP_WHAT_IT_DOES

    def test_seed_covers_all_eight_tabs(self, tmp_path: Path, sample_doc: Path) -> None:
        # REQ-202: every tab gets at least one seeded parameter.
        store = make_kb_dir(tmp_path)
        result = seed_from_doc(store, doc_path=sample_doc)
        seeded_tabs = {p.tab for p in result.parameters if p.status == "seeded"}
        assert set(KB_TABS) <= seeded_tabs

    def test_maximum_trades_per_day_recommendation(self, tmp_path: Path, sample_doc: Path) -> None:
        # REQ-206 scenario: recommendation 1, default 0, overtrading rationale.
        store = make_kb_dir(tmp_path)
        result = seed_from_doc(store, doc_path=sample_doc)
        entry = next(
            p for p in result.parameters if p.name == "Maximum Trades Per Day"
        )
        assert entry.small_account_recommendation is not None
        assert entry.small_account_recommendation.recommended_value == 1
        assert entry.small_account_recommendation.default_value == 0
        assert "overtrading" in entry.small_account_recommendation.reason.lower()

    def test_ranking_criterium_weights_from_doc(self, tmp_path: Path, sample_doc: Path) -> None:
        store = make_kb_dir(tmp_path)
        result = seed_from_doc(store, doc_path=sample_doc)
        entry = next(p for p in result.parameters if p.name == "Ranking Criterium")
        assert entry.status == "seeded"
        assert "40" in str(entry.default)
        assert "25" in str(entry.default)

    def test_missing_doc_returns_empty_result(self, tmp_path: Path) -> None:
        store = make_kb_dir(tmp_path)
        result = seed_from_doc(store, doc_path=tmp_path / "no-such-doc.md")
        assert result.total == 0
        assert result.seeded == 0


# ──────────────────────────────────────────────────────────────────────────────
# REQ-207: KB CLI
# ──────────────────────────────────────────────────────────────────────────────


class TestKbCli:
    """``quantlab sqx kb`` subcommands."""

    def _main(self, argv: list[str]) -> int:
        from quantlab.cli.main import main

        return main(argv)

    def test_kb_list_by_tab_exit_0(self, tmp_path: Path, sample_doc: Path, capsys: pytest.CaptureFixture) -> None:
        store = make_kb_dir(tmp_path)
        seed_from_doc(store, doc_path=sample_doc)
        code = self._main(
            ["sqx", "kb", "list", "--tab", "Ranking", "--knowledge-root", str(store.root)]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "Ranking Criterium" in out
        assert "needs_review" in out or "seeded" in out

    def test_kb_list_filters_by_status_exit_0(self, tmp_path: Path, sample_doc: Path, capsys: pytest.CaptureFixture) -> None:
        store = make_kb_dir(tmp_path)
        seed_from_doc(store, doc_path=sample_doc)
        code = self._main(
            ["sqx", "kb", "list", "--status", "needs_review", "--knowledge-root", str(store.root)]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "ATM tab" in out

    def test_kb_get_prints_yaml_exit_0(self, tmp_path: Path, sample_doc: Path, capsys: pytest.CaptureFixture) -> None:
        store = make_kb_dir(tmp_path)
        seed_from_doc(store, doc_path=sample_doc)
        code = self._main(
            [
                "sqx", "kb", "get",
                "Trading options/Maximum Trades Per Day",
                "--knowledge-root", str(store.root),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "what_it_does" in out
        assert "Maximum Trades Per Day" in out

    def test_kb_get_unknown_param_exit_1(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        # REQ-207 scenario: unknown param → exit 1 with a "not found" message.
        store = make_kb_dir(tmp_path)
        code = self._main(
            ["sqx", "kb", "get", "Unknown", "--knowledge-root", str(store.root)]
        )
        captured = capsys.readouterr()
        assert code == 1
        assert "not found" in (captured.out + captured.err).lower()

    def test_kb_get_unknown_tab_param_exit_1(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        store = make_kb_dir(tmp_path)
        code = self._main(
            ["sqx", "kb", "get", "Ranking/Missing Param", "--knowledge-root", str(store.root)]
        )
        err = capsys.readouterr().err
        assert code == 1
        assert "not found" in err.lower()

    def test_kb_seed_exit_0(self, tmp_path: Path, sample_doc: Path, capsys: pytest.CaptureFixture) -> None:
        store = make_kb_dir(tmp_path)
        code = self._main(
            [
                "sqx", "kb", "seed",
                "--doc", str(sample_doc),
                "--knowledge-root", str(store.root),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "seeded" in out.lower()

    def test_kb_status_exit_0(self, tmp_path: Path, sample_doc: Path, capsys: pytest.CaptureFixture) -> None:
        store = make_kb_dir(tmp_path)
        seed_from_doc(store, doc_path=sample_doc)
        code = self._main(
            ["sqx", "kb", "status", "--knowledge-root", str(store.root)]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "needs_review" in out
