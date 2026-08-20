"""Knowledge Store — filesystem Knowledge Lake manager.

Manages the Knowledge Lake directory structure: a filesystem-first,
Git-versioned research artifact repository. Provides path conventions,
directory initialisation, and basic metadata indexing using open,
human-readable formats.

Directory layout::

    knowledge/
    ├── index.yaml            # auto-generated metadata index (v5)
    ├── raw/                  # raw/unprocessed research artifacts
    ├── structured/           # cleaned, structured data (JSON, Parquet)
    │   ├── {campaign_id}/    # per-campaign configs, metrics, results
    │   ├── sqx-kb/{ver}/parameters/{tab}/   # SQX parameter KB
    │   └── sqx-version/{old}→{new}/         # version-drift checklists
    ├── graph/                # relationship graphs and knowledge maps
    ├── embeddings/           # vector embeddings and model artifacts
    ├── datasets/             # curated, versioned datasets
    ├── pipeline-runs/        # pipeline execution history (YAML per run)
    ├── agent-memory/         # durable per-agent per-campaign memory
    ├── campaign-phases/      # phase envelopes per campaign execution
    ├── parameter-matrix/     # SQX parameter justification matrices
    ├── guardian-feedback/    # live degradation and parameter feedback
    └── maintenance/          # maintenance plans and replacement runbooks
"""

from __future__ import annotations

import hashlib
import json
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from quantlab.data.market.models import Bar
from quantlab.tools.exceptions import ParseError
from quantlab.robustness.circuit_breaker import CircuitBreaker
from quantlab.robustness.knowledge_health import (
    HealthCheckResult,
    HealthStatus,
    KnowledgeStoreHealthCheck,
)

# ── Constants ─────────────────────────────────────────────────────────────────

KNOWLEDGE_DIRS = [
    "raw",
    "structured",
    "graph",
    "embeddings",
    "datasets",
    "pipeline-runs",
    "agent-memory",
    "campaign-phases",
    "parameter-matrix",
    "guardian-feedback",
    "maintenance",
]

ALLOWED_EXTENSIONS = {".yaml", ".yml", ".json", ".csv", ".parquet"}

INDEX_FILENAME = "index.yaml"

GITKEEP_FILENAME = ".gitkeep"

# File size limit for indexing (500 MB)
MAX_INDEX_SIZE = 500 * 1024 * 1024

PIPELINE_RUNS_DIR = "pipeline-runs"

# Canonical structured sub-layout skeletons (REQ-101). ``initialize()``
# creates these so the reconciled taxonomy exists before any real
# campaign/version is known; the ``_template`` segments are placeholders
# for ``{campaign_id}``, ``{ver}/{tab}`` and ``{old}→{new}`` respectively.
STRUCTURED_SUB_LAYOUTS = [
    "structured/_template",
    "structured/sqx-kb/_template/parameters/_template",
    "structured/sqx-kb/_template/docs/_template",
    "structured/jforex-kb/_template",
    "structured/sqx-version/_template→_template",
    "campaign-phases/_template",
    "parameter-matrix/_template",
    "guardian-feedback/_template",
    "maintenance/_template",
]


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


# ── Deterministic text similarity (REQ-501, WU6) ──────────────────────────────

