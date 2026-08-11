"""REQ-209 seed-validation gate tests (PR1 WU1+WU2, D1-D4).

The gate validates the seeded SQX Parameter KB after ``sqx kb seed`` and
SHALL fail unless: (1) every emitted YAML loads against the REQ-201 schema,
(2) the index was rebuilt with ``kb_parameters`` coverage for the pinned
version (REQ-403), (3) every parameter carries a non-empty ``evidence_ref``
and every *verified* parameter's reference points to an existing file, and
(4) the status distribution matches the frozen seeding band
(total == 82; verified / needs_review within the frozen range;
verified + needs_review == total). ``needs_review`` within the quota is a
SUCCESS terminal state and MUST NOT fail the gate (REQ-209 scenario 2).

All tests run against ``tmp_path`` lakes — deterministic and CI-safe, never
touching the untracked real install (D9).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import yaml

from quantlab.knowledge.kb.educational import (
    TPL_KEY_MAP,
    build_educational_dataset,
    load_educational_dataset,
    parse_tpl_build,
)
from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.seeder import iter_seed_entries
from quantlab.knowledge.kb.seeding_flow import CFX_EVIDENCE_MAP, run_seed_flow
from quantlab.knowledge.kb.store import KbStore
from quantlab.knowledge.kb.validation import (
    NEEDS_REVIEW_MAX,
    NEEDS_REVIEW_MIN,
    SEED_TOTAL,
    VERIFIED_MAX,
    VERIFIED_MIN,
    SeedValidationReport,
    validate_seed,
)
from quantlab.knowledge.store import KnowledgeStore

FIXTURE_TPL = Path(__file__).parent / "fixtures" / "tpl_build_mini.xml"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _full_doc(tmp_path: Path) -> Path:
    """Generate a doc that documents every SEED_SPEC doc_key (all 77 seeded).

    Each tab heading matches the seeder's ``TAB_HEADING_MARKERS``; every
    doc_key is emitted verbatim under its tab so ``_doc_keys_found`` passes.
    GAP_SPEC entries have no doc_keys and stay needs_review.
    """
    lines = ["# **SQX Builder Config**"]
    current: str | None = None
    for entry in iter_seed_entries():
        tab = str(entry["tab"])
        if tab != current:
            lines.append(f"### **{tab}**")
            current = tab
        for key in entry.get("doc_keys") or []:
            lines.append(f"* **{key}:** yes.")
    doc = tmp_path / "SQX Builder Config.md"
    doc.write_text("\n".join(lines), encoding="utf-8")
    return doc


def _evidence_files(tmp_path: Path, evidence_base: Path) -> None:
    """Create an empty file for every CFX_EVIDENCE_MAP path (existence checks)."""
    for ref in CFX_EVIDENCE_MAP.values():
        target = evidence_base / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text("<config/>", encoding="utf-8")


def _make_lake(
    root: Path,
    *,
    verified: int,
    needs_review: int,
    seeded: int = 0,
    rebuild_index: bool = True,
) -> KbStore:
    """Build a full 82-entry lake with a controlled status distribution.

    Verified entries get evidence_refs to real temp ``.cfx`` files;
    needs_review/seeded entries get a non-empty doc anchor ref.
    """
    store = KbStore(root=root)
    store.initialize()
    entries = list(iter_seed_entries())
    assert len(entries) == SEED_TOTAL
    assert verified + needs_review + seeded == SEED_TOTAL

    ev_dir = root / "evidence"
    ev_dir.mkdir(exist_ok=True)
    params: list[KbParameter] = []
    for i, entry in enumerate(entries):
        fields = {k: v for k, v in entry.items() if k != "doc_keys"}
        if i < verified:
            fields["status"] = "verified"
            ev = ev_dir / f"ev{i:03d}.cfx"
            ev.write_text("<config/>", encoding="utf-8")
            fields["evidence_ref"] = str(ev)
        elif i < verified + seeded:
            fields["status"] = "seeded"
            fields["evidence_ref"] = f"{root}/doc.md#tab"
        else:
            fields["status"] = "needs_review"
            fields["evidence_ref"] = f"{root}/doc.md#tab"
        params.append(KbParameter.model_validate(fields))

    store.seed(params)
    if rebuild_index:
        store.store.rebuild_index()
    return store


def _kb_args(root: Path, **overrides: object) -> argparse.Namespace:
    args = argparse.Namespace(
        knowledge_root=str(root),
        sqx_version="144.2953",
        doc=str(root / "SQX Builder Config.md"),
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


# ──────────────────────────────────────────────────────────────────────────────
# REQ-209 scenario: Schema violation fails the gate
# ──────────────────────────────────────────────────────────────────────────────


class TestSchemaViolationFails:
    """A YAML missing a required field fails, naming param + field."""

    def test_missing_what_it_does_fails_naming_param_and_field(
        self, tmp_path: Path
    ) -> None:
        store = _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        param = store.get("Ranking", "Ranking Criterium")
        data = param.model_dump()
        del data["what_it_does"]
        bad_path = (
            tmp_path
            / "structured/sqx-kb/144.2953/parameters/Ranking/Ranking Criterium.yaml"
        )
        bad_path.write_text(yaml.safe_dump(data), encoding="utf-8")

        report = validate_seed(tmp_path)

        assert report.checks["schema"] is False
        assert any("Ranking Criterium" in e for e in report.errors)
        assert any("what_it_does" in e for e in report.errors)
        assert report.ok is False

    def test_corrupt_yaml_fails(self, tmp_path: Path) -> None:
        store = _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        bad_path = (
            tmp_path
            / "structured/sqx-kb/144.2953/parameters/Ranking/Ranking Criterium.yaml"
        )
        bad_path.write_text("not: [valid\n  yaml", encoding="utf-8")

        report = validate_seed(tmp_path)

        assert report.checks["schema"] is False
        assert any("Ranking Criterium" in e for e in report.errors)
        assert report.ok is False


# ──────────────────────────────────────────────────────────────────────────────
# REQ-209 scenario: Stale or incomplete index fails the gate
# ──────────────────────────────────────────────────────────────────────────────


class TestStaleIndexFails:
    def test_index_without_kb_parameters_fails(self, tmp_path: Path) -> None:
        _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        # Simulate the pre-rebuild v3 index (current repo state).
        (tmp_path / "index.yaml").write_text(
            "_version: '3'\ndirectories: {}\n", encoding="utf-8"
        )

        report = validate_seed(tmp_path)

        assert report.checks["index_coverage"] is False
        assert any("index" in e.lower() for e in report.errors)
        assert any("kb_parameters" in e for e in report.errors)
        assert report.ok is False

    def test_partial_index_coverage_fails(self, tmp_path: Path) -> None:
        store = _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        index = store.store.read_index()
        coverage = index["kb_parameters"]
        assert len(coverage) == SEED_TOTAL  # sanity: rebuilt index covers all
        # Keep only half the entries -> coverage must fail the gate.
        index["kb_parameters"] = dict(list(coverage.items())[: SEED_TOTAL // 2])
        (tmp_path / "index.yaml").write_text(
            yaml.safe_dump(index), encoding="utf-8"
        )

        report = validate_seed(tmp_path)

        assert report.checks["index_coverage"] is False
        assert report.ok is False


# ──────────────────────────────────────────────────────────────────────────────
# REQ-209 scenario: Inconsistent evidence_ref fails the gate
# ──────────────────────────────────────────────────────────────────────────────


class TestDanglingEvidenceFails:
    def test_verified_param_dangling_evidence_fails(self, tmp_path: Path) -> None:
        store = _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        param = store.list(status="verified")[0]
        dangling = param.model_copy(
            update={"evidence_ref": str(tmp_path / "does-not-exist.cfx")}
        )
        store.seed([dangling])

        report = validate_seed(tmp_path)

        assert report.checks["evidence"] is False
        assert any(param.name in e for e in report.errors)
        assert any("does-not-exist.cfx" in e for e in report.errors)
        assert report.ok is False

    def test_empty_evidence_ref_fails(self, tmp_path: Path) -> None:
        store = _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        param = store.list(status="needs_review")[0]
        store.seed([param.model_copy(update={"evidence_ref": None})])

        report = validate_seed(tmp_path)

        assert report.checks["evidence"] is False
        assert any(param.name in e for e in report.errors)
        assert report.ok is False

    def test_valid_evidence_passes(self, tmp_path: Path) -> None:
        _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        report = validate_seed(tmp_path)
        assert report.checks["evidence"] is True


# ──────────────────────────────────────────────────────────────────────────────
# REQ-209 scenario: Seed produces expected distribution (frozen band)
# ──────────────────────────────────────────────────────────────────────────────


class TestDistributionBand:
    def test_expected_distribution_passes(self, tmp_path: Path) -> None:
        _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        report = validate_seed(tmp_path)
        assert report.checks["distribution"] is True
        assert report.checks["schema"] is True
        assert report.checks["index_coverage"] is True
        assert report.checks["evidence"] is True
        assert report.errors == []
        assert report.ok is True

    def test_needs_review_within_quota_is_success(self, tmp_path: Path) -> None:
        # needs_review is an accepted terminal state; gate must not raise on it.
        store = _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        report = validate_seed(tmp_path)
        assert report.counts["needs_review"] > 0
        assert report.checks["distribution"] is True
        assert all("needs_review" not in e for e in report.errors)
        assert report.ok is True

    def test_total_mismatch_fails(self, tmp_path: Path) -> None:
        store = _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        # Drop one YAML so total != SEED_TOTAL.
        target = store.list()[0]
        (
            tmp_path
            / "structured/sqx-kb/144.2953/parameters"
            / target.tab
            / f"{target.name}.yaml"
        ).unlink()
        store.store.rebuild_index()

        report = validate_seed(tmp_path)

        assert report.checks["distribution"] is False
        assert report.ok is False

    def test_verified_outside_band_fails(self, tmp_path: Path) -> None:
        _make_lake(tmp_path, verified=VERIFIED_MIN - 10, needs_review=SEED_TOTAL - VERIFIED_MIN + 10)
        report = validate_seed(tmp_path)
        assert report.checks["distribution"] is False
        assert report.ok is False

    def test_needs_review_outside_band_fails(self, tmp_path: Path) -> None:
        _make_lake(tmp_path, verified=VERIFIED_MAX + 2, needs_review=SEED_TOTAL - VERIFIED_MAX - 2)
        report = validate_seed(tmp_path)
        assert report.checks["distribution"] is False
        assert report.ok is False

    def test_leftover_seeded_status_fails_sum_invariant(self, tmp_path: Path) -> None:
        # verified + needs_review must equal total: leftover seeded entries
        # mean the flow was not completed (D2 demotion is part of seed).
        _make_lake(
            tmp_path,
            verified=VERIFIED_MIN + 1,
            needs_review=SEED_TOTAL - VERIFIED_MIN - 2,
            seeded=1,
        )
        report = validate_seed(tmp_path)
        assert report.checks["distribution"] is False
        assert report.ok is False


# ──────────────────────────────────────────────────────────────────────────────
# Report shape / counts
# ──────────────────────────────────────────────────────────────────────────────


class TestSeedValidationReport:
    def test_report_carries_checks_counts_and_errors(self, tmp_path: Path) -> None:
        _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        report = validate_seed(tmp_path)
        assert isinstance(report, SeedValidationReport)
        assert set(report.checks) == {
            "schema",
            "index_coverage",
            "evidence",
            "distribution",
        }
        assert report.counts["total"] == SEED_TOTAL
        assert report.counts["verified"] == VERIFIED_MIN + 1
        assert report.counts["needs_review"] == SEED_TOTAL - VERIFIED_MIN - 1
        assert report.counts["seeded"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# Seeding flow: CFX_EVIDENCE_MAP + run_seed_flow (D2)
# ──────────────────────────────────────────────────────────────────────────────


class TestCfxEvidenceMap:
    def test_map_is_curated_74_entries(self) -> None:
        assert len(CFX_EVIDENCE_MAP) == 74

    def test_every_key_matches_a_seed_spec_entry(self) -> None:
        spec_names = {(str(e["tab"]), str(e["name"])) for e in iter_seed_entries() if "doc_keys" in e}
        for key in CFX_EVIDENCE_MAP:
            assert key in spec_names, f"map key {key} is not a SEED_SPEC entry"

    def test_every_value_is_a_cfx_install_path(self) -> None:
        for ref in CFX_EVIDENCE_MAP.values():
            assert ref.startswith("assets/SQX_")
            assert ref.endswith(".cfx")

    def test_downgraded_params_are_not_in_map(self) -> None:
        # Strategy style (no config evidence), Use + Number of Exit Types
        # (ambiguous naming) are documented as needs_review, never verified.
        mapped_names = {name for (_, name) in CFX_EVIDENCE_MAP}
        for name in ("Strategy style", "Use", "Number of Exit Types (SL/PT/etc...)"):
            assert name not in mapped_names

    def test_map_plus_downgraded_equals_all_seed_spec(self) -> None:
        spec_names = {str(e["name"]) for e in iter_seed_entries() if "doc_keys" in e}
        mapped_names = {name for (_, name) in CFX_EVIDENCE_MAP}
        leftover = spec_names - mapped_names
        assert leftover == {
            "Strategy style",
            "Use",
            "Number of Exit Types (SL/PT/etc...)",
        }


class TestRunSeedFlow:
    def test_end_to_end_synthetic_flow(self, tmp_path: Path) -> None:
        """seed → bulk-verify → demote → rebuild index → gate (exit 0)."""
        doc = _full_doc(tmp_path)
        evidence_base = tmp_path
        _evidence_files(tmp_path, evidence_base)

        result = run_seed_flow(
            KbStore(root=tmp_path / "lake"),
            doc_path=doc,
            sqx_version="144.2953",
            evidence_base=evidence_base,
        )

        store = KbStore(root=tmp_path / "lake")
        assert result.total == SEED_TOTAL
        assert result.verified == len(CFX_EVIDENCE_MAP)
        assert result.verified + result.needs_review == SEED_TOTAL
        assert result.ok is True
        assert result.report.errors == []

        # Index rebuilt with full kb_parameters coverage.
        index = KnowledgeStore(tmp_path / "lake").read_index()
        coverage = index["kb_parameters"]
        assert len(coverage) == SEED_TOTAL
        assert all(v["sqx_version"] == "144.2953" for v in coverage.values())

        # A mapped parameter is verified with .cfx evidence.
        verified = store.get("Genetic options", "Max # of Generations")
        assert verified.status == "verified"
        assert verified.evidence_ref and verified.evidence_ref.endswith(".cfx")

        # A leftover doc-only parameter was demoted to needs_review (D2).
        leftover = store.get("What to build", "Strategy style")
        assert leftover.status == "needs_review"

    def test_flow_without_evidence_base_never_verifies(self, tmp_path: Path) -> None:
        doc = _full_doc(tmp_path)
        result = run_seed_flow(
            KbStore(root=tmp_path / "lake"),
            doc_path=doc,
            sqx_version="144.2953",
            evidence_base=None,
        )
        assert result.verified == 0
        assert result.needs_review == SEED_TOTAL
        assert result.ok is False
        assert result.report.checks["distribution"] is False

    def test_flow_demotes_leftover_seeded_entries(self, tmp_path: Path) -> None:
        doc = _full_doc(tmp_path)
        evidence_base = tmp_path
        _evidence_files(tmp_path, evidence_base)
        result = run_seed_flow(
            KbStore(root=tmp_path / "lake"),
            doc_path=doc,
            sqx_version="144.2953",
            evidence_base=evidence_base,
        )
        store = KbStore(root=tmp_path / "lake")
        statuses = {p.status for p in store.list()}
        assert "seeded" not in statuses  # everything resolved to verified/needs_review
        assert result.report.counts["seeded"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# CLI wiring: sqx kb seed / sqx kb validate exit codes 0/1 (T-1.4)
# ──────────────────────────────────────────────────────────────────────────────


class TestKbSeedCliExitCodes:
    @pytest.mark.asyncio
    async def test_seed_exits_zero_on_valid_full_flow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quantlab.cli.sq_commands import cmd_kb_seed

        doc = _full_doc(tmp_path)
        evidence_base = tmp_path
        _evidence_files(tmp_path, evidence_base)
        args = _kb_args(tmp_path, doc=str(doc))
        # Default evidence derivation: parent of lake root contains assets? In
        # tests the lake is under tmp, so pass the base explicitly via a small
        # wrapper on run_seed_flow defaults — here we point knowledge_root at
        # tmp so the parent is tmp_path (no assets) -> use monkeypatch default.
        monkeypatch.setattr(
            "quantlab.cli.sq_commands._DEFAULT_EVIDENCE_BASE_FACTORY",
            lambda root: evidence_base,
        )

        code = await cmd_kb_seed(args)

        assert code == 0

    @pytest.mark.asyncio
    async def test_seed_exits_one_when_doc_missing(
        self, tmp_path: Path
    ) -> None:
        from quantlab.cli.sq_commands import cmd_kb_seed

        args = _kb_args(tmp_path, doc=str(tmp_path / "missing.md"))
        code = await cmd_kb_seed(args)
        assert code == 1

    @pytest.mark.asyncio
    async def test_seed_exits_one_on_distribution_failure(
        self, tmp_path: Path
    ) -> None:
        from quantlab.cli.sq_commands import cmd_kb_seed

        doc = _full_doc(tmp_path)
        args = _kb_args(tmp_path, doc=str(doc))
        code = await cmd_kb_seed(args)  # no evidence base -> nothing verifies
        assert code == 1


class TestKbValidateCliExitCodes:
    @pytest.mark.asyncio
    async def test_validate_exits_zero_on_healthy_lake(self, tmp_path: Path) -> None:
        from quantlab.cli.sq_commands import cmd_kb_validate

        _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        code = await cmd_kb_validate(_kb_args(tmp_path))
        assert code == 0

    @pytest.mark.asyncio
    async def test_validate_exits_one_on_stale_index(self, tmp_path: Path) -> None:
        from quantlab.cli.sq_commands import cmd_kb_validate

        _make_lake(tmp_path, verified=VERIFIED_MIN + 1, needs_review=SEED_TOTAL - VERIFIED_MIN - 1)
        (tmp_path / "index.yaml").write_text(
            "_version: '3'\ndirectories: {}\n", encoding="utf-8"
        )
        code = await cmd_kb_validate(_kb_args(tmp_path))
        assert code == 1


# ──────────────────────────────────────────────────────────────────────────────
# WU5 (PR3, T-3.1): integration layer — .cfx spot-checks, synthetic install
# tree E2E, and matrix rationale fallback composing the WU1-WU4 seams
# ──────────────────────────────────────────────────────────────────────────────


def _write_synthetic_cfx_tree(
    tmp_path: Path, make_cfx: object
) -> None:
    """Place a real ``.cfx`` ZIP at every CFX_EVIDENCE_MAP path (T-3.1).

    ``make_cfx`` wraps the committed ``config_mini.xml`` into a real ZIP
    container (AD-9); this helper drops one at each of the two distinct
    evidence paths the curated map references, so a synthetic install
    tree drives the same ``_bulk_verify`` existence checks as the real
    pinned install.
    """
    for ref in sorted(set(CFX_EVIDENCE_MAP.values())):
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        make_cfx(target.parent, name=target.name)


class TestCfxIntegration:
    """WU5 integration: cfx spot-checks, synthetic install tree E2E, matrix falls back."""

    def test_cfx_zip_maps_known_param_and_dataset_loads(
        self, tmp_path: Path, make_cfx: object
    ) -> None:
        """A synthetic .cfx ZIP maps a known (name, tab) to a verified KB
        record, and the educational dataset round-trips over the seeded lake."""
        doc = _full_doc(tmp_path)
        _write_synthetic_cfx_tree(tmp_path, make_cfx)

        result = run_seed_flow(
            KbStore(root=tmp_path / "lake"),
            doc_path=doc,
            sqx_version="144.2953",
            evidence_base=tmp_path,
        )
        assert result.ok is True

        store = KbStore(root=tmp_path / "lake")
        param = store.get("Genetic options", "Max # of Generations")
        assert param.status == "verified"
        assert param.evidence_ref and param.evidence_ref.endswith(".cfx")

        records = build_educational_dataset(
            store.list(),
            tpl=parse_tpl_build(FIXTURE_TPL),
            tpl_key_map=TPL_KEY_MAP,
        )
        rec = next(
            r
            for r in records
            if r.name == "Max # of Generations" and r.tab == "Genetic options"
        )
        assert rec.status == "verified"
        assert rec.evidence_ref and rec.evidence_ref.endswith(".cfx")

        edu = (
            tmp_path
            / "lake"
            / "structured"
            / "sqx-kb"
            / "144.2953"
            / "educational"
        )
        edu.mkdir(parents=True)
        (edu / "educational-dataset.yaml").write_text(
            yaml.safe_dump([r.model_dump() for r in records], sort_keys=False),
            encoding="utf-8",
        )
        loaded = load_educational_dataset(
            tmp_path / "lake", sqx_version="144.2953"
        )
        assert len(loaded) == SEED_TOTAL
        loaded_rec = next(
            r
            for r in loaded
            if r.name == "Max # of Generations" and r.tab == "Genetic options"
        )
        assert loaded_rec.status == "verified"

    @pytest.mark.asyncio
    async def test_seed_cli_on_synthetic_install_tree_reproduces_band(
        self, tmp_path: Path, make_cfx: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI seed over a synthetic install tree reproduces the T-1.5 band
        (74 verified + 8 needs_review) and exits 0 — same distribution as the
        real first seed, proving the seams compose end-to-end."""
        from quantlab.cli.sq_commands import cmd_kb_seed

        doc = _full_doc(tmp_path)
        _write_synthetic_cfx_tree(tmp_path, make_cfx)
        args = _kb_args(tmp_path, doc=str(doc))
        monkeypatch.setattr(
            "quantlab.cli.sq_commands._DEFAULT_EVIDENCE_BASE_FACTORY",
            lambda root: tmp_path,
        )

        code = await cmd_kb_seed(args)

        assert code == 0
        store = KbStore(root=tmp_path)
        statuses = store.status(sqx_version="144.2953")
        assert statuses["total"] == SEED_TOTAL
        assert statuses["verified"] == len(CFX_EVIDENCE_MAP)
        assert statuses["needs_review"] == SEED_TOTAL - len(CFX_EVIDENCE_MAP)
        # frozen band: verified in [71,77], needs_review in [5,11]
        assert VERIFIED_MIN <= statuses["verified"] <= VERIFIED_MAX
        assert NEEDS_REVIEW_MIN <= statuses["needs_review"] <= NEEDS_REVIEW_MAX

    def test_matrix_manual_rationale_honored_when_dataset_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rationale_overrides still win when the dataset is absent; the
        fallback never invents KB-sourced text (T-3.1 AC)."""
        from quantlab.agents.parameter_matrix import (
            DEFAULT_RATIONALE,
            generate_run_matrix,
        )
        from quantlab.phase4.retester import RetesterConfig

        monkeypatch.setattr(
            "quantlab.agents.parameter_matrix.load_educational_dataset",
            lambda **_: [],
        )
        config = RetesterConfig(
            strategy_id="S1",
            monte_carlo_runs=123,
            mc_percentile=95,
            walkforward_cycles=5,
            min_trades=30,
            confidence_level=0.95,
            databanks=[],
        )

        entries = generate_run_matrix(
            config,
            run_type="retest",
            rationale_overrides={"monte_carlo_runs": "manual choice"},
        )

        manual = next(e for e in entries if e["parameter"] == "monte_carlo_runs")
        assert manual["source"] == "manual"
        assert manual["rationale"] == "manual choice"
        defaults = [e for e in entries if e["source"] == "default"]
        assert defaults  # non-overridden fields still classified default
        assert all(e["rationale"] == DEFAULT_RATIONALE for e in defaults)
        assert not any(
            "controls a trading behavior" in e["rationale"] for e in entries
        )
