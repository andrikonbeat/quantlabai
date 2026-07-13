"""Tests for the Knowledge Store — directory init, indexing, format validation."""

import warnings
from pathlib import Path

import pytest
import yaml

from quantlab.knowledge.store import KNOWLEDGE_DIRS, KnowledgeStore, FormatWarning


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
        assert index["_version"] == "1"

    def test_missing_index_is_rebuilt(self, tmp_path: Path) -> None:
        """If index.yaml doesn't exist, read_index rebuilds it."""
        root = tmp_path / "knowledge"
        store = KnowledgeStore(root)
        store.initialize()

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
