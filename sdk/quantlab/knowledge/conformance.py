"""Knowledge Lake taxonomy conformance (REQ-402).

Maps every writer to its canonical Knowledge Lake destinations and provides
checks that refuse writes outside the mapped layout. The map follows the
REQ-101 capture taxonomy:

    ==================  ============================================
    Writer              Canonical destination patterns
    ==================  ============================================
    memory_capture      agent-memory/{agent}/{campaign}/memory.yaml
    pipeline            pipeline-runs/
    config_writer       structured/{campaign_id}/
    raw_exporter        raw/
    metrics_writer      structured/{campaign_id}/metrics.yaml
    embedding_writer    embeddings/
    training_exporter   datasets/
    kb_seeder           structured/sqx-kb/{ver}/parameters/{tab}/
    educational_generator structured/sqx-kb/{ver}/educational/**
    version_events      structured/sqx-version/{old}→{new}/
    ==================  ============================================

Destination patterns are relative to the Knowledge Lake root. ``*`` matches
a single path segment; ``**`` matches zero or more segments.
"""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

# Writer -> canonical destination patterns (relative to the lake root).
WRITER_DESTINATIONS: dict[str, list[str]] = {
    "memory_capture": ["agent-memory/*/*/**"],
    "pipeline": ["pipeline-runs/**"],
    "config_writer": ["structured/*/**"],
    "raw_exporter": ["raw/**"],
    "metrics_writer": ["structured/*/metrics.yaml"],
    "embedding_writer": ["embeddings/**"],
    "training_exporter": ["datasets/**"],
    "kb_seeder": ["structured/sqx-kb/*/parameters/**"],
    "educational_generator": ["structured/sqx-kb/*/educational/**"],
    "version_events": ["structured/sqx-version/*/**"],
}


class ConformanceError(ValueError):
    """Raised when a writer emits outside its mapped canonical layout."""


def canonical_destination(writer: str) -> list[str]:
    """Return the canonical destination patterns for a writer.

    Args:
        writer: Writer name from the REQ-101 taxonomy.

    Returns:
        List of canonical destination patterns (relative to the lake root).

    Raises:
        KeyError: if the writer has no canonical mapping.
    """
    return list(WRITER_DESTINATIONS[writer])


def _match_parts(pattern: tuple[str, ...], path: tuple[str, ...]) -> bool:
    """Match path segments against a pattern supporting ``**`` recursion."""
    if not pattern:
        return not path
    head, *rest = pattern
    if head == "**":
        # `**` consumes zero or more path segments.
        return any(_match_parts(tuple(rest), path[i:]) for i in range(len(path) + 1))
    if not path:
        return False
    if fnmatch.fnmatchcase(path[0], head):
        return _match_parts(tuple(rest), path[1:])
    return False


def _match_pattern(pattern: str, relative_path: str) -> bool:
    """Match a single destination pattern against a relative path."""
    pattern_parts = PurePosixPath(pattern).parts
    path_parts = PurePosixPath(relative_path).parts
    return _match_parts(pattern_parts, path_parts)


def is_conformant(writer: str, relative_path: str) -> bool:
    """Return True when ``relative_path`` stays inside the writer's layout.

    Args:
        writer: Writer name from the REQ-101 taxonomy.
        relative_path: Artifact path relative to the Knowledge Lake root.

    Returns:
        True when the path matches at least one canonical destination.
    """
    if writer not in WRITER_DESTINATIONS:
        return False
    return any(
        _match_pattern(pattern, relative_path)
        for pattern in WRITER_DESTINATIONS[writer]
    )


def assert_conformance(writer: str, relative_path: str) -> None:
    """Assert a write lands in the writer's canonical layout.

    Args:
        writer: Writer name from the REQ-101 taxonomy.
        relative_path: Artifact path relative to the Knowledge Lake root.

    Raises:
        ConformanceError: if the writer is unknown (listing valid
            destinations) or the path escapes the mapped layout (naming
            the offending path).
    """
    if writer not in WRITER_DESTINATIONS:
        destinations = sorted(
            {d for dests in WRITER_DESTINATIONS.values() for d in dests}
        )
        raise ConformanceError(
            f"Unknown writer {writer!r}; "
            f"valid destinations: {', '.join(destinations)}"
        )
    if not is_conformant(writer, relative_path):
        raise ConformanceError(
            f"Off-layout write for writer {writer!r}: {relative_path!r} "
            f"is outside mapped destinations "
            f"{WRITER_DESTINATIONS[writer]}"
        )
