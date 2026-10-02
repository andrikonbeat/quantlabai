"""Phase 4 (PR 3) — ``KbStore.reverify_against_build`` (D4/D5, scenarios 8-10).

PR 2's pure module decides; this wrapper supplies the population and the single write path.
Evidence is the TRACKED ``default-project.sqx-template`` and the lake is a four-entry
``tmp_path`` lake holding the real anchor shapes: one entry that positively resolves, one
that genuinely does not (SQX ships ``OptProfileSysParamPermutation`` instead of
``SequentialOptimization``), the one real documentation gap, and a non-``Cross checks``
entry with no anchor at all. The live 82-entry lake is never written.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from quantlab.knowledge.kb.models import SQX_VERSION
from quantlab.knowledge.kb.reverify import (
    EntryVerdict,
    ReverifyReport,
    UnknownVersionBucketError,
    Verdict,
)
from quantlab.knowledge.kb.store import KbStore

_EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "sdk/quantlab/sqx/templates/default-project.sqx-template"
)
_VERSION = SQX_VERSION
_TAB = "Cross checks"
_BASE = f"structured/sqx-kb/{_VERSION}/parameters/{_TAB}"
_PROMOTED = f"{_BASE}/What If simulations.yaml"
_DOC_YAML = f"{_BASE}/Cross Checks vs Retester.yaml"
_DOC_GAP = "docs/sqx-builder-config/SQX Builder Config.md#Cross checks"

# tab, name, xml_path, element_name, status — the real catalog shapes.
_ENTRIES = (
    (_TAB, "What If simulations", "CrossChecks/WhatIf", "WhatIf", "needs_review"),
    (
        _TAB,
        "Sequential Optimization",
        "CrossChecks/SequentialOptimization",
        "SequentialOptimization",
        "needs_review",
    ),
    (
        _TAB,
        "Cross Checks vs Retester",
        _DOC_GAP,
        "Cross checks vs Retester",
        "verified",
    ),
    ("Data", "Data sample size", None, None, "seeded"),
)


def _yaml(
    tab: str,
    name: str,
    status: str,
    xml_path: str | None = None,
    element_name: str | None = None,
    version: str = _VERSION,
) -> str:
    """Serialize one lake entry the way the store itself would."""
    data: dict[str, Any] = {
        "name": name,
        "sqx_name": name,
        "tab": tab,
        "section": "1. BASIC (FAST)",
        "type": "config",
        "what_it_does": "Scenario tests to check profit dependence on isolated events.",
        "how_it_works_in_sqx": "What-If robustness simulations.",
        "quant_trading_role": "Detects event-dependent profitability.",
        "status": status,
        "sqx_version": version,
    }
    if xml_path is not None:
        data["xml_path"] = xml_path
    if element_name is not None:
        data["element_name"] = element_name
    return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)


def _snapshot(root: Path) -> dict[str, bytes]:
    """Byte-for-byte map of every file in the lake, for write detection."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _verdict(report: ReverifyReport, name: str) -> Verdict:
    return next(e.verdict for e in report.entries if e.name == name)


@pytest.fixture
def lake(tmp_path: Path) -> KbStore:
    """A lake holding the four real anchor shapes in the pinned version bucket."""
    store = KbStore(root=tmp_path)
    store.initialize()
    for tab, name, xml_path, element_name, status in _ENTRIES:
        path = store._param_path(tab, name, _VERSION)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _yaml(tab, name, status, xml_path, element_name), encoding="utf-8"
        )
    return store


class TestDryRunIsTheDefault:
    """Scenario 8: omitted ``apply`` returns verdicts and writes nothing."""

    def test_dry_run_is_the_default_and_writes_nothing(self, lake: KbStore) -> None:
        before = _snapshot(lake.root)

        report = lake.reverify_against_build(_EVIDENCE)

        assert _snapshot(lake.root) == before, "dry-run must not write"
        assert len(report.entries) == 4
        assert report.artifact == str(_EVIDENCE)
        assert report.evidence_ok is True
        assert report.counts == {
            "verified": 1,
            "field_absent": 1,
            "not_xml_backed": 2,
            "evidence_unreadable": 0,
        }
        assert [e.name for e in report.promotable] == ["What If simulations"]
        assert lake.get(_TAB, "What If simulations").status == "needs_review"


