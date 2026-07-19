"""Knowledge Store — filesystem Knowledge Lake manager.

Manages the Knowledge Lake directory structure: a filesystem-first,
Git-versioned research artifact repository. Provides path conventions,
directory initialisation, and basic metadata indexing using open,
human-readable formats.

Directory layout::

    knowledge/
    ├── index.yaml            # auto-generated metadata index
    ├── raw/                  # raw/unprocessed research artifacts
    ├── structured/           # cleaned, structured data (JSON, Parquet)
    ├── graph/                # relationship graphs and knowledge maps
    ├── embeddings/           # vector embeddings and model artifacts
    ├── datasets/             # curated, versioned datasets
    └── pipeline-runs/        # pipeline execution history (YAML per run)
"""

from __future__ import annotations

import hashlib
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from quantlab.tools.exceptions import ParseError

# ── Constants ─────────────────────────────────────────────────────────────────

KNOWLEDGE_DIRS = ["raw", "structured", "graph", "embeddings", "datasets", "pipeline-runs"]

ALLOWED_EXTENSIONS = {".yaml", ".yml", ".json", ".csv", ".parquet"}

INDEX_FILENAME = "index.yaml"

GITKEEP_FILENAME = ".gitkeep"

# File size limit for indexing (500 MB)
MAX_INDEX_SIZE = 500 * 1024 * 1024

PIPELINE_RUNS_DIR = "pipeline-runs"


# ── Models ────────────────────────────────────────────────────────────────────


class IndexEntry:
    """Metadata for a single file in the Knowledge Lake."""

    def __init__(
        self,
        path: str,
        size: int,
        sha256: str,
        created: str,
        tags: list[str] | None = None,
        metrics: dict | None = None,
        linked_campaigns: list[str] | None = None,
    ) -> None:
        self.path = path
        self.size = size
        self.sha256 = sha256
        self.created = created
        self.tags = tags or []
        self.metrics = metrics or {}
        self.linked_campaigns = linked_campaigns or []

    def to_dict(self) -> dict[str, object]:
        d = {
            "size": self.size,
            "sha256": self.sha256,
            "created": self.created,
        }
        if self.tags:
            d["tags"] = self.tags
        if self.metrics:
            d["metrics"] = self.metrics
        if self.linked_campaigns:
            d["linked_campaigns"] = self.linked_campaigns
        return d


class FormatWarning(UserWarning):
    """Warning raised when a file uses a non-standard format."""


# ── KnowledgeStore ────────────────────────────────────────────────────────────


