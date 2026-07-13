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
    └── datasets/             # curated, versioned datasets
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

KNOWLEDGE_DIRS = ["raw", "structured", "graph", "embeddings", "datasets"]

ALLOWED_EXTENSIONS = {".yaml", ".yml", ".json", ".csv", ".parquet"}

INDEX_FILENAME = "index.yaml"

GITKEEP_FILENAME = ".gitkeep"

# File size limit for indexing (500 MB)
MAX_INDEX_SIZE = 500 * 1024 * 1024


# ── Models ────────────────────────────────────────────────────────────────────


class IndexEntry:
    """Metadata for a single file in the Knowledge Lake."""

    def __init__(
        self,
        path: str,
        size: int,
        sha256: str,
        created: str,
    ) -> None:
        self.path = path
        self.size = size
        self.sha256 = sha256
        self.created = created

    def to_dict(self) -> dict[str, object]:
        return {
            "size": self.size,
            "sha256": self.sha256,
            "created": self.created,
        }


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

    # ── Indexing ───────────────────────────────────────────────────────────────

    def rebuild_index(self) -> dict[str, dict[str, object]]:
        """Scan the Knowledge Lake and regenerate ``index.yaml``.

        Walks all 5 directories, computes SHA-256 hashes and sizes
        for every file (skipping ``.gitkeep`` and ``index.yaml``),
        and writes a human-readable YAML index.

        Corrupted or missing index files are silently rebuilt — the
        filesystem state is always the source of truth.

        Returns:
            The index data as a nested dict.
        """
        index: dict[str, dict[str, object]] = {}

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
                if file_path.stat().st_size > MAX_INDEX_SIZE:
                    continue

                rel = str(file_path.relative_to(self.root))
                try:
                    sha256 = self._hash_file(file_path)
                    entries[rel] = IndexEntry(
                        path=rel,
                        size=file_path.stat().st_size,
                        sha256=sha256,
                        created=datetime.fromtimestamp(
                            file_path.stat().st_ctime, tz=timezone.utc
                        ).isoformat(),
                    ).to_dict()
                except OSError:
                    continue

            if entries:
                index[dir_name] = entries

        # Write index.yaml
        index_path = self.root / INDEX_FILENAME
        header = {
            "_generated": datetime.now(timezone.utc).isoformat(),
            "_version": "1",
        }
        doc = {**header, "directories": index}

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

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
