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

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from quantlab.data.market.models import Bar
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
        assert data["_version"] == "5"

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


class TestKnowledgeStoreV5RebuildKeys:
    """Index v5 migration acceptance (G6, knowledge-store delta).

    Spec "Index v5 Migration Acceptance": a stale v4 index MUST upgrade to 5
    with the v5 keys present after rebuild; "Seed writes dataset files":
    datasets/ files MUST be recorded by ``rebuild_index``.
    """

    def _write_v4_index(self, store: KnowledgeStore) -> None:
        (store.root / "index.yaml").write_text(
            yaml.dump(
                {
                    "_version": "4",
                    "_generated": "2026-01-01T00:00:00",
                    "directories": {},
                    "agent_memory": {},
                    "kb_parameters": {},
                    "version_events": {},
                }
            ),
            encoding="utf-8",
        )

    def test_rebuild_index_emits_v5_keys_and_upgrades_stale_v4(
        self, tmp_path: Path
    ) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()
        self._write_v4_index(store)

        index = store.rebuild_index()

        assert index["_version"] == "5"
        for key in ("campaign_phases", "parameter_matrix", "guardian_feedback", "maintenance"):
            assert key in index

        on_disk = yaml.safe_load(
            (store.root / "index.yaml").read_text(encoding="utf-8")
        )
        assert on_disk["_version"] == "5"
        for key in ("campaign_phases", "parameter_matrix", "guardian_feedback", "maintenance"):
            assert key in on_disk

    def test_read_index_upgrades_stale_v4_and_preserves_legacy_keys(
        self, tmp_path: Path
    ) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()
        legacy = {
            "_version": "4",
            "_generated": "2026-01-01T00:00:00",
            "directories": {"raw": {"raw/data.csv": {"size": 100}}},
            "agent_memory": {},
            "kb_parameters": {"structured/sqx-kb/v1/parameters/tab/p.yaml": {}},
            "version_events": {"structured/sqx-version/1->2/checklist.yaml": {}},
        }
        (store.root / "index.yaml").write_text(
            yaml.dump(legacy), encoding="utf-8"
        )

        index = store.read_index()

        assert index["_version"] == "5"
        assert index["directories"]["raw"]["raw/data.csv"]["size"] == 100
        assert "kb_parameters" in index
        assert "version_events" in index
        for key in ("campaign_phases", "parameter_matrix", "guardian_feedback", "maintenance"):
            assert key in index

    def test_rebuild_index_records_dataset_files(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()
        dataset_path = store.root / "datasets" / "EURUSD" / "M1.csv"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_path.write_text(
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T00:00:00+00:00,1.0,1.1,0.9,1.05,100.0\n",
            encoding="utf-8",
        )

        index = store.rebuild_index()

        assert "datasets" in index["directories"]
        assert "datasets/EURUSD/M1.csv" in index["directories"]["datasets"]

    def test_rebuild_index_records_nested_campaign_phase_envelope(
        self, tmp_path: Path
    ) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()
        envelope = store.resolve("campaign-phases/camp-001/research/envelope.json")
        envelope.parent.mkdir(parents=True, exist_ok=True)
        envelope.write_text(
            json.dumps({"campaign_id": "camp-001", "phase": "research"}),
            encoding="utf-8",
        )

        index = store.rebuild_index()

        assert "campaign-phases" in index["directories"]
        assert (
            "campaign-phases/camp-001/research/envelope.json"
            in index["directories"]["campaign-phases"]
        )


class TestDatasetCache:
    """KnowledgeStore.cache_dataset — the G6 datasets cache helper."""

    @pytest.mark.asyncio
    async def test_cache_dataset_writes_csv_and_returns_rel_path(
        self, tmp_path: Path
    ) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()
        bars = [
            Bar(
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                open=1.0, high=1.1, low=0.9, close=1.05, volume=100.0,
            ),
            Bar(
                timestamp=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
                open=1.05, high=1.15, low=1.0, close=1.10, volume=120.0,
            ),
        ]

        rel = await store.cache_dataset("EURUSD", "M1", bars)

        assert rel == "datasets/EURUSD/M1.csv"
        csv_path = store.root / "datasets" / "EURUSD" / "M1.csv"
        assert csv_path.is_file()
        lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0] == "timestamp,open,high,low,close,volume"
        assert len(lines) == 3
        assert lines[1].startswith("2026-01-01T00:00:00")

    @pytest.mark.asyncio
    async def test_cache_dataset_overwrites_on_reseed(self, tmp_path: Path) -> None:
        store = KnowledgeStore(root=tmp_path / "knowledge")
        store.initialize()
        bar = [
            Bar(
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                open=1.0, high=1.1, low=0.9, close=1.05, volume=100.0,
            )
        ]
        await store.cache_dataset("EURUSD", "M1", bar)
        await store.cache_dataset("EURUSD", "M1", bar)

        csv_path = store.root / "datasets" / "EURUSD" / "M1.csv"
        lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2  # header + 1 row — overwrite, not append


