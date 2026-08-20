"""DocIndexer — ingests official SQX/JForex documentation into the Knowledge Lake.

Writes version-pinned Markdown under ``knowledge/structured/sqx-kb/{ver}/docs/``
and ``knowledge/structured/jforex-kb/{ver}/``, with front-matter provenance.
Raw corpus stays under gitignored ``knowledge/raw/`` (REQ-KDI-01).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from quantlab.knowledge.ingest.adapters import (
    DocRecord,
    DocsJsonAdapter,
    SnippetsAdapter,
    TemplatesAdapter,
    _sha256_of,
)
from quantlab.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)


@dataclass
class IngestStats:
    """Summary of a DocIndexer run."""

    docs_written: int = 0
    docs_skipped: int = 0
    sources_processed: int = 0


class DocIndexer:
    """Ingest official SQX/JForex docs into the Knowledge Lake.

    Args:
        knowledge_root: Root of the Knowledge Lake (defaults to ``knowledge/``).
        install_path: Path to the licensed SQX install (for sqx-install source).
    """

    def __init__(self, knowledge_root: Path | str | None = None, install_path: Path | str | None = None) -> None:
        self._root = Path(knowledge_root) if knowledge_root else Path("knowledge")
        self._install = Path(install_path) if install_path else None
        self._store = KnowledgeStore(root=self._root)

    def ingest(self, version: str, source: str = "sqx-install") -> IngestStats:
        """Run ingestion for a specific SQX version.

        Args:
            version: SQX version bucket (e.g. ``"144.2953"``).
            source: Source selector — ``"sqx-install"`` only in U4.

        Returns:
            IngestStats summarizing written/skipped docs.
        """
        stats = IngestStats()
        adapters: Sequence[DocsJsonAdapter | SnippetsAdapter | TemplatesAdapter] = []

        if source == "sqx-install":
            if self._install is None:
                raise ValueError("install_path is required for source='sqx-install'")
            adapters = self._build_sqx_install_adapters(version)
        else:
            raise ValueError(f"Unsupported source {source!r}")

        for adapter in adapters:
            stats.sources_processed += 1
            for record in adapter.iter_records():
                if self._write_doc(version, record):
                    stats.docs_written += 1
                else:
                    stats.docs_skipped += 1

        self._store.rebuild_index()
        return stats

    def _build_sqx_install_adapters(self, version: str) -> list[DocsJsonAdapter | SnippetsAdapter | TemplatesAdapter]:
        """Build adapters from the licensed SQX install."""
        if self._install is None:
            return []
        base = self._install
        return [
            DocsJsonAdapter(base / "internal" / "autocomplete" / "docs.json", version),
            SnippetsAdapter(base / "internal" / "extend" / "Snippets" / "SQ" / "Blocks", version),
            TemplatesAdapter(base / "internal" / "extend" / "Code" / "JForex", version),
        ]

    def _write_doc(self, version: str, record: DocRecord) -> bool:
        """Write one doc to the structured layout. Returns True if written, False if skipped."""
        kind_dir = {
            "block": "docs/blocks",
            "api": "docs/apis",
            "cheat-sheet": "cheat-sheets",
            "jforex": "docs/jforex",
        }.get(record.kind)

        if kind_dir is None:
            logger.warning("DocIndexer: unknown kind %r for %s", record.kind, record.slug)
            return False

        if record.kind == "jforex":
            target_dir = self._root / "structured" / "jforex-kb" / version / kind_dir
        else:
            target_dir = self._root / "structured" / "sqx-kb" / version / kind_dir

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{record.slug}.md"

        # Idempotency: skip when the stored sha256 matches the expected one.
        if target_path.exists():
            existing = target_path.read_text(encoding="utf-8")
            stored_sha256 = None
            for line in existing.splitlines()[:20]:
                if line.startswith("sha256:"):
                    stored_sha256 = line.split(":", 1)[1].strip()
                    break
            if stored_sha256 == record.provenance.get("sha256"):
                logger.debug("DocIndexer: skip unchanged %s", target_path)
                return False

        target_path.write_text(record.content, encoding="utf-8")
        logger.debug("DocIndexer: wrote %s", target_path)
        return True

    @staticmethod
    def _sha256_of(text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = ["DocIndexer", "IngestStats"]
