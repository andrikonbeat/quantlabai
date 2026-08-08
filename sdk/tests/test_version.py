"""Version pre-flight + drift workflow tests (REQ-303/304/305, D8/D9).

Covers the full WU4 contract:

* ``VersionPreflight`` — in-sync silent; drift warns but proceeds; mock /
  no-sqcli skips; installed build resolved from a license check (REQ-301).
* ``DriftWorkflow`` — drift writes ``structured/sqx-version/{old}→{new}/
  checklist.yaml`` {from, to, detected_at, affected_files, kb_invalidated,
  status} and invalidates old KB parameters (REQ-305/208); re-runs update
  the checklist in place (additive, no duplication).
* ``quantlab sqx check-version`` — exit 0 in-sync, 1 drift, 0 unknown
  (fail-open) (REQ-304).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from quantlab.cli.runner import CliResult
from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.store import KbStore
from quantlab.pipeline.license import LicenseManager
from quantlab.versioning import (
    PINNED_SQX_VERSION,
    DriftWorkflow,
    VersionPreflight,
)

# Real-sqcli-faithful license line with a point version (REQ-301).
BUILD_LINE_WITH_POINT = (
    "StrategyQuant X Ultimate Build 144.2953 (Futlab license) - valid until "
    "14.08.2026, license FUTLABF255"
)


def license_output(build: str) -> str:
    """Build a license line for an arbitrary installed build."""
    return (
        f"StrategyQuant X Ultimate Build {build} (Futlab license) - valid until "
        "14.08.2026, license FUTLABF255"
    )


class FakeExecutor:
    """Minimal Executor stub returning canned license output (mock executor)."""

    def __init__(self, license_stdout: str) -> None:
        self._stdout = license_stdout
        self.executed: list[list[str]] = []

    def execute(self, command: str | list[str], **kwargs: object) -> CliResult:
        self.executed.append(list(command) if isinstance(command, list) else [command])
        return CliResult(returncode=0, stdout=self._stdout, stderr="")


def make_param(name: str) -> KbParameter:
    """Minimal valid KbParameter for seeding a tmp lake."""
    return KbParameter(
        name=name,
        sqx_name=name,
        tab="Ranking",
        section="Ranking",
        type="int",
        what_it_does="dummy",
        how_it_works_in_sqx="dummy",
        quant_trading_role="dummy",
    )


@pytest.fixture
def seeded_kb(tmp_path: Path) -> Path:
    """A tmp Knowledge Lake with 2 pinned-version KB parameters."""
    root = tmp_path / "lake"
    store = KbStore(root=root)
    store.initialize()
    seeded = store.seed([make_param("Ranking Criterium"), make_param("Max Trades")])
    assert seeded == 2
    return root


# ──────────────────────────────────────────────────────────────────────────────
# REQ-303: VersionPreflight — fail-open compare
# ──────────────────────────────────────────────────────────────────────────────


class TestVersionPreflight:
    """Installed build vs PINNED_SQX_VERSION, warn-only, never raises."""

    def test_in_sync_is_silent(self, caplog: pytest.LogCaptureFixture) -> None:
        # REQ-303 "Matching version proceeds silently": no drift warning.
        preflight = VersionPreflight(executor=FakeExecutor(BUILD_LINE_WITH_POINT))
        with caplog.at_level(logging.WARNING, logger="quantlab.versioning"):
            status = preflight.run()
        assert status == "in-sync"
        assert preflight.installed_build == PINNED_SQX_VERSION
        assert not any(
            "drift" in r.getMessage().lower() for r in caplog.records
        )

    def test_in_sync_major_only_matches_pinned(self) -> None:
        # Real sqcli Build line carries no point version (REQ-301) — "144"
        # must NOT be treated as drift against pinned "144.2953".
        preflight = VersionPreflight(executor=FakeExecutor(license_output("144")))
        assert preflight.run() == "in-sync"

    def test_drift_warns_but_proceeds(
        self, caplog: pytest.LogCaptureFixture, seeded_kb: Path
    ) -> None:
        # REQ-303 "Drift warns but proceeds": warning logged, no exception,
        # no mock dispatch involved.
        preflight = VersionPreflight(
            executor=FakeExecutor(license_output("145.0")),
            knowledge_root=seeded_kb,
        )
        with caplog.at_level(logging.WARNING, logger="quantlab.versioning"):
            status = preflight.run()
        assert status == "drift"
        assert preflight.installed_build == "145.0"
        assert any("drift" in r.getMessage().lower() for r in caplog.records)

    def test_mock_path_skips_check(self) -> None:
        # REQ-303 "Mock path skips check": SQX_FORCE_MOCK → the executor is
        # never invoked and the check reports unknown.
        executor = FakeExecutor(license_output("145.0"))
        preflight = VersionPreflight(executor=executor, force_mock=True)
        assert preflight.run() == "unknown"
        assert preflight.installed_build is None
        assert executor.executed == []

    def test_no_sqcli_reports_unknown_without_raise(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # REQ-303 "sqcli not found": no executor → unknown, warn, no raise.
        preflight = VersionPreflight(executor=None)
        with caplog.at_level(logging.WARNING, logger="quantlab.versioning"):
            status = preflight.run()
        assert status == "unknown"
        assert preflight.installed_build is None
        assert any(
            "skip" in r.getMessage().lower() or "unknown" in r.getMessage().lower()
            for r in caplog.records
        )


# ──────────────────────────────────────────────────────────────────────────────
# REQ-305: DriftWorkflow — checklist + KB invalidation
# ──────────────────────────────────────────────────────────────────────────────


class TestDriftWorkflow:
    """Drift persists a migration checklist and invalidates old KB params."""

    def _checklist_path(self, root: Path, to: str = "145.0") -> Path:
        return (
            root
            / "structured"
            / "sqx-version"
            / f"{PINNED_SQX_VERSION}→{to}"
            / "checklist.yaml"
        )

    def test_drift_writes_checklist_and_invalidates_kb(self, seeded_kb: Path) -> None:
        import yaml

        preflight = VersionPreflight(
            executor=FakeExecutor(license_output("145.0")),
            knowledge_root=seeded_kb,
        )
        assert preflight.run() == "drift"

        # REQ-305: checklist.yaml at structured/sqx-version/144.2953→145.0/
        checklist = self._checklist_path(seeded_kb)
        assert checklist.is_file()
        doc = yaml.safe_load(checklist.read_text(encoding="utf-8"))
        assert doc["from"] == PINNED_SQX_VERSION
        assert doc["to"] == "145.0"
        assert doc["status"] == "drift"
        assert "detected_at" in doc
        # affected_files lists the KB params of the departed version.
        assert doc["affected_files"]
        assert any("sqx-kb/144.2953" in f for f in doc["affected_files"])
        assert doc["kb_invalidated"] == 2

        # REQ-208: all old-version params are now needs_review.
        params = KbStore(root=seeded_kb).list(sqx_version=PINNED_SQX_VERSION)
        assert params and all(p.status == "needs_review" for p in params)

    def test_checklist_not_written_when_in_sync(self, seeded_kb: Path) -> None:
        preflight = VersionPreflight(
            executor=FakeExecutor(BUILD_LINE_WITH_POINT),
            knowledge_root=seeded_kb,
        )
        assert preflight.run() == "in-sync"
        version_dir = seeded_kb / "structured" / "sqx-version"
        if version_dir.is_dir():
            assert list(version_dir.rglob("checklist.yaml")) == []

    def test_rerun_updates_in_place_not_duplicated(self, seeded_kb: Path) -> None:
        workflow = DriftWorkflow(seeded_kb)
        first = workflow.run(PINNED_SQX_VERSION, "145.0")
        second = workflow.run(PINNED_SQX_VERSION, "145.0")
        checklist = self._checklist_path(seeded_kb)
        assert checklist.is_file()
        # REQ-305 "Re-run is additive": exactly one checklist for the
        # transition, updated in place, not duplicated.
        yamls = list(checklist.parent.glob("*.yaml"))
        assert len(yamls) == 1
        assert first["to"] == second["to"] == "145.0"


# ──────────────────────────────────────────────────────────────────────────────
# REQ-701: version_preflight hook beside license_preflight
# ──────────────────────────────────────────────────────────────────────────────


class TestCliWrapperVersionPreflight:
    """``version_preflight`` reuses the license check's build (REQ-701)."""

    def test_in_sync_from_license_info(self) -> None:
        from quantlab.sqx.cli_wrapper import version_preflight

        info = LicenseManager._parse_info(BUILD_LINE_WITH_POINT)
        assert info.build_number == PINNED_SQX_VERSION
        assert version_preflight(info) == "in-sync"

    def test_drift_from_license_info_writes_checklist(
        self, seeded_kb: Path
    ) -> None:
        from quantlab.sqx.cli_wrapper import version_preflight
        from quantlab.pipeline.license import LicenseInfo

        info = LicenseInfo(build_number="145.0")
        assert version_preflight(info, knowledge_root=seeded_kb) == "drift"
        checklist = (
            seeded_kb
            / "structured"
            / "sqx-version"
            / f"{PINNED_SQX_VERSION}→145.0"
            / "checklist.yaml"
        )
        assert checklist.is_file()

    def test_unknown_build_skips_quietly(self) -> None:
        from quantlab.sqx.cli_wrapper import version_preflight
        from quantlab.pipeline.license import LicenseInfo

        assert version_preflight(LicenseInfo()) == "unknown"


