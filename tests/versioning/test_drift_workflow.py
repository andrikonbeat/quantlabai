"""Tests for DriftWorkflow wiring of invalidate_on_version_drift (PR6/W-3).

Strict TDD — RED phase: DriftWorkflow.run() still calls the legacy
``KbStore.invalidate()`` and the checklist carries only ``kb_invalidated``.
The new hook contract requires the checklist to record the full
``VersionDriftResult`` (``drifted``, ``warnings``) so consumers can
surface why entries were demoted (REQ-208/305).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.store import KbStore
from quantlab.versioning import DriftWorkflow


def _seed_param(name: str, status: str) -> KbParameter:
    return KbParameter(
        name=name,
        sqx_name=name,
        tab="Cross checks",
        section="1. BASIC (FAST)",
        type="config",
        what_it_does="seeded for drift workflow test",
        how_it_works_in_sqx="seeded for drift workflow test",
        quant_trading_role="seeded for drift workflow test",
        status=status,
        sqx_version="144.2953",
        evidence_ref="seeded",
    )


@pytest.fixture
def drift_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    store = KbStore(root=root)
    store.initialize()
    store.seed(
        [
            _seed_param("What If simulations", "verified"),
            _seed_param("Walk-Forward Optimization", "verified"),
        ]
    )
    return root


class TestDriftWorkflowWiresVersionDriftHook:
    """DriftWorkflow must demote through the REQ-208 hook and record it."""

    def test_checklist_records_version_drift_result(
        self, drift_root: Path
    ) -> None:
        """A 144.2953 → 145.1 migration demotes 2 entries and says so."""
        checklist = DriftWorkflow(drift_root).run("144.2953", "145.1")

        assert checklist["from"] == "144.2953"
        assert checklist["to"] == "145.1"
        assert checklist["kb_invalidated"] == 2
        assert checklist["drifted"] is True
        assert checklist["warnings"], "drift must surface an actionable warning"

        persisted = yaml.safe_load(
            (drift_root / "structured" / "sqx-version" / "144.2953→145.1" / "checklist.yaml").read_text()
        )
        assert persisted["drifted"] is True
        assert persisted["kb_invalidated"] == 2

    def test_entries_are_demoted_to_needs_review(self, drift_root: Path) -> None:
        result = DriftWorkflow(drift_root).run("144.2953", "145.1")
        assert result["kb_invalidated"] == 2

        statuses = {
            p.name: p.status for p in KbStore(root=drift_root).list(tab="Cross checks")
        }
        assert statuses == {
            "What If simulations": "needs_review",
            "Walk-Forward Optimization": "needs_review",
        }

    def test_in_sync_migration_is_a_no_op(self, drift_root: Path) -> None:
        """No version change demotes nothing and warns nothing."""
        checklist = DriftWorkflow(drift_root).run("144.2953", "144.2953")

        assert checklist["drifted"] is False
        assert checklist["kb_invalidated"] == 0
        assert checklist["warnings"] == []
        assert all(
            p.status == "verified"
            for p in KbStore(root=drift_root).list(tab="Cross checks")
        )

    def test_missing_kb_dir_is_fail_open(self, tmp_path: Path) -> None:
        """An empty knowledge root must not abort the checklist (REQ-305 fail-open)."""
        checklist = DriftWorkflow(tmp_path / "missing").run("144.2953", "145.1")

        assert checklist["kb_invalidated"] == 0
        assert checklist["status"] == "drift"