class TestPromotionGoesThroughVerify:
    """D4/scenario 9: every promotion is an existing ``verify()`` call."""

    def test_promotion_routes_through_the_existing_verify_path(
        self, lake: KbStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple] = []
        real_verify = KbStore.verify

        def spy(self, tab, param, evidence_ref, sqx_version=None):
            calls.append((tab, param, evidence_ref, sqx_version))
            return real_verify(self, tab, param, evidence_ref, sqx_version)

        monkeypatch.setattr(KbStore, "verify", spy)
        report = lake.reverify_against_build(_EVIDENCE, apply=True)

        assert calls == [
            (
                _TAB,
                "What If simulations",
                f"{_EVIDENCE}#CrossChecks/WhatIf",
                _VERSION,
            )
        ]
        promoted = lake.get(_TAB, "What If simulations")
        assert promoted.status == "verified"
        assert promoted.evidence_ref == f"{_EVIDENCE}#CrossChecks/WhatIf"
        assert [e.name for e in report.entries if e.verdict is Verdict.VERIFIED] == [
            "What If simulations"
        ]

    def test_wrapper_write_preserves_the_xml_anchor_pair(self, lake: KbStore) -> None:
        """Finding 0 tripwire: the wrapper write must not strip either anchor."""
        lake.reverify_against_build(_EVIDENCE, apply=True)

        promoted = lake.get(_TAB, "What If simulations")
        assert (promoted.xml_path, promoted.element_name) == (
            "CrossChecks/WhatIf",
            "WhatIf",
        )
        on_disk = lake._param_path(_TAB, "What If simulations", _VERSION).read_text()
        assert "xml_path: CrossChecks/WhatIf" in on_disk
        assert "element_name: WhatIf" in on_disk


class TestNonPromotingOutcomesNeverWrite:
    """Only ``verified`` may mutate the store (four-outcome verdict contract)."""

    def test_field_absent_is_terminal_and_is_left_untouched(
        self, lake: KbStore
    ) -> None:
        before = _snapshot(lake.root)

        report = lake.reverify_against_build(_EVIDENCE, apply=True)

        assert lake.get(_TAB, "Sequential Optimization").status == "needs_review"
        changed = {k for k, v in _snapshot(lake.root).items() if v != before[k]}
        assert changed == {_PROMOTED}, "only the promoted entry may be written"
        assert _verdict(report, "Sequential Optimization") is Verdict.FIELD_ABSENT

    def test_documentation_anchor_is_skipped_even_when_it_needs_review(
        self, lake: KbStore
    ) -> None:
        """D5: a doc gap is skipped by SHAPE — never because of its status."""
        entry = lake.get(_TAB, "Cross Checks vs Retester")
        entry.status = "needs_review"
        lake._save_file(entry)
        before = _snapshot(lake.root)

        report = lake.reverify_against_build(_EVIDENCE, apply=True)

        assert _verdict(report, "Cross Checks vs Retester") is Verdict.NOT_XML_BACKED
        assert _snapshot(lake.root)[_DOC_YAML] == before[_DOC_YAML]
        assert lake.get(_TAB, "Cross Checks vs Retester").status == "needs_review"

    def test_an_already_verified_doc_gap_is_still_not_promoted(
        self, lake: KbStore
    ) -> None:
        """D5: a status filter would have exempted this entry; it must still be skipped."""
        assert lake.get(_TAB, "Cross Checks vs Retester").status == "verified"
        before = _snapshot(lake.root)

        report = lake.reverify_against_build(_EVIDENCE, apply=True)

        assert _verdict(report, "Cross Checks vs Retester") is Verdict.NOT_XML_BACKED
        assert _snapshot(lake.root)[_DOC_YAML] == before[_DOC_YAML]


