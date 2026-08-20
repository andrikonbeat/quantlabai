"""Ingest adapters for official SQX/JForex documentation sources.

Each adapter yields normalized doc records (slug, kind, version, content,
provenance) from a specific source. The adapters are intentionally thin:
they translate raw source material into the Markdown + provenance format
expected by :class:`DocIndexer`.
"""

from __future__ import annotations

import logging
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocRecord:
    """Normalized doc ready for persistence.

    Attributes:
        slug: Filesystem-safe identifier derived from the source name/FQN.
        kind: Doc category — ``block``, ``api``, ``cheat-sheet``, ``jforex``.
        version: Source version bucket (e.g. ``"144.2953"``).
        content: Full Markdown content (with front-matter provenance).
        provenance: Provenance metadata (source path/URL, license note, etc.).
    """

    slug: str
    kind: str
    version: str
    content: str
    provenance: dict[str, str] = field(default_factory=dict)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _slugify(name: str) -> str:
    """Normalize a name into a filesystem slug (``"Stop Loss"`` -> ``"stop-loss"``)."""
    slug = __import__("re").sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unnamed"


def _sha256_of(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _front_matter(provenance: dict[str, str]) -> str:
    return yaml.dump(provenance, default_flow_style=False, sort_keys=False)


# ── Adapters ───────────────────────────────────────────────────────────────────


class DocsJsonAdapter:
    """Read SQX ``internal/autocomplete/docs.json`` and emit Markdown docs.

    The JSON is a flat ``{FQN: description}`` dict. Each entry becomes one
    ``.md`` file under ``structured/sqx-kb/{ver}/docs/{kind}s/{slug}.md``.
    Kind is inferred from the FQN segment (``blocks`` → ``block``,
    ``...results.stats...`` → ``api``).
    """

    def __init__(self, docs_json_path: Path, version: str) -> None:
        self._path = docs_json_path
        self._version = version

    def iter_records(self) -> Iterator[DocRecord]:
        if not self._path.is_file():
            logger.warning("DocsJsonAdapter: %s missing", self._path)
            return

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("DocsJsonAdapter: failed to parse %s (%s)", self._path, exc)
            return

        if not isinstance(data, dict):
            return

        for fqn, description in data.items():
            kind = self._infer_kind(fqn)
            slug = _slugify(fqn)
            body = f"# {fqn}\n\n{description}\n"
            provenance: dict[str, str] = {
                "source": str(self._path),
                "license": "licensed-install/personal-use",
                "fetched_at": _now_iso(),
                "fqn": fqn,
            }
            # Deterministic sha256: stable fields + body only (no timestamp).
            provenance["sha256"] = _sha256_of(
                provenance["source"] + body
            )
            content = (
                f"---\n"
                f"{_front_matter(provenance)}"
                f"---\n"
                f"{body}"
            )
            yield DocRecord(
                slug=slug,
                kind=kind,
                version=self._version,
                content=content,
                provenance=provenance,
            )

    @staticmethod
    def _infer_kind(fqn: str) -> str:
        lowered = fqn.lower()
        if "block" in lowered:
            return "block"
        if "results.stats" in lowered or "interface" in lowered or ".api" in lowered:
            return "api"
        return "api"


class SnippetsAdapter:
    """Emit one doc per Java snippet under ``Snippets/SQ/Blocks/``.

    U4 scope: list the snippet files; U5+ can normalize content.
    """

    def __init__(self, snippets_dir: Path, version: str, max_dirs: int = 10) -> None:
        self._dir = snippets_dir
        self._version = version
        self._max_dirs = max_dirs

    def iter_records(self) -> Iterator[DocRecord]:
        if not self._dir.is_dir():
            logger.warning("SnippetsAdapter: %s missing", self._dir)
            return

        dirs = sorted(self._dir.iterdir())[: self._max_dirs]
        for snippet_dir in dirs:
            if not snippet_dir.is_dir():
                continue
            for snippet_file in sorted(snippet_dir.glob("*.java")):
                slug = _slugify(snippet_file.stem)
            body = (
                f"# Snippet: {snippet_file.name}\n\n"
                f"_Source: {snippet_file}_\n"
            )
            provenance: dict[str, str] = {
                "source": str(snippet_file),
                "license": "licensed-install/personal-use",
                "fetched_at": _now_iso(),
            }
            provenance["sha256"] = _sha256_of(provenance["source"] + body)
            content = (
                f"---\n"
                f"{_front_matter(provenance)}"
                f"---\n"
                f"{body}"
            )
            yield DocRecord(
                slug=slug,
                kind="block",
                version=self._version,
                content=content,
                provenance=provenance,
            )


class TemplatesAdapter:
    """Emit one doc per JForex export template under ``Code/JForex/``."""

    def __init__(self, templates_dir: Path, version: str) -> None:
        self._dir = templates_dir
        self._version = version

    def iter_records(self) -> Iterator[DocRecord]:
        if not self._dir.is_dir():
            logger.warning("TemplatesAdapter: %s missing", self._dir)
            return

        for template_file in sorted(self._dir.rglob("*")):
            if not template_file.is_file():
                continue
            slug = _slugify(template_file.stem)
            kind = "jforex"
            body = (
                f"# Template: {template_file.name}\n\n"
                f"_Source: {template_file}_\n"
            )
            provenance: dict[str, str] = {
                "source": str(template_file),
                "license": "licensed-install/personal-use",
                "fetched_at": _now_iso(),
            }
            provenance["sha256"] = _sha256_of(provenance["source"] + body)
            content = (
                f"---\n"
                f"{_front_matter(provenance)}"
                f"---\n"
                f"{body}"
            )
            yield DocRecord(
                slug=slug,
                kind=kind,
                version=self._version,
                content=content,
                provenance=provenance,
            )


__all__ = ["DocRecord", "DocsJsonAdapter", "SnippetsAdapter", "TemplatesAdapter"]