# ──────────────────────────────────────────────────────────────────────────────
# REQ-304: quantlab sqx check-version
# ──────────────────────────────────────────────────────────────────────────────


class TestCheckVersionCli:
    """``quantlab sqx check-version`` exit contract 0/1/unknown."""

    def _main(self, argv: list[str]) -> int:
        from quantlab.cli.main import main

        return main(argv)

    def _monkeypatch_sqcli(
        self, monkeypatch: pytest.MonkeyPatch, build: str
    ) -> FakeExecutor:
        """Point RealExecutor and _find_sqcli at a fake sqcli."""
        import quantlab.cli.runner as runner_mod
        import quantlab.sqx.cli_wrapper as cw

        fake = FakeExecutor(license_output(build))
        monkeypatch.setattr(runner_mod, "RealExecutor", lambda _path: fake)
        monkeypatch.setattr(cw, "_find_sqcli", lambda _path: "/fake/sqcli")
        return fake

    def test_in_sync_prints_and_exits_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._monkeypatch_sqcli(monkeypatch, "144.2953")
        code = self._main(
            ["sqx", "check-version", "--knowledge-root", str(tmp_path)]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "in-sync" in out.lower()
        assert "144.2953" in out
        assert "pinned" in out.lower()

    def test_drift_prints_and_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._monkeypatch_sqcli(monkeypatch, "145.0")
        code = self._main(
            ["sqx", "check-version", "--knowledge-root", str(tmp_path)]
        )
        out = capsys.readouterr().out
        assert code == 1
        assert "drift" in out.lower()
        assert "145.0" in out
        # REQ-305: drift through the CLI also persists the checklist.
        checklist = (
            tmp_path
            / "structured"
            / "sqx-version"
            / f"{PINNED_SQX_VERSION}→145.0"
            / "checklist.yaml"
        )
        assert checklist.is_file()

    def test_unknown_without_sqcli_exits_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # REQ-304 "Unknown when sqcli unavailable": no binary and no override
        # → prints unknown and exits 0 (fail-open).
        code = self._main(
            [
                "sqx", "check-version",
                "--sqx-path", str(tmp_path / "no-sqcli-here"),
                "--knowledge-root", str(tmp_path),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "unknown" in out.lower()
        assert "pinned" in out.lower()
