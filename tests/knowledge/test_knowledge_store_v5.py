"""Tests for QuantLab KnowledgeStore v5 schema changes.

Covers:
- KNOWLEDGE_DIRS includes 4 new directories
- STRUCTURED_SUB_LAYOUTS includes 4 new template paths
- initialize() creates all new directories
- index.yaml version is "5" after rebuild + read
- _upgrade_index() upgrades legacy v1/v2/v3/v4 indexes to v5
- Legacy data remains readable after upgrade
- KnowledgeStore can save/load campaign-phase artifacts
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from quantlab.knowledge.store import (
    KNOWLEDGE_DIRS,
    STRUCTURED_SUB_LAYOUTS,
    KnowledgeStore,
)


class TestKnowledgeStoreV5Constants:
    """Verify v5 constants include new directories and layouts."""

    def test_knowledge_dirs_includes_new_directories(self) -> None:
        new_dirs = {"campaign-phases", "parameter-matrix", "guardian-feedback", "maintenance"}
        assert new_dirs.issubset(set(KNOWLEDGE_DIRS))

    def test_structured_sub_layouts_includes_new_templates(self) -> None:
        new_layouts = {
            "campaign-phases/_template",
            "parameter-matrix/_template",
            "guardian-feedback/_template",
            "maintenance/_template",
        }
        assert new_layouts.issubset(set(STRUCTURED_SUB_LAYOUTS))


class TestKnowledgeStoreV5Initialize:
    """Verify initialize() creates v5 directory structure."""

    def test_initialize_creates_all_new_directories(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()

        for dir_name in KNOWLEDGE_DIRS:
            assert (tmp_path / "knowledge" / dir_name).is_dir()

    def test_initialize_creates_gitkeep_in_new_directories(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()

        for dir_name in ["campaign-phases", "parameter-matrix", "guardian-feedback", "maintenance"]:
            gitkeep = tmp_path / "knowledge" / dir_name / ".gitkeep"
            assert gitkeep.is_file()

    def test_initialize_rebuild_creates_v5_index(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()
        store.rebuild_index()

        index_path = tmp_path / "knowledge" / "index.yaml"
        assert index_path.is_file()

        raw = index_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        assert data["_version"] == "4"

        index = store.read_index()
        assert index["_version"] == "5"

    def test_initialize_idempotent(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()
        store.initialize()

        for dir_name in KNOWLEDGE_DIRS:
            assert (tmp_path / "knowledge" / dir_name).is_dir()


class TestKnowledgeStoreV5Upgrade:
    """Verify _upgrade_index() migrates legacy schemas to v5."""

    def test_upgrade_v4_to_v5_adds_new_keys(self) -> None:
        legacy = {
            "_version": "4",
            "_generated": "2026-01-01T00:00:00",
            "directories": {"raw": {}},
            "agent_memory": {},
            "kb_parameters": {},
            "version_events": {},
        }
        upgraded = KnowledgeStore._upgrade_index(legacy)
        assert upgraded["_version"] == "5"
        assert "campaign_phases" in upgraded
        assert "parameter_matrix" in upgraded
        assert "guardian_feedback" in upgraded
        assert "maintenance" in upgraded

    def test_upgrade_v3_to_v5_adds_all_new_keys(self) -> None:
        legacy = {"_version": "3", "_generated": "2026-01-01T00:00:00"}
        upgraded = KnowledgeStore._upgrade_index(legacy)
        assert upgraded["_version"] == "5"
        assert upgraded["campaign_phases"] == {}
        assert upgraded["parameter_matrix"] == {}
        assert upgraded["guardian_feedback"] == {}
        assert upgraded["maintenance"] == {}

    def test_upgrade_v2_to_v5_adds_new_keys(self) -> None:
        legacy = {
            "_version": "2",
            "_generated": "2026-01-01T00:00:00",
            "directories": {"agent-memory": {"a/b/memory.yaml": {}}},
        }
        upgraded = KnowledgeStore._upgrade_index(legacy)
        assert upgraded["_version"] == "5"
        assert "campaign_phases" in upgraded
        assert "parameter_matrix" in upgraded
        assert "guardian_feedback" in upgraded
        assert "maintenance" in upgraded

    def test_upgrade_v1_to_v5_adds_all_keys(self) -> None:
        legacy = {"_version": "1", "_generated": "2026-01-01T00:00:00"}
        upgraded = KnowledgeStore._upgrade_index(legacy)
        assert upgraded["_version"] == "5"
        assert upgraded["campaign_phases"] == {}
        assert upgraded["parameter_matrix"] == {}
        assert upgraded["guardian_feedback"] == {}
        assert upgraded["maintenance"] == {}

    def test_upgrade_preserves_legacy_data(self) -> None:
        legacy = {
            "_version": "4",
            "_generated": "2026-01-01T00:00:00",
            "directories": {"raw": {"raw/data.csv": {"size": 100}}},
            "agent_memory": {"agent-memory/a/b/memory.yaml": {"agent_name": "a"}},
            "kb_parameters": {"structured/sqx-kb/v1/parameters/tab/p.yaml": {}},
            "version_events": {"structured/sqx-version/1->2/checklist.yaml": {}},
        }
        upgraded = KnowledgeStore._upgrade_index(legacy)
        assert upgraded["_version"] == "5"
        assert upgraded["directories"]["raw"]["raw/data.csv"]["size"] == 100
        assert upgraded["agent_memory"]["agent-memory/a/b/memory.yaml"]["agent_name"] == "a"
        assert "campaign_phases" in upgraded
        assert "parameter_matrix" in upgraded
        assert "guardian_feedback" in upgraded
        assert "maintenance" in upgraded

    def test_upgrade_v5_is_noop(self) -> None:
        current = {
            "_version": "5",
            "_generated": "2026-01-01T00:00:00",
            "campaign_phases": {"cp": 1},
        }
        upgraded = KnowledgeStore._upgrade_index(current)
        assert upgraded["_version"] == "5"
        assert upgraded["campaign_phases"] == {"cp": 1}


class TestKnowledgeStoreV5ReadIndex:
    """Verify read_index() transparently upgrades legacy indexes."""

    def test_read_index_upgrades_v4_file(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()

        index_path = tmp_path / "knowledge" / "index.yaml"
        index_path.write_text(
            yaml.dump({"_version": "4", "_generated": "2026-01-01T00:00:00"}),
            encoding="utf-8",
        )

        index = store.read_index()
        assert index["_version"] == "5"
        assert "campaign_phases" in index
        assert "parameter_matrix" in index
        assert "guardian_feedback" in index
        assert "maintenance" in index

    def test_read_index_upgrades_v1_file(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()

        index_path = tmp_path / "knowledge" / "index.yaml"
        index_path.write_text(
            yaml.dump({"_version": "1", "_generated": "2026-01-01T00:00:00"}),
            encoding="utf-8",
        )

        index = store.read_index()
        assert index["_version"] == "5"


class TestKnowledgeStoreV5Artifacts:
    """Verify campaign-phase artifacts can be saved and loaded."""

    def test_save_and_load_campaign_phase_artifact(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()

        phase_data = {
            "campaign_id": "camp-001",
            "phase": "research",
            "status": "completed",
            "started_at": "2026-01-01T00:00:00",
            "completed_at": "2026-01-01T01:00:00",
            "duration": 3600.0,
            "artifacts": ["artifact-a.yaml"],
            "next_gate": "hypothesis",
            "gate_decision": "passed",
        }

        phase_path = store.resolve("campaign-phases/camp-001-research.yaml")
        phase_path.write_text(
            yaml.dump(phase_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        loaded = yaml.safe_load(phase_path.read_text(encoding="utf-8"))
        assert loaded["campaign_id"] == "camp-001"
        assert loaded["phase"] == "research"
        assert loaded["status"] == "completed"

    def test_campaign_phase_indexed_after_rebuild(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()

        phase_path = store.resolve("campaign-phases/camp-001.yaml")
        phase_path.write_text(
            yaml.dump({"campaign_id": "camp-001", "phase": "research", "status": "completed"}),
            encoding="utf-8",
        )

        index = store.rebuild_index()
        assert "campaign-phases" in index["directories"]
        assert any("camp-001.yaml" in k for k in index["directories"]["campaign-phases"])


class TestFailedPhaseEnvelope:
    """full-campaign-lifecycle REQ-3: a failed phase envelope is durable.

    Spec scenarios:
    - GIVEN a failed phase THEN the envelope records status "failed", the
      artifacts list includes the error log, and the next-phase gate is HOLD.
    """

    def test_failed_envelope_records_status_error_log_and_hold_gate(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()

        path = store.save_phase_envelope(
            "camp-001",
            "retest",
            status="failed",
            artifacts=["campaign-phases/camp-001/retest/error.log"],
            error="sqcli timeout after 120s",
            next_gate="HOLD",
        )

        envelope_path = Path(path)
        assert envelope_path.is_file()
        raw = json.loads(envelope_path.read_text(encoding="utf-8"))
        assert raw["campaign_id"] == "camp-001"
        assert raw["phase"] == "retest"
        assert raw["status"] == "failed"
        assert raw["error"] == "sqcli timeout after 120s"
        assert any("error.log" in artifact for artifact in raw["artifacts"])
        assert raw["next_gate"] == "HOLD"

    def test_successful_envelope_records_gate_decision(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()

        path = store.save_phase_envelope(
            "camp-002",
            "archive",
            status="completed",
            artifacts=["campaign-phases/camp-002/archive/bundle.json"],
            next_gate="live-ops",
            gate_decision="APPROVE",
        )

        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        assert raw["status"] == "completed"
        assert raw["gate_decision"] == "APPROVE"
        assert raw["next_gate"] == "live-ops"