def _ohlc_args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    """Build a cmd_kb_seed_ohlc Namespace against a hermetic tmp lake."""
    from quantlab.cli.sq_commands import (
        DEFAULT_SEED_SYMBOLS,
        DEFAULT_SEED_TIMEFRAMES,
    )

    defaults: dict[str, object] = {
        "knowledge_root": str(tmp_path / "lake"),
        "symbols": list(DEFAULT_SEED_SYMBOLS),
        "timeframes": list(DEFAULT_SEED_TIMEFRAMES),
        "jforex_state_dir": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class _FakeOhlcSource:
    """Hermetic data source seam for the seed command (mirrors cmd_kb_seed)."""

    def __init__(self, bars_by_key: dict[tuple[str, str], list[Bar]]) -> None:
        self.bars_by_key = bars_by_key
        self.requests: list[tuple[str, str]] = []

    def fetch_bars(self, symbol: str, timeframe: str) -> list[Bar]:
        self.requests.append((symbol, timeframe))
        return self.bars_by_key.get((symbol, timeframe), [])


def _sample_bars(count: int = 2) -> list[Bar]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Bar(
            timestamp=base + timedelta(minutes=i),
            open=1.0 + i, high=1.1 + i, low=0.9 + i, close=1.05 + i,
            volume=100.0 + i,
        )
        for i in range(count)
    ]


class TestSeedOhlc:
    """G6 seed-ohlc: EURUSD default (Q3), M1/M5/H1, env-gap names dependency."""

    def test_default_symbol_and_timeframes_are_eurusd_m1_m5_h1(self) -> None:
        from quantlab.cli.sq_commands import (
            DEFAULT_SEED_SYMBOLS,
            DEFAULT_SEED_TIMEFRAMES,
        )

        assert DEFAULT_SEED_SYMBOLS == ("EURUSD",)
        assert DEFAULT_SEED_TIMEFRAMES == ("M1", "M5", "H1")

    @pytest.mark.asyncio
    async def test_seed_ohlc_writes_datasets_and_rebuilds_index(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quantlab.cli.sq_commands import cmd_kb_seed_ohlc

        bars = _sample_bars()
        source = _FakeOhlcSource(
            {(sym, tf): bars for sym in ("EURUSD",) for tf in ("M1", "M5", "H1")}
        )
        monkeypatch.setattr(
            "quantlab.cli.sq_commands._DEFAULT_OHLC_SOURCE_FACTORY",
            lambda root, **kw: source,
        )

        code = await cmd_kb_seed_ohlc(_ohlc_args(tmp_path))

        assert code == 0
        lake = tmp_path / "lake"
        for tf in ("M1", "M5", "H1"):
            csv_path = lake / "datasets" / "EURUSD" / f"{tf}.csv"
            assert csv_path.is_file()
            lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
            assert lines[0] == "timestamp,open,high,low,close,volume"
            assert len(lines) == 3
        assert source.requests == [
            ("EURUSD", "M1"), ("EURUSD", "M5"), ("EURUSD", "H1"),
        ]
        index = yaml.safe_load((lake / "index.yaml").read_text(encoding="utf-8"))
        assert index["_version"] == "5"
        datasets = index["directories"]["datasets"]
        for tf in ("M1", "M5", "H1"):
            assert f"datasets/EURUSD/{tf}.csv" in datasets

    @pytest.mark.asyncio
    async def test_seed_ohlc_env_gap_exits_one_and_names_dependency(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        from quantlab.cli.sq_commands import cmd_kb_seed_ohlc

        monkeypatch.delenv("SQCLI_PATH", raising=False)
        monkeypatch.delenv("SQX_INSTALL_PATH", raising=False)

        code = await cmd_kb_seed_ohlc(_ohlc_args(tmp_path))

        assert code == 1
        err = capsys.readouterr().err
        assert "JForex" in err
        assert "SQCLI" in err
        assert "no dataset files written" in err

    @pytest.mark.asyncio
    async def test_seed_ohlc_partial_gap_reports_written_and_skipped(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        from quantlab.cli.sq_commands import cmd_kb_seed_ohlc

        bars = _sample_bars()
        source = _FakeOhlcSource({("EURUSD", "M1"): bars})
        monkeypatch.setattr(
            "quantlab.cli.sq_commands._DEFAULT_OHLC_SOURCE_FACTORY",
            lambda root, **kw: source,
        )

        code = await cmd_kb_seed_ohlc(_ohlc_args(tmp_path))

        assert code == 0
        assert (tmp_path / "lake" / "datasets" / "EURUSD" / "M1.csv").is_file()
        out = capsys.readouterr().out
        assert "datasets/EURUSD/M1.csv" in out
        assert "EURUSD M5" in out
        assert "EURUSD H1" in out

    def test_seed_ohlc_registered_in_cli(self, tmp_path: Path) -> None:
        from quantlab.cli.main import build_parser
        from quantlab.cli.sq_commands import cmd_kb_seed_ohlc

        parser = build_parser()
        args = parser.parse_args(
            ["sqx", "kb", "seed-ohlc", "--knowledge-root", str(tmp_path / "lake")]
        )
        assert args.func is cmd_kb_seed_ohlc
