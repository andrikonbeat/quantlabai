"""Tests for the Knowledge Store — directory init, indexing, format validation."""

import warnings
from pathlib import Path

import pytest
import yaml

from quantlab.knowledge.indexer import Indexer
from quantlab.knowledge.store import (
    STRUCTURED_SUB_LAYOUTS,
    KNOWLEDGE_DIRS,
    KnowledgeStore,
    FormatWarning,
)


class TestKnowledgeStoreInit:
    """Tests for ``KnowledgeStore.initialize()``."""

    def test_fresh_initialization_creates_all_directories(self, tmp_path: Path) -> None:
        """GIVEN a knowledge/ path that does not exist
        WHEN the system initializes the Knowledge Lake
        THEN 5 subdirectories are created each with a .gitkeep marker file.
        """
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        assert root.exists()
        assert root.is_dir()

        for dir_name in KNOWLEDGE_DIRS:
            dir_path = root / dir_name
            assert dir_path.exists(), f"Directory '{dir_name}' was not created"
            assert dir_path.is_dir(), f"'{dir_name}' is not a directory"
            assert (dir_path / ".gitkeep").exists(), f"Missing .gitkeep in '{dir_name}'"

    def test_reinitialization_is_idempotent(self, tmp_path: Path) -> None:
        """GIVEN an already-initialized Knowledge Lake with files present
        WHEN the system initializes again
        THEN no existing files are modified or deleted, and no error is raised.
        """
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        # Add a file to one of the directories
        test_file = root / "raw" / "test.txt"
        test_file.write_text("hello", encoding="utf-8")

        # Re-initialize
        store.initialize()

        # The test file should still exist
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "hello"

        # All directories still exist
        for dir_name in KNOWLEDGE_DIRS:
            assert (root / dir_name).exists()


class TestKnowledgeStoreIndex:
    """Tests for ``KnowledgeStore.rebuild_index()`` and ``read_index()``."""

    def test_index_updates_after_file_addition(self, tmp_path: Path) -> None:
        """GIVEN an initialized Knowledge Lake with an index
        WHEN a file is added to raw/ and the index is rebuilt
        THEN the index contains the new file's path, size, and SHA-256 hash.
        """
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        # Add a test file
        test_file = root / "raw" / "backtest-1.csv"
        test_file.write_text("time,equity\n2024-01-01,100000\n", encoding="utf-8")

        # Rebuild index
        index = store.rebuild_index()

        # Check the index structure
        assert "directories" in index
        assert "raw" in index["directories"]
        entries = index["directories"]["raw"]
        assert len(entries) == 1

        # The key should be the relative path
        key = "raw/backtest-1.csv"
        assert key in entries
        assert entries[key]["size"] > 0
        assert "sha256" in entries[key]
        assert "created" in entries[key]

    def test_corrupted_index_is_recoverable(self, tmp_path: Path) -> None:
        """GIVEN a Knowledge Lake with a corrupted index.yaml
        WHEN the system attempts to read the index
        THEN the corruption is detected and a new index is rebuilt.
        """
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        # Write a corrupted index
        index_path = root / "index.yaml"
        index_path.write_text("{broken: yaml: [unclosed", encoding="utf-8")

        # Read should auto-rebuild
        index = store.read_index()

        # Should have a valid structure
        assert "directories" in index
        assert "_generated" in index
        assert index["_version"] == "5"  # Post-Indexer version (REQ-403)

    def test_missing_index_is_rebuilt(self, tmp_path: Path) -> None:
        """If index.yaml doesn't exist, read_index rebuilds it."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()
        store.rebuild_index()  # create initial index

        # Remove the index
        (root / "index.yaml").unlink()

        # Read should rebuild
        index = store.read_index()
        assert "directories" in index


class TestKnowledgeStoreFormatValidation:
    """Tests for ``KnowledgeStore.validate_formats()``."""

    def test_allowed_formats_pass_validation(self, tmp_path: Path) -> None:
        """GIVEN .yaml, .json, .csv, and .parquet files
        WHEN the system validates file conventions
        THEN no warnings or errors are raised.
        """
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        # Add allowed format files
        (root / "raw" / "data.yaml").write_text("key: value\n", encoding="utf-8")
        (root / "structured" / "data.json").write_text('{"key": "value"}\n', encoding="utf-8")
        (root / "raw" / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")

        warnings_list = store.validate_formats()
        assert warnings_list == []

    def test_non_conforming_file_logs_warning(self, tmp_path: Path) -> None:
        """GIVEN a .docx file placed in structured/
        WHEN the system validates file conventions
        THEN a warning is logged noting the non-standard format.
        """
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        # Add a non-standard file
        (root / "structured" / "notes.docx").write_bytes(b"fake docx content")

        warnings_list = store.validate_formats()
        assert len(warnings_list) >= 1
        assert any(".docx" in w for w in warnings_list)

    def test_warning_emitted_via_warnings_module(self, tmp_path: Path) -> None:
        """The non-standard format warning is also emitted via warnings.warn."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        (root / "graph" / "graph.png").write_bytes(b"fake png")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            store.validate_formats()
            assert len(w) >= 1
            assert any(issubclass(category, FormatWarning) for category in [x.category for x in w])

    def test_empty_directory_no_warnings(self, tmp_path: Path) -> None:
        """An empty knowledge lake produces no format warnings."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        warnings_list = store.validate_formats()
        assert warnings_list == []


class TestKnowledgeStorePathResolution:
    """Tests for ``KnowledgeStore.resolve()``."""

    def test_linux_paths_use_forward_slashes(self, tmp_path: Path) -> None:
        """GIVEN a Knowledge Lake on Linux
        WHEN resolving raw/backtest-1.csv
        THEN the resolved path uses forward slashes.
        """
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)

        resolved = store.resolve("raw/backtest-1.csv")
        assert str(resolved).endswith("knowledge/raw/backtest-1.csv")

    def test_resolve_absolute_path(self, tmp_path: Path) -> None:
        """Resolved path should be absolute."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)

        resolved = store.resolve("raw/backtest-1.csv")
        assert resolved.is_absolute()