class KnowledgeStore:
    """Manages the Knowledge Lake directory structure and metadata.

    Usage::

        store = KnowledgeStore(root=Path("knowledge"))
        store.initialize()
        store.rebuild_index()
        warnings = store.validate_formats()
    """

    def __init__(self, root: str | Path = "knowledge") -> None:
        self.root = Path(root).resolve()

    # ── Initialisation ─────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Create the 5-directory Knowledge Lake skeleton.

        Creates ``knowledge/`` and all 5 subdirectories if they do not
        exist. Each directory receives a ``.gitkeep`` marker file.

        Re-initialisation on an existing structure is **idempotent**:
        no existing files are modified or deleted, and no error is raised.
        """
        self.root.mkdir(parents=True, exist_ok=True)

        for dir_name in KNOWLEDGE_DIRS:
            dir_path = self.root / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            gitkeep = dir_path / GITKEEP_FILENAME
            if not gitkeep.exists():
                gitkeep.write_text("", encoding="utf-8")

    # ── Pipeline Run History ───────────────────────────────────────────────────────

    def _pipeline_runs_dir(self) -> Path:
        """Get the pipeline runs directory, creating it if needed."""
        runs_dir = self.root / PIPELINE_RUNS_DIR
        runs_dir.mkdir(parents=True, exist_ok=True)
        return runs_dir

    def save_pipeline_run(self, run: "PipelineRun") -> str:
        """Save a pipeline run to the Knowledge Lake.

        Args:
            run: PipelineRun object to persist.

        Returns:
            The run_id of the saved run.
        """
        import yaml

        runs_dir = self._pipeline_runs_dir()
        filename = f"{run.run_id}.yaml"
        filepath = runs_dir / filename

        data = run.to_dict()
        filepath.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        return run.run_id

    def load_pipeline_runs(
        self, limit: int = 10, status: str | None = None
    ) -> list["PipelineRun"]:
        """Load pipeline runs from the Knowledge Lake.

        Args:
            limit: Maximum number of runs to return (most recent first).
            status: Optional filter by status (pending, running, completed, failed, skipped).

        Returns:
            List of PipelineRun objects, sorted by start time descending.
        """
        import yaml

        from quantlab.pipeline.models import PipelineRun, StageStatus

        runs_dir = self._pipeline_runs_dir()
        if not runs_dir.exists():
            return []

        runs = []
        for filepath in sorted(runs_dir.glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                raw = filepath.read_text(encoding="utf-8")
                data = yaml.safe_load(raw)
                if not isinstance(data, dict):
                    continue

                # Filter by status if specified
                if status and data.get("status") != status:
                    continue

                run = PipelineRun.from_dict(data)
                runs.append(run)

                if len(runs) >= limit:
                    break
            except (yaml.YAMLError, OSError, KeyError, ValueError):
                # Skip corrupted files
                continue

        return runs

    def get_pipeline_run(self, run_id: str) -> "PipelineRun | None":
        """Load a single pipeline run by ID.

        Args:
            run_id: The run identifier.

        Returns:
            PipelineRun object or None if not found.
        """
        import yaml

        from quantlab.pipeline.models import PipelineRun

        runs_dir = self._pipeline_runs_dir()
        filepath = runs_dir / f"{run_id}.yaml"

        if not filepath.exists():
            return None

        try:
            raw = filepath.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            return PipelineRun.from_dict(data)
        except (yaml.YAMLError, OSError, KeyError, ValueError):
            return None

    # ── Indexing ───────────────────────────────────────────────────────────────

    def rebuild_index(self) -> dict[str, dict[str, object]]:
        """Scan the Knowledge Lake and regenerate ``index.yaml``.

        Walks all directories, computes SHA-256 hashes and sizes
        for every file (skipping ``.gitkeep`` and ``index.yaml``),
        and writes a human-readable YAML index.

        Corrupted or missing index files are silently rebuilt — the
        filesystem state is always the source of truth.

        Returns:
            The index data as a nested dict.
        """
        directories: dict[str, dict[str, object]] = {}
        now_iso = datetime.now(timezone.utc).isoformat()

        for dir_name in KNOWLEDGE_DIRS:
            dir_path = self.root / dir_name
            if not dir_path.exists():
                continue

            entries: dict[str, object] = {}
            for file_path in sorted(dir_path.iterdir()):
                if not file_path.is_file():
                    continue
                if file_path.name in (GITKEEP_FILENAME, INDEX_FILENAME):
                    continue

                rel = str(file_path.relative_to(self.root))
                stat = file_path.stat()
                entries[rel] = {
                    "size": stat.st_size,
                    "sha256": self._hash_file(file_path),
                    "created": now_iso,
                }

            if entries:
                directories[dir_name] = entries

        # Build base index dict
        doc: dict[str, object] = {
            "_generated": now_iso,
            "_version": "2",
            "directories": directories,
        }

        # Enhance with metrics/tags via Indexer (if available)
        try:
            from quantlab.knowledge.indexer import Indexer
            indexer = Indexer(self)
            doc = indexer.build_index(existing_index=doc)
        except Exception:
            pass  # Non-critical enhancement; plain scan is sufficient

        # Write index.yaml
        index_path = self.root / INDEX_FILENAME
        index_path.write_text(
            yaml.dump(doc, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        return doc

    def read_index(self) -> dict[str, object]:
        """Read the current ``index.yaml``.

        If the index file is corrupted or does not exist, it is
        automatically rebuilt from the filesystem state.

        Returns:
            The index data as a dict.
        """
        index_path = self.root / INDEX_FILENAME

        if not index_path.exists():
            return self.rebuild_index()

        try:
            raw = index_path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            if not isinstance(data, dict):
                return self.rebuild_index()
            return data
        except (yaml.YAMLError, OSError):
            return self.rebuild_index()

    # ── Tagging and Linking ─────────────────────────────────────────────────────

    def tag(self, campaign_id: str, tags: dict[str, str] | list[str]) -> bool:
        """Add tags to a campaign.

        Args:
            campaign_id: Campaign identifier (directory name)
            tags: Dict of key:value tags or list of tag names

        Returns:
            True if campaign was found and tagged.
        """
        indexer = Indexer(self)
        if isinstance(tags, list):
            tag_list = tags
        else:
            tag_list = [f"{k}={v}" for k, v in tags.items()]

        return indexer.tag_campaign(campaign_id, tag_list)

    def get_tags(self, campaign_id: str) -> list[str]:
        """Get all tags for a campaign."""
        index = self.read_index()
        for dir_name in ["results", "campaigns"]:
            if dir_name not in index.get("directories", {}):
                continue
            for rel_path, info in index["directories"][dir_name].items():
                if info.get("path", "").endswith(campaign_id) or Path(info.get("path", "")).stem == campaign_id:
                    return info.get("tags", [])
        return []

    def link(self, parent_id: str, child_ids: list[str]) -> bool:
        """Create parent-child relationships between campaigns."""
        indexer = Indexer(self)
        return indexer.link_campaigns(parent_id, child_ids)

    def get_links(self, campaign_id: str) -> dict[str, list[str]]:
        """Get parent and child links for a campaign."""
        index = self.read_index()
        for dir_name in ["results", "campaigns"]:
            if dir_name not in index.get("directories", {}):
                continue
            for rel_path, info in index["directories"][dir_name].items():
                if Path(info.get("path", "")).stem == campaign_id:
                    linked = info.get("linked_campaigns", [])
                    return {"children": linked, "parents": []}
        return {"children": [], "parents": []}

    # ── Querying ────────────────────────────────────────────────────────────────

    def query(self, filters: dict | None = None):
        """Create a query builder for campaigns."""
        from quantlab.knowledge.query import QueryBuilder
        index = self.read_index()
        return QueryBuilder(index, self.root)

    # ── Format Validation ──────────────────────────────────────────────────────

    def validate_formats(self) -> list[str]:
        """Check all files for standard format compliance.

        Non-conforming files generate a warning and are listed in the
        returned list. Only the following formats are allowed:
        ``.yaml``, ``.yml``, ``.json``, ``.csv``, ``.parquet``.

        Returns:
            A list of warning messages for non-standard files.
        """
        warnings_list: list[str] = []

        for dir_name in KNOWLEDGE_DIRS:
            dir_path = self.root / dir_name
            if not dir_path.exists():
                continue

            for file_path in dir_path.iterdir():
                if not file_path.is_file():
                    continue
                if file_path.name == GITKEEP_FILENAME:
                    continue

                ext = file_path.suffix.lower()
                if ext not in ALLOWED_EXTENSIONS:
                    msg = (
                        f"Non-standard format '{ext}' for file "
                        f"'{file_path.relative_to(self.root)}' in "
                        f"'{dir_name}/'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
                    )
                    warnings.warn(msg, FormatWarning, stacklevel=2)
                    warnings_list.append(msg)

        return warnings_list

    # ── Path Resolution ────────────────────────────────────────────────────────

    def resolve(self, relative_path: str) -> Path:
        """Resolve a relative Knowledge Lake path.

        Uses ``pathlib`` for cross-platform separator handling
        (forward slash on POSIX, backslash on Windows).

        Args:
            relative_path: A path relative to the Knowledge Lake root
                (e.g., ``"raw/backtest-1.csv"``).

        Returns:
            The absolute, resolved path.
        """
        return (self.root / relative_path).resolve()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _write_index(self, index: dict) -> None:
        """Write the index dict to index.yaml."""
        index_path = self.root / INDEX_FILENAME
        index_path.write_text(
            yaml.dump(index, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