class TestUnreadableEvidence:
    """Scenario 10: unreadable evidence is a run-level outcome with zero writes."""

    @pytest.mark.parametrize("apply", [False, True])
    def test_unreadable_evidence_reports_and_writes_nothing(
        self, lake: KbStore, tmp_path: Path, apply: bool
    ) -> None:
        before = _snapshot(lake.root)

        report = lake.reverify_against_build(tmp_path / "absent.cfx", apply=apply)

        assert report.evidence_ok is False
        assert report.entries == ()
        assert report.counts["evidence_unreadable"] == 1
        assert "does not exist" in report.unreadable_reason
        assert _snapshot(lake.root) == before


class TestTabScoping:
    """``tab`` narrows the population; it does not filter verdicts."""

    def test_tab_scoping_narrows_the_population(self, lake: KbStore) -> None:
        scoped = lake.reverify_against_build(_EVIDENCE, tab=_TAB)
        unscoped = lake.reverify_against_build(_EVIDENCE)

        assert len(scoped.entries) == 3
        assert len(unscoped.entries) == 4
        assert {e.tab for e in scoped.entries} == {_TAB}
        assert "Data sample size" in {e.name for e in unscoped.entries}
        assert "Data sample size" not in {e.name for e in scoped.entries}


class TestVersionBucketGuard:
    """An unknown bucket is refused, never answered with a silent empty run."""

    def test_unknown_version_bucket_is_refused(self, lake: KbStore) -> None:
        with pytest.raises(UnknownVersionBucketError) as exc_info:
            lake.reverify_against_build(_EVIDENCE, sqx_version="999.1")

        assert exc_info.value.sqx_version == "999.1"

    def test_known_non_pinned_bucket_is_reverified_without_leaking(
        self, lake: KbStore
    ) -> None:
        path = lake._param_path(_TAB, "What If simulations", "145.1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _yaml(
                _TAB,
                "What If simulations",
                "needs_review",
                "CrossChecks/WhatIf",
                "WhatIf",
                "145.1",
            ),
            encoding="utf-8",
        )

        report = lake.reverify_against_build(_EVIDENCE, sqx_version="145.1", apply=True)

        assert [e.name for e in report.entries] == ["What If simulations"]
        pinned = lake.get(_TAB, "What If simulations", sqx_version=_VERSION)
        other = lake.get(_TAB, "What If simulations", sqx_version="145.1")
        assert other.status == "verified" and pinned.status == "needs_review"


def test_idempotent_reverify_is_stable(lake: KbStore) -> None:
    """D5: re-``verify()`` is idempotent, so a second apply pass is a no-op."""
    lake.reverify_against_build(_EVIDENCE, apply=True)
    after_first = _snapshot(lake.root)

    lake.reverify_against_build(_EVIDENCE, apply=True)

    assert _snapshot(lake.root) == after_first


class TestReportContract:
    """The report is the pipeline's only surface, under both ``apply`` values.

    ``counts``' readable half is asserted by ``test_dry_run_is_the_default_and_writes_
    nothing`` and its unreadable half by ``TestUnreadableEvidence``; what is unique here is
    that every outcome explains itself in the operator's terms.
    """

    @pytest.mark.parametrize(
        "xml_path, verdict, fragment",
        [
            ("CrossChecks/WhatIf", Verdict.VERIFIED, "resolves"),
            ("CrossChecks/Missing", Verdict.FIELD_ABSENT, "does not resolve"),
            (None, Verdict.NOT_XML_BACKED, "no xml_path"),
            ("docs/x.md#A", Verdict.NOT_XML_BACKED, "not an XML anchor"),
            ("CrossChecks/WhatIf", Verdict.EVIDENCE_UNREADABLE, "no entry was probed"),
        ],
    )
    def test_reason_explains_each_verdict(
        self, xml_path: str | None, verdict: Verdict, fragment: str
    ) -> None:
        assert fragment in EntryVerdict(_TAB, "n", xml_path, verdict).reason