class TestKnowledgeStoreInitBase:
    """Init without filesystem — just test constructor."""

    def test_default_root_is_knowledge(self) -> None:
        store = KnowledgeStore()
        assert str(store.root).endswith("knowledge")


class TestKnowledgeStoreReconciledLayout:
    """REQ-101/REQ-402: structured/ hosts the reconciled sub-layouts."""

    def test_fresh_init_creates_all_structured_sub_layouts(self, tmp_path: Path) -> None:
        """GIVEN a fresh knowledge/ path
        WHEN the system initializes the Knowledge Lake
        THEN every canonical structured sub-layout skeleton exists with .gitkeep."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        assert len(STRUCTURED_SUB_LAYOUTS) == 7
        for rel in STRUCTURED_SUB_LAYOUTS:
            sub = root / rel
            assert sub.is_dir(), f"sub-layout {rel} was not created"
            assert (sub / ".gitkeep").exists(), f"missing .gitkeep in {rel}"

    def test_sub_layout_placeholder_names(self, tmp_path: Path) -> None:
        """The parametric segments use _template placeholders so the skeleton
        exists before any real campaign/version is known."""
        root = tmp_path / "knowledge"
        KnowledgeStore(root).initialize()

        assert (root / "structured/_template").is_dir()
        assert (root / "structured/sqx-kb/_template/parameters/_template").is_dir()
        assert (root / "structured/sqx-version/_template→_template").is_dir()

    def test_reinit_preserves_structured_content(self, tmp_path: Path) -> None:
        """Re-initialization must not touch files already inside structured/."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        keep = root / "structured/campaign-7/config.yaml"
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text("key: value\n", encoding="utf-8")

        store.initialize()  # idempotent re-init

        assert keep.read_text(encoding="utf-8") == "key: value\n"