# Text features are token counts PLUS char 3-gram counts over those tokens.
# This keeps the ranking deterministic and dependency-free (no dense embedding
# model), while still capturing phrase-level structure beyond bag-of-words.
_NGRAM_SIZE = 3


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase alphanumeric tokens (no regex dependency)."""
    tokens: list[str] = []
    current: list[str] = []
    for ch in str(text).lower():
        if ch.isalnum():
            current.append(ch)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _add_text(vector: dict[str, int], text: str) -> None:
    """Accumulate token + char n-gram counts into a feature vector."""
    tokens = _tokenize(text)
    for token in tokens:
        vector[token] = vector.get(token, 0) + 1
    if len(tokens) >= _NGRAM_SIZE:
        for i in range(len(tokens) - _NGRAM_SIZE + 1):
            gram = "".join(tokens[i : i + _NGRAM_SIZE])
            vector[gram] = vector.get(gram, 0) + 1


def _record_text(record: dict) -> str:
    """Concatenate the comparable fields of a decision record."""
    parts = [
        str(record.get("phase", "")),
        str(record.get("status", "")),
        str(record.get("executive_summary", "")),
    ]
    for key in ("risks", "lessons"):
        value = record.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value is not None:
            parts.append(str(value))
    config = record.get("config")
    if isinstance(config, dict):
        parts.extend(str(value) for value in config.values())
    return " ".join(parts)


def _text_cosine(a: dict[str, int], b: dict[str, int]) -> float:
    """Cosine similarity between two sparse feature vectors."""
    if not a or not b:
        return 0.0
    dot = sum(count * b.get(feature, 0) for feature, count in a.items())
    norm_a = sum(count * count for count in a.values()) ** 0.5
    norm_b = sum(count * count for count in b.values()) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── KnowledgeStore ────────────────────────────────────────────────────────────


class KnowledgeStore:
    """Manages the Knowledge Lake directory structure and metadata.

    Usage::

        store = KnowledgeStore(root=Path("knowledge"))
        store.initialize()
        store.rebuild_index()
        warnings = store.validate_formats()
    """

    def __init__(
        self, root: str | Path = "knowledge", circuit_breaker: CircuitBreaker | None = None
    ) -> None:
        self.root = Path(root).resolve()

        # ── Robustness integration (advanced-robustness 3.3, REQ-403) ─────────
        # Writes are protected by a CircuitBreaker: when the circuit is OPEN,
        # writes are buffered in-memory (bounded FIFO) instead of hitting disk.
        # ``health_check`` replays buffered writes once the store is writable.
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._write_buffer: list[dict[str, str]] = []
        self._buffer_max_size = 1000

    # ── Initialisation ─────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Create the Knowledge Lake skeleton.

        Creates ``knowledge/`` and all 7 subdirectories (``raw/``,
        ``structured/``, ``graph/``, ``embeddings/``, ``datasets/``,
        ``pipeline-runs/``, ``agent-memory/``) plus the 3 reconciled
        structured sub-layouts (``structured/{campaign_id}/``,
        ``structured/sqx-kb/{ver}/parameters/{tab}/`` and
        ``structured/sqx-version/{old}→{new}/``, as ``_template``
        placeholders) if they do not exist. Each directory receives a
        ``.gitkeep`` marker file.

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

        for rel in STRUCTURED_SUB_LAYOUTS:
            sub_path = self.root / rel
            sub_path.mkdir(parents=True, exist_ok=True)

            gitkeep = sub_path / GITKEEP_FILENAME
            if not gitkeep.exists():
                gitkeep.write_text("", encoding="utf-8")

    # ── Write buffering with circuit breaker (advanced-robustness 3.3) ───────

    def _check_write_circuit(self, path: str, content: str) -> None:
        """Write ``content`` to ``path`` when the circuit is CLOSED.

        When the circuit breaker is OPEN (or HALF_OPEN), the write is
        buffered in ``_write_buffer`` (bounded FIFO) instead of hitting
        disk.  Buffered writes are replayed by :meth:`_replay_buffer`
        or :meth:`health_check`.
        """
        if self._circuit_breaker.state == "CLOSED":
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return

        if len(self._write_buffer) >= self._buffer_max_size:
            self._write_buffer.pop(0)
        self._write_buffer.append({"path": path, "content": content})

    def _replay_buffer(self) -> None:
        """Replay buffered writes to disk, preserving any that still fail.

        Writes that succeed are removed from the buffer; writes that raise
        an ``OSError`` (e.g. read-only store) are kept for a later replay.
        """
        remaining: list[dict[str, str]] = []
        for entry in self._write_buffer:
            try:
                target = self.root / entry["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(entry["content"], encoding="utf-8")
            except OSError:
                remaining.append(entry)
        self._write_buffer = remaining

    async def health_check(self) -> "HealthCheckResult":
        """Probe store writability and replay buffered writes.

        Runs a ``KnowledgeStoreHealthCheck`` probe against this store; on a
        healthy probe, buffered writes are replayed to disk.  Unlike a
        circuit close, a healthy probe does **not** change the circuit
        breaker state — recovery is driven by the circuit's own timeout.
        """
        check = KnowledgeStoreHealthCheck(self)
        result = await check.check()
        if result.status == HealthStatus.HEALTHY:
            self._replay_buffer()
        return result

    # ── Async I/O interface (used by KnowledgeStoreHealthCheck) ───────────────

    async def write(self, path: str, content: str) -> None:
        """Write ``content`` to ``path`` under the store root (async I/O)."""
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    async def read(self, path: str) -> str:
        """Read and return the text at ``path`` under the store root."""
        target = self.root / path
        return target.read_text(encoding="utf-8")

    async def delete(self, path: str) -> None:
        """Delete the file at ``path`` under the store root, if present."""
        target = self.root / path
        if target.exists():
            target.unlink()

    # ── Dataset Cache (G6) ──────────────────────────────────────────────────

    async def cache_dataset(
        self, symbol: str, timeframe: str, bars: list[Bar]
    ) -> str:
        """Cache normalized OHLC bars into ``datasets/{symbol}/{timeframe}.csv``.

        The G6 seed command and the Dukascopy research provider (G3) both
        write through this helper so ``rebuild_index()`` records every cached
        dataset. Timestamps are stored as UTC ISO-8601; columns match the
        ``Bar`` model (``quantlab.data.market.models``). Re-caching the same
        symbol/timeframe overwrites the file (idempotent re-seed).

        Args:
            symbol: Base symbol (e.g. ``EURUSD``).
            timeframe: FX timeframe (``M1``/``M5``/``H1``).
            bars: Normalized OHLCV bars to persist.

        Returns:
            The relative lake path (``datasets/{symbol}/{timeframe}.csv``).
        """
        rows = [
            f"{bar.timestamp.isoformat()},{bar.open},{bar.high},{bar.low},"
            f"{bar.close},{bar.volume}"
            for bar in bars
        ]
        rel = f"datasets/{symbol}/{timeframe}.csv"
        header = "timestamp,open,high,low,close,volume"
        await self.write(rel, header + "\n" + "\n".join(rows) + "\n")
        return rel

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

        Walks every directory recursively (v5 records nested artifacts such
        as ``datasets/{symbol}/{timeframe}.csv`` and
        ``campaign-phases/{campaign_id}/{phase}/envelope.json``), computes
        SHA-256 hashes and sizes for every file (skipping ``.gitkeep`` and
        ``index.yaml``), and writes a human-readable YAML index.

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
            for file_path in sorted(dir_path.rglob("*")):
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

        # Build base index dict (v5 — reconciled layout, REQ-403; v5 adds
        # campaign-phase, parameter-matrix, guardian-feedback, maintenance)
        doc: dict[str, object] = {
            "_generated": now_iso,
            "_version": "5",
            "directories": directories,
            "agent_memory": self._build_agent_memory_index(),
            "kb_parameters": self._build_kb_parameters_index(),
            "version_events": self._build_version_events_index(),
            "campaign_phases": {},
            "parameter_matrix": {},
            "guardian_feedback": {},
            "maintenance": {},
            "docs": self._build_docs_index(),
        }

        # Enhance with campaign metrics/tags/links via Indexer (if available)
        try:
            from quantlab.knowledge.indexer import Indexer
            indexer = Indexer(self.root)
            doc["campaigns"] = indexer.build_index()
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
            data = self._upgrade_index(data)
            data.setdefault("docs", {})
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

    # ── Campaign Phase Envelopes ───────────────────────────────────────────────

    def save_phase_envelope(
        self,
        campaign_id: str,
        phase: str,
        *,
        status: str,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        duration: Optional[float] = None,
        artifacts: Optional[list[str]] = None,
        error: Optional[str] = None,
        next_gate: Optional[str] = None,
        gate_decision: Optional[str] = None,
    ) -> Path:
        """Persist a phase execution envelope (full-campaign-lifecycle REQ-3).

        Writes ``campaign-phases/{campaign_id}/{phase}/envelope.json`` so every
        phase — including failed ones — leaves a durable, reviewable record:
        the status, the artifact list (the error log must be listed on
        failure), and the next-phase gate.

        Args:
            campaign_id: Campaign identifier.
            phase: Phase name (e.g. "retest", "archive").
            status: Phase status ("pending", "running", "completed",
                "failed", ...).
            started_at: Optional ISO start timestamp.
            completed_at: Optional ISO completion timestamp.
            duration: Optional phase duration in seconds.
            artifacts: Artifact paths produced by the phase; on failure this
                MUST include the error log (REQ-3).
            error: Error message when the phase failed.
            next_gate: The next-phase gate — "HOLD" on failure (REQ-3).
            gate_decision: Resolved gate action, when a gate ran.

        Returns:
            The absolute path of the written ``envelope.json``.
        """
        from dataclasses import asdict

        from quantlab.knowledge.models import PhaseEnvelope

        envelope = PhaseEnvelope(
            campaign_id=campaign_id,
            phase=phase,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration=duration,
            artifacts=list(artifacts or []),
            error=error,
            next_gate=next_gate,
            gate_decision=gate_decision,
        )
        envelope_dir = self.resolve(f"campaign-phases/{campaign_id}/{phase}")
        envelope_dir.mkdir(parents=True, exist_ok=True)
        envelope_path = envelope_dir / "envelope.json"
        envelope_path.write_text(
            json.dumps(asdict(envelope), indent=2, default=str), encoding="utf-8"
        )
        return envelope_path

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

    @staticmethod
    def _upgrade_index(data: dict[str, object]) -> dict[str, object]:
        """Upgrade a legacy index schema to v5 with backward-compatible defaults."""
        version = str(data.get("_version", "1"))
        if version == "5":
            return data

        # v4 → v5: add campaign-phase, parameter-matrix, guardian-feedback, maintenance
        if version == "4":
            data["_version"] = "5"
            data.setdefault("campaign_phases", {})
            data.setdefault("parameter_matrix", {})
            data.setdefault("guardian_feedback", {})
            data.setdefault("maintenance", {})
            return data

        # v3 → v5 (skip v4 intermediate)
        if version == "3":
            data["_version"] = "5"
            data.setdefault("agent_memory", {})
            data.setdefault("kb_parameters", {})
            data.setdefault("version_events", {})
            data.setdefault("campaign_phases", {})
            data.setdefault("parameter_matrix", {})
            data.setdefault("guardian_feedback", {})
            data.setdefault("maintenance", {})
            return data

        if version == "2":
            data["_version"] = "5"
            am_index = data.setdefault("agent_memory", {})
            for path, info in (
                data.get("directories", {}).get("agent-memory", {}).items()
            ):
                if isinstance(info, dict):
                    info.setdefault("agent_name", None)
                    info.setdefault("campaign_id", None)
                    info.setdefault("memory_path", path)
                    info.setdefault("checkpoint_paths", [])
                    info.setdefault("last_updated", None)
                    info.setdefault("embedding_ref", None)
            data.setdefault("kb_parameters", {})
            data.setdefault("version_events", {})
            data.setdefault("campaign_phases", {})
            data.setdefault("parameter_matrix", {})
            data.setdefault("guardian_feedback", {})
            data.setdefault("maintenance", {})
            return data

        # v1 → v5 (best-effort; every new area gets a default)
        if version == "1":
            data["_version"] = "5"
            data.setdefault("directories", {})
            data.setdefault("agent_memory", {})
            data.setdefault("kb_parameters", {})
            data.setdefault("version_events", {})
            data.setdefault("campaign_phases", {})
            data.setdefault("parameter_matrix", {})
            data.setdefault("guardian_feedback", {})
            data.setdefault("maintenance", {})
        return data

    def _build_agent_memory_index(self) -> dict[str, dict[str, object]]:
        """Build an index of ``agent-memory/`` entries.

        Returns:
            Dict mapping memory file path -> metadata with agent_name,
            campaign_id, checkpoint_paths, last_updated, and embedding_ref.
        """
        agent_memory_dir = self.root / "agent-memory"
        if not agent_memory_dir.exists():
            return {}

        entries: dict[str, object] = {}
        now_iso = datetime.now(timezone.utc).isoformat()

        for memory_file in agent_memory_dir.rglob("memory.yaml"):
            rel = str(memory_file.relative_to(self.root))
            parts = memory_file.relative_to(agent_memory_dir).parts
            agent_name = parts[0] if len(parts) > 0 else None
            campaign_id = parts[1] if len(parts) > 1 else None

            checkpoint_paths: list[str] = []
            parent = memory_file.parent
            if parent.exists():
                for cp in parent.glob("checkpoints/*.yaml"):
                    checkpoint_paths.append(
                        str(cp.relative_to(self.root))
                    )

            embedding_ref = None
            try:
                from quantlab.knowledge.models import AgentMemoryEntry

                entry = AgentMemoryEntry(
                    agent_name=agent_name or "",
                    campaign_id=campaign_id or "",
                    memory_path=rel,
                    checkpoint_paths=checkpoint_paths,
                    last_updated=now_iso,
                    embedding_ref=embedding_ref,
                )
                entries[rel] = entry.to_dict()
            except Exception:
                entries[rel] = {
                    "agent_name": agent_name,
                    "campaign_id": campaign_id,
                    "memory_path": rel,
                    "checkpoint_paths": checkpoint_paths,
                    "last_updated": now_iso,
                    "embedding_ref": None,
                    "size": memory_file.stat().st_size,
                    "sha256": self._hash_file(memory_file),
                }

        return entries

    def _build_kb_parameters_index(self) -> dict[str, dict[str, object]]:
        """Build an index of KB parameter files under ``structured/sqx-kb/``.

        Maps ``structured/sqx-kb/{ver}/parameters/{tab}/{param}.yaml`` to
        metadata with sqx_version, tab, and parameter name (REQ-403).
        """
        kb_root = self.root / "structured" / "sqx-kb"
        if not kb_root.exists():
            return {}

        entries: dict[str, object] = {}
        for param_file in sorted(kb_root.rglob("parameters/**/*.yaml")):
            rel = str(param_file.relative_to(self.root))
            # parts = (ver, "parameters", tab, *rest, filename)
            parts = param_file.relative_to(kb_root).parts
            ver = parts[0]
            tab = parts[2]
            entries[rel] = {
                "sqx_version": ver,
                "tab": tab,
                "parameter": param_file.stem,
                "size": param_file.stat().st_size,
                "sha256": self._hash_file(param_file),
            }
        return entries

    def _build_version_events_index(self) -> dict[str, dict[str, object]]:
        """Build an index of version-event checklists under ``structured/sqx-version/``.

        Maps ``structured/sqx-version/{old}→{new}/checklist.yaml`` to
        metadata with from_version, to_version, and checklist status (REQ-403).
        """
        ver_root = self.root / "structured" / "sqx-version"
        if not ver_root.exists():
            return {}

        entries: dict[str, object] = {}
        for checklist in sorted(ver_root.glob("*/checklist.yaml")):
            rel = str(checklist.relative_to(self.root))
            transition = checklist.parent.name
            from_version, to_version = (
                transition.split("→", 1) if "→" in transition else (None, None)
            )
            status = None
            try:
                data = yaml.safe_load(checklist.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    status = data.get("status")
            except Exception:
                pass
            entries[rel] = {
                "from_version": from_version,
                "to_version": to_version,
                "status": status,
                "size": checklist.stat().st_size,
                "sha256": self._hash_file(checklist),
            }
        return entries

    def _build_docs_index(self) -> dict[str, dict[str, object]]:
        """Index official SQX/JForex docs under ``structured/sqx-kb/`` and ``structured/jforex-kb/``.

        Maps each doc file to ``{size, sha256, kind, version}`` where ``kind``
        is one of ``block``, ``api``, ``cheat-sheet``, or ``jforex``.
        """
        docs_root = self.root / "structured"
        if not docs_root.exists():
            return {}

        entries: dict[str, object] = {}
        for file_path in sorted(docs_root.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name in (GITKEEP_FILENAME, INDEX_FILENAME):
                continue

            rel = str(file_path.relative_to(self.root))
            rel_parts = file_path.relative_to(docs_root).parts
            kind = "jforex"
            version = None
            for idx, part in enumerate(rel_parts):
                if part == "sqx-kb" and idx + 1 < len(rel_parts):
                    version = rel_parts[idx + 1]
                    if idx + 2 < len(rel_parts) and rel_parts[idx + 2] == "docs":
                        if idx + 3 < len(rel_parts) and rel_parts[idx + 3] == "blocks":
                            kind = "block"
                        elif idx + 3 < len(rel_parts) and rel_parts[idx + 3] == "apis":
                            kind = "api"
                    elif idx + 2 < len(rel_parts) and rel_parts[idx + 2] == "cheat-sheets":
                        kind = "cheat-sheet"
                    break
                if part == "jforex-kb" and idx + 1 < len(rel_parts):
                    version = rel_parts[idx + 1]
                    break

            if version is None:
                continue

            entries[rel] = {
                "size": file_path.stat().st_size,
                "sha256": self._hash_file(file_path),
                "kind": kind,
                "version": version,
            }

        return entries

    # ── Tag Management ──────────────────────────────────────────────────────────

    def tag(self, campaign_id: str, tags: list[str]) -> None:
        """Add tags to a campaign.

        Tags stored in ``knowledge/tags/{campaign_id}.yaml``.

        Args:
            campaign_id: Campaign identifier.
            tags: List of tag strings to add.
        """
        from quantlab.knowledge.indexer import Indexer

        Indexer.tag_campaign(self, campaign_id, tags)

    def get_tags(self, campaign_id: str) -> list[str]:
        """Get tags for a campaign.

        Args:
            campaign_id: Campaign identifier.

        Returns:
            List of tag strings.
        """
        from quantlab.knowledge.indexer import Indexer

        return Indexer.get_tags(self, campaign_id)

    # ── Link Management ─────────────────────────────────────────────────────────

    def link(self, parent: str, children: list[str]) -> None:
        """Create parent-child links between campaigns.

        Args:
            parent: Parent campaign identifier.
            children: List of child campaign identifiers.
        """
        from quantlab.knowledge.indexer import Indexer

        Indexer.link_campaigns(self, parent, children)

    def get_links(self, campaign_id: str) -> dict[str, list[str]]:
        """Get links (parents and children) for a campaign.

        Args:
            campaign_id: Campaign identifier.

        Returns:
            Dict with optional 'parents' and 'children' keys.
        """
        from quantlab.knowledge.indexer import Indexer

        return Indexer.get_links(self, campaign_id)

    # ── Query ───────────────────────────────────────────────────────────────────

    def query(self) -> object:
        """Create a QueryBuilder for this Knowledge Lake.

        Returns:
            QueryBuilder instance configured with the current index.
        """
        from quantlab.knowledge.query import QueryBuilder

        index = self.read_index()
        return QueryBuilder(index, self.root)

    def find_similar_campaigns(
        self,
        campaign_id: str,
        top_k: int = 10,
        min_similarity: float = 0.7,
    ) -> list[dict[str, object]]:
        """Find campaigns similar to the target campaign using embeddings.

        Loads embedding vectors from ``embeddings/`` and computes cosine
        similarity against the target campaign's embedding.

        Args:
            campaign_id: Target campaign identifier.
            top_k: Maximum number of similar campaigns to return.
            min_similarity: Minimum cosine similarity threshold.

        Returns:
            List of dicts with ``campaign_id`` and ``similarity_score``.
        """
        embeddings_dir = self.root / "embeddings"
        if not embeddings_dir.exists() or not any(embeddings_dir.iterdir()):
            # WU6: no dense vectors available — fall back to a deterministic
            # text-embedding ranking over the memory lake (REQ-501).
            return self._find_similar_text(campaign_id, top_k, min_similarity)

        import numpy as np

        target_file = None
        for ext in (".npy",):
            candidate = embeddings_dir / f"{campaign_id}{ext}"
            if candidate.exists():
                target_file = candidate
                break
        if target_file is None:
            # Also try parquet
            import pandas as pd

            parquet_file = embeddings_dir / f"{campaign_id}.parquet"
            if parquet_file.exists():
                try:
                    df = pd.read_parquet(parquet_file)
                    target_vec = df.iloc[:, 0].to_numpy(dtype=np.float64)
                except Exception:
                    return []
            else:
                return []
        else:
            target_vec = np.load(target_file)

        target_norm = float(np.linalg.norm(target_vec))
        if target_norm == 0:
            return []

        results: list[dict[str, object]] = []
        for emb_path in embeddings_dir.iterdir():
            if emb_path.stem == campaign_id:
                continue
            try:
                if emb_path.suffix == ".npy":
                    vec = np.load(emb_path)
                else:
                    continue
                norm = float(np.linalg.norm(vec))
                if norm == 0:
                    continue
                similarity = float(np.dot(target_vec, vec) / (target_norm * norm))
                if similarity >= min_similarity:
                    results.append(
                        {
                            "campaign_id": emb_path.stem,
                            "similarity_score": similarity,
                        }
                    )
            except Exception:
                continue

        results.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
        return results[:top_k]

    def _find_similar_text(
        self,
        campaign_id: str,
        top_k: int,
        min_similarity: float,
    ) -> list[dict[str, object]]:
        """Rank campaigns by deterministic text similarity (REQ-501, WU6).

        Builds a sparse token + char n-gram vector per campaign from the
        memory lake (``agent-memory/*/*/memory.yaml``) and structured campaign
        artifacts, then ranks by cosine similarity. Deterministic and
        dependency-free — no dense embedding model required. An empty or
        unreadable lake yields ``[]``.
        """
        corpus = self._text_corpus()
        target = corpus.get(campaign_id)
        if not target:
            return []
        results: list[dict[str, object]] = []
        for other_id, vector in corpus.items():
            if other_id == campaign_id:
                continue
            similarity = _text_cosine(vector, target)
            if similarity > 0.0 and similarity >= min_similarity:
                results.append(
                    {"campaign_id": other_id, "similarity_score": similarity}
                )
        results.sort(
            key=lambda r: float(r.get("similarity_score", 0.0)), reverse=True
        )
        return results[:top_k]

    def _text_corpus(self) -> dict[str, dict[str, int]]:
        """Map campaign_id -> text feature vector (REQ-501, WU6).

        Features come from captured decisions (``agent-memory/``) and, when
        present, the structured campaign.md artifact (``structured/``).
        """
        corpus: dict[str, dict[str, int]] = {}

        memory_root = self.root / "agent-memory"
        if memory_root.is_dir():
            for memory_file in memory_root.glob("*/*/memory.yaml"):
                campaign = memory_file.parent.name
                try:
                    records = yaml.safe_load(
                        memory_file.read_text(encoding="utf-8")
                    ) or []
                except Exception:
                    continue
                if not isinstance(records, list):
                    records = [records]
                vector = corpus.setdefault(campaign, {})
                for record in records:
                    if isinstance(record, dict):
                        _add_text(vector, _record_text(record))

        structured_root = self.root / "structured"
        if structured_root.is_dir():
            for camp_dir in structured_root.iterdir():
                if not camp_dir.is_dir():
                    continue
                summary_file = camp_dir / "campaign.md"
                if summary_file.is_file():
                    vector = corpus.setdefault(camp_dir.name, {})
                    try:
                        _add_text(
                            vector,
                            summary_file.read_text(
                                encoding="utf-8", errors="ignore"
                            ),
                        )
                    except Exception:
                        continue

        return corpus

    # ── Enhanced Indexing ─────────────────────────────────────────────────────────

    def enhance_index(self) -> dict[str, dict[str, object]]:
        """Rebuild index with enhanced v2 schema (metrics, tags, links).

        Calls ``Indexer.enhance_index()`` to enrich the index with
        campaign metrics from stats YAML files.

        Returns:
            The enriched index as a dict.
        """
        from quantlab.knowledge.indexer import Indexer

        idx = Indexer(self.root)
        enriched = idx.enhance_index(self)

        # Merge enriched data into the index
        current_index = self.read_index()

        # Add campaigns section
        current_index["campaigns"] = enriched
        current_index["_version"] = "2"

        # Write updated index
        index_path = self.root / INDEX_FILENAME
        index_path.write_text(
            yaml.dump(current_index, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        return current_index

    # ── Pipeline History ─────────────────────────────────────────────────────────



    def load_pipeline_runs(
        self,
        limit: int = 50,
        status: object = None,
        pipeline: str | None = None,
    ) -> list[object]:
        """Load pipeline run records from the Knowledge Lake.

        Args:
            limit: Max number of runs to return.
            status: Optional StageStatus filter.
            pipeline: Optional pipeline name filter.

        Returns:
            List of PipelineRun objects (deserialized from YAML).
        """
        from quantlab.pipeline.models import PipelineRun, StageStatus

        runs_dir = self.root / "pipeline-runs"
        if not runs_dir.exists():
            return []

        runs: list[PipelineRun] = []
        for yaml_path in sorted(runs_dir.rglob("*.yaml"), reverse=True):
            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue

                run = PipelineRun.from_dict(data)

                # Apply filters
                if status is not None and run.status != status:
                    continue
                if pipeline is not None and run.pipeline_name != pipeline:
                    continue

                runs.append(run)
                if len(runs) >= limit:
                    break

            except Exception:
                continue

        return runs

    def delete_pipeline_runs(self, run_ids: list[str]) -> int:
        """Delete pipeline run records from the Knowledge Lake.

        Args:
            run_ids: List of run IDs to delete.

        Returns:
            Number of runs successfully deleted.
        """
        runs_dir = self.root / "pipeline-runs"
        if not runs_dir.exists():
            return 0

        deleted = 0
        for run_id in run_ids:
            run_file = runs_dir / f"{run_id}.yaml"
            if run_file.exists():
                try:
                    run_file.unlink()
                    deleted += 1
                except OSError:
                    continue

        return deleted

    # ── Agent Memory ─────────────────────────────────────────────────────────────

    def store_agent_memory(
        self,
        agent_name: str,
        campaign_id: str,
        artifact: dict[str, object],
    ) -> str:
        """Append an agent memory artifact to ``agent-memory/{agent}/{campaign}/memory.yaml``.

        Args:
            agent_name: Agent identifier (e.g. ``"research-agent"``).
            campaign_id: Campaign identifier.
            artifact: Memory artifact dict to append.

        Returns:
            Absolute path to the written memory file.
        """
        memory_dir = self.root / "agent-memory" / agent_name / campaign_id
        memory_dir.mkdir(parents=True, exist_ok=True)

        memory_file = memory_dir / "memory.yaml"
        existing: list[dict[str, object]] = []
        if memory_file.exists():
            try:
                data = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    existing = data
                elif isinstance(data, dict):
                    existing = [data]
            except Exception:
                existing = []

        existing.append(artifact)
        memory_file.write_text(
            yaml.dump(existing, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        return str(memory_file)

    def load_agent_memory(
        self,
        agent_name: str,
        campaign_id: str,
    ) -> list[dict[str, object]]:
        """Load agent memory artifacts from Knowledge Lake.

        Args:
            agent_name: Agent identifier.
            campaign_id: Campaign identifier.

        Returns:
            List of memory artifact dicts. Returns ``[]`` when the memory file
            does not exist or cannot be parsed.
        """
        memory_file = (
            self.root / "agent-memory" / agent_name / campaign_id / "memory.yaml"
        )
        if not memory_file.exists():
            return []
        try:
            data = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
        except Exception:
            pass
        return []


# ── Time-Series Store ─────────────────────────────────────────────────────────


class TimeSeriesStore:
    """Append-only SQLite time-series store for metrics, alerts, and heartbeats.

    Used by the autonomous monitor daemon to persist rolling metrics, alert
    events, and heartbeat health-check records.

    Uses stdlib ``sqlite3`` — zero additional dependencies.

    Usage::

        store = TimeSeriesStore("knowledge/timeseries/monitor.db")
        store.append_metrics("strat_a", 100.0, {"sharpe": 1.5, "drawdown": 0.05})
        rows = store.query_metrics("strat_a", 0.0, 999.0)
    """

    def __init__(self, db_path: str) -> None:
        import sqlite3

        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ── Schema ──────────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        """Create tables if they do not exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS metrics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT    NOT NULL,
                timestamp   REAL    NOT NULL,
                metric_name TEXT    NOT NULL,
                value       REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                type        TEXT    NOT NULL,
                severity    TEXT    NOT NULL,
                strategy_id TEXT,
                message     TEXT,
                details     TEXT
            );

            CREATE TABLE IF NOT EXISTS heartbeats (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    REAL    NOT NULL,
                strategy_id  TEXT    NOT NULL,
                equity_count INTEGER DEFAULT 0,
                alert_count  INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_metrics_strat_time
                ON metrics(strategy_id, timestamp);

            CREATE INDEX IF NOT EXISTS idx_alerts_strat
                ON alerts(strategy_id);

            CREATE INDEX IF NOT EXISTS idx_heartbeats_strat_time
                ON heartbeats(strategy_id, timestamp);
        """)
        self._conn.commit()

    # ── Append ──────────────────────────────────────────────────────────────────

    def append_metrics(
        self, strategy_id: str, timestamp: float, metrics: dict[str, float]
    ) -> None:
        """Append a batch of metric values as individual rows.

        Args:
            strategy_id: Strategy identifier.
            timestamp: Unix timestamp (float) for this batch.
            metrics: Dict mapping metric name → value.
        """
        for name, value in metrics.items():
            self._conn.execute(
                "INSERT INTO metrics (strategy_id, timestamp, metric_name, value) "
                "VALUES (?, ?, ?, ?)",
                (strategy_id, timestamp, name, value),
            )
        self._conn.commit()

    def append_alert(self, alert: dict) -> None:
        """Append an alert event.

        Args:
            alert: Dict with keys ``timestamp``, ``type``, ``severity``,
                ``strategy_id``, ``message``, ``details``.
        """
        self._conn.execute(
            "INSERT INTO alerts (timestamp, type, severity, strategy_id, message, details) "
            "VALUES (:timestamp, :type, :severity, :strategy_id, :message, :details)",
            alert,
        )
        self._conn.commit()

    def append_heartbeat(self, heartbeat: dict) -> None:
        """Append a heartbeat record.

        Args:
            heartbeat: Dict with keys ``timestamp``, ``strategy_id``,
                optionally ``equity_count`` and ``alert_count``.
        """
        self._conn.execute(
            "INSERT INTO heartbeats (timestamp, strategy_id, equity_count, alert_count) "
            "VALUES (:timestamp, :strategy_id, :equity_count, :alert_count)",
            {
                "timestamp": heartbeat["timestamp"],
                "strategy_id": heartbeat["strategy_id"],
                "equity_count": heartbeat.get("equity_count", 0),
                "alert_count": heartbeat.get("alert_count", 0),
            },
        )
        self._conn.commit()

    # ── Query ───────────────────────────────────────────────────────────────────

    def query_metrics(
        self, strategy_id: str, since: float, until: float
    ) -> list[dict]:
        """Query metric rows for a strategy within a time range.

        Args:
            strategy_id: Strategy identifier to filter.
            since: Start timestamp (inclusive).
            until: End timestamp (exclusive).

        Returns:
            List of dicts with keys ``strategy_id``, ``timestamp``,
            ``metric_name``, ``value``.
        """
        cursor = self._conn.execute(
            "SELECT strategy_id, timestamp, metric_name, value "
            "FROM metrics "
            "WHERE strategy_id = ? AND timestamp >= ? AND timestamp < ? "
            "ORDER BY timestamp, metric_name",
            (strategy_id, since, until),
        )
        return [dict(row) for row in cursor.fetchall()]

