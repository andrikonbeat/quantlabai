"""Phase 5 (PR 4) — the ``sqx kb reverify`` command (D6/D7, scenarios 11-12).

PR 2 decides, PR 3 writes; this is the only operator-visible surface, and stdout is the
only report surface (spec Non-Goals), so it must render per-entry verdicts and per-outcome
counts. Argv is parsed through the *real* parser, so these tests also pin the subparser
wiring and the exit contract: 0 ran, 1 refused bucket, 3 unreadable evidence — never
argparse's 2, which stays reserved for a usage error.

Evidence is the TRACKED ``default-project.sqx-template`` and the lake is a three-entry
``tmp_path`` lake: the three real outcomes (resolves, genuinely absent, no anchor at all)
plus a second tab so ``--tab`` scoping is observable. The live lake is never written.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from quantlab.cli.main import build_parser, main
from quantlab.knowledge.kb.models import SQX_VERSION
from quantlab.knowledge.kb.store import KbStore

_EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "sdk/quantlab/sqx/templates/default-project.sqx-template"
)
_ABSENT = str(Path(__file__).resolve().parent / "no-such-build.cfx")
_VERSION = SQX_VERSION
_TAB = "Cross checks"
_PROMOTABLE = "What If simulations"

# tab, name, xml_path, element_name, status — the real catalog shapes.
_ENTRIES = (
    (_TAB, _PROMOTABLE, "CrossChecks/WhatIf", "WhatIf", "needs_review"),
    (
        _TAB,
        "Sequential Optimization",
        "CrossChecks/SequentialOptimization",
        "SequentialOptimization",
        "needs_review",
    ),
    ("Data", "Data sample size", None, None, "seeded"),
)


def _yaml(
    tab: str, name: str, status: str, xml_path: str | None, element_name: str | None
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
        "sqx_version": _VERSION,
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


@pytest.fixture
def lake(tmp_path: Path) -> KbStore:
    """A lake holding one entry per outcome, plus a second tab for scoping."""
    store = KbStore(root=tmp_path)
    store.initialize()
    for tab, name, xml_path, element_name, status in _ENTRIES:
        path = store._param_path(tab, name, _VERSION)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _yaml(tab, name, status, xml_path, element_name), encoding="utf-8"
        )
    return store


def _argv(lake: KbStore, *extra: str, evidence: str = str(_EVIDENCE)) -> list[str]:
    """Real CLI argv against the real parser (proves the subparser is registered)."""
    return [
        "sqx",
        "kb",
        "reverify",
        "--knowledge-root",
        str(lake.root),
        "--evidence",
        evidence,
        *extra,
    ]


async def _run(lake: KbStore, *extra: str, evidence: str = str(_EVIDENCE)) -> Any:
    """Run the parsed handler the way ``main()`` dispatches it."""
    args = build_parser().parse_args(_argv(lake, *extra, evidence=evidence))
    return await args.func(args)


class TestDryRunIsTheDefault:
    """Scenario 11: no ``--apply`` → counts on stdout, exit 0, zero writes."""

    async def test_dry_run_prints_counts_and_exits_zero(
        self, lake: KbStore, capsys: pytest.CaptureFixture[str]
    ) -> None:
        before = _snapshot(lake.root)

        code = await _run(lake)

        out = capsys.readouterr().out
        assert code == 0
        assert _snapshot(lake.root) == before, "dry-run must not write"
        assert "verified 1" in out
        assert "field_absent 1" in out
        assert "not_xml_backed 1" in out
        assert "evidence_unreadable 0" in out
        assert "dry-run (no changes)" in out

    async def test_dry_run_renders_every_entry_and_its_verdict(
        self, lake: KbStore, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """stdout is the only report surface, so each verdict must be readable."""
        await _run(lake)

        out = capsys.readouterr().out
        assert _PROMOTABLE in out
        assert "Sequential Optimization" in out
        assert "Data sample size" in out
        assert "CrossChecks/WhatIf" in out
        assert "does not resolve" in out, "field_absent must explain itself"

    async def test_tab_scoping_narrows_the_reported_population(
        self, lake: KbStore, capsys: pytest.CaptureFixture[str]
    ) -> None:
        await _run(lake, "--tab", _TAB)

        out = capsys.readouterr().out
        assert "not_xml_backed 0" in out, "the unanchored Data entry is out of scope"
        assert "Data sample size" not in out
        assert _PROMOTABLE in out


class TestApplyPromotes:
    """``--apply`` promotes through the existing verify path and says so."""

    async def test_apply_promotes_only_the_resolving_entry(
        self, lake: KbStore, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = await _run(lake, "--apply")

        out = capsys.readouterr().out
        assert code == 0
        promoted = lake.get(_TAB, _PROMOTABLE)
        assert promoted.status == "verified"
        assert promoted.evidence_ref == f"{_EVIDENCE}#CrossChecks/WhatIf"
        assert promoted.xml_path == "CrossChecks/WhatIf", "Finding 0 tripwire"
        assert lake.get(_TAB, "Sequential Optimization").status == "needs_review"
        assert "dry-run (no changes)" not in out
        assert "applied 1" in out


class TestUnreadableEvidenceExitsThree:
    """D6/scenario 12: distinct exit, zero writes, dispatch completes."""

    @pytest.mark.parametrize("flag", [(), ("--apply",)])
    async def test_unreadable_evidence_exits_three_without_writing(
        self,
        lake: KbStore,
        capsys: pytest.CaptureFixture[str],
        flag: tuple[str, ...],
    ) -> None:
        before = _snapshot(lake.root)

        code = await _run(lake, *flag, evidence=_ABSENT)

        err = capsys.readouterr().err
        assert code == 3, "unreadable evidence must not reuse 0/1 or argparse's 2"
        assert _snapshot(lake.root) == before
        assert "does not exist" in err


class TestExitContract:
    """The codes are distinct and documented: 0 ran, 1 refused, 2 usage, 3 unreadable."""

    def test_missing_evidence_flag_is_an_argparse_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["sqx", "kb", "reverify"]) == 2
        # Names the missing flag, not an unknown subcommand — 2 is a usage error only.
        assert "--evidence" in capsys.readouterr().err

    async def test_unknown_version_bucket_is_refused_not_answered_empty(
        self, lake: KbStore, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = await _run(lake, "--sqx-version", "999.1")

        assert code == 1
        assert "999.1" in capsys.readouterr().err

    def test_help_documents_the_exit_contract(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["sqx", "kb", "reverify", "--help"])

        # Collapse argparse's wrapping so the assertion is about the contract,
        # not about where the terminal happened to break the line.
        flat = " ".join(capsys.readouterr().out.split())
        assert "--evidence" in flat and "--apply" in flat
        assert "dry-run unless --apply" in flat.lower()
        assert "3 the evidence could not be read" in flat
        assert "Argparse keeps 2 for a usage error" in flat