class TestKnowledgeStoreIndexV5:
    """REQ-403: rebuild_index bumps to v5 and covers the reconciled areas."""

    def test_rebuild_index_is_v5_with_new_areas(self, tmp_path: Path) -> None:
        """GIVEN campaigns, agent-memory, and sqx-kb entries
        WHEN rebuild_index() runs
        THEN index.yaml is version 5 and includes entries for each area."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        # Seed a KB parameter file
        kb_param = root / "structured/sqx-kb/144.2953/parameters/Ranking/entry.yaml"
        kb_param.parent.mkdir(parents=True, exist_ok=True)
        kb_param.write_text("name: entry\n", encoding="utf-8")

        # Seed a version-event checklist
        checklist = root / "structured/sqx-version/144.2953→144.2954/checklist.yaml"
        checklist.parent.mkdir(parents=True, exist_ok=True)
        checklist.write_text("status: pending\n", encoding="utf-8")

        # Seed an agent memory entry
        store.store_agent_memory("research-director", "campaign-7", {"decision": "ok"})

        # Seed canonical campaign metrics
        metrics = root / "structured/campaign-7/metrics.yaml"
        metrics.parent.mkdir(parents=True, exist_ok=True)
        metrics.write_text("sharpe_ratio: 1.5\n", encoding="utf-8")

        index = store.rebuild_index()

        assert index["_version"] == "5"
        assert "kb_parameters" in index
        assert "version_events" in index
        assert "campaign_phases" in index
        assert "parameter_matrix" in index
        assert "guardian_feedback" in index
        assert "maintenance" in index
        assert any("sqx-kb" in key for key in index["kb_parameters"])
        assert any("sqx-version" in key for key in index["version_events"])
        assert "agent-memory/research-director/campaign-7/memory.yaml" in index["agent_memory"]
        assert index.get("campaigns", {}).get("campaign-7", {}).get("metrics", {}).get("sharpe_ratio") == 1.5

    def test_v1_index_readable_with_defaults(self, tmp_path: Path) -> None:
        """GIVEN an index.yaml of version 1
        WHEN read_index() runs
        THEN entries parse with defaults and no error (REQ-403)."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        (root / "index.yaml").write_text(
            yaml.dump(
                {
                    "_generated": "2024-01-01T00:00:00+00:00",
                    "_version": "1",
                    "directories": {"raw": {}},
                }
            ),
            encoding="utf-8",
        )

        index = store.read_index()

        assert index["_version"] == "5"
        assert "directories" in index
        assert index["kb_parameters"] == {}
        assert index["version_events"] == {}

    def test_v2_index_upgraded_to_v5(self, tmp_path: Path) -> None:
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        (root / "index.yaml").write_text(
            yaml.dump(
                {
                    "_generated": "2024-01-01T00:00:00+00:00",
                    "_version": "2",
                    "directories": {"agent-memory": {}},
                    "agent_memory": {},
                }
            ),
            encoding="utf-8",
        )

        index = store.read_index()

        assert index["_version"] == "5"
        assert index["kb_parameters"] == {}
        assert index["version_events"] == {}
        assert index["campaign_phases"] == {}
        assert index["parameter_matrix"] == {}
        assert index["guardian_feedback"] == {}
        assert index["maintenance"] == {}

    def test_v3_index_upgraded_to_v5(self, tmp_path: Path) -> None:
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        (root / "index.yaml").write_text(
            yaml.dump(
                {
                    "_generated": "2024-01-01T00:00:00+00:00",
                    "_version": "3",
                    "directories": {"raw": {}},
                    "agent_memory": {},
                }
            ),
            encoding="utf-8",
        )

        index = store.read_index()

        assert index["_version"] == "5"
        assert index["kb_parameters"] == {}
        assert index["version_events"] == {}
        assert index["campaign_phases"] == {}
        assert index["parameter_matrix"] == {}
        assert index["guardian_feedback"] == {}
        assert index["maintenance"] == {}


class TestIndexerReconciledRead:
    """D6/REQ-402: metrics from structured/{campaign_id}/metrics.yaml with
    legacy campaigns/ results/ stats/ read fallback."""

    def test_metrics_read_from_structured_campaign_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        metrics = root / "structured/campaign-9/metrics.yaml"
        metrics.parent.mkdir(parents=True, exist_ok=True)
        metrics.write_text("sharpe_ratio: 2.5\nprofit_factor: 1.9\n", encoding="utf-8")

        idx = Indexer(root).build_index()

        assert "campaign-9" in idx
        assert idx["campaign-9"]["metrics"]["sharpe_ratio"] == 2.5
        assert idx["campaign-9"]["metrics"]["profit_factor"] == 1.9

    def test_legacy_stats_fallback(self, tmp_path: Path) -> None:
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        stats = root / "stats"
        stats.mkdir(exist_ok=True)
        (stats / "legacy-camp.yaml").write_text("sharpe_ratio: 1.1\n", encoding="utf-8")

        idx = Indexer(root).build_index()

        assert idx["legacy-camp"]["metrics"]["sharpe_ratio"] == 1.1

    def test_legacy_results_nested_fallback(self, tmp_path: Path) -> None:
        """results/{campaign}/stats.yaml resolves the campaign from the dir."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        nested = root / "results/campaign-11/stats.yaml"
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_text("sharpe_ratio: 0.9\n", encoding="utf-8")

        idx = Indexer(root).build_index()

        assert idx["campaign-11"]["metrics"]["sharpe_ratio"] == 0.9

    def test_canonical_wins_over_legacy_fallback(self, tmp_path: Path) -> None:
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

        stats = root / "stats"
        stats.mkdir(exist_ok=True)
        (stats / "dup.yaml").write_text("sharpe_ratio: 0.5\n", encoding="utf-8")

        metrics = root / "structured/dup/metrics.yaml"
        metrics.parent.mkdir(parents=True, exist_ok=True)
        metrics.write_text("sharpe_ratio: 3.0\n", encoding="utf-8")

        idx = Indexer(root).build_index()

        assert idx["dup"]["metrics"]["sharpe_ratio"] == 3.0

