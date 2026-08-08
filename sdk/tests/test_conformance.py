"""Conformance tests for the Knowledge Lake taxonomy (REQ-402, REQ-101).

Every writer MUST emit only into its mapped canonical directories. A write
outside the mapped layout MUST fail, naming the offending path. Unknown
writers MUST be refused, listing the valid destinations.
"""

import pytest

from quantlab.knowledge.conformance import (
    WRITER_DESTINATIONS,
    ConformanceError,
    assert_conformance,
    canonical_destination,
    is_conformant,
)

# Writers from the REQ-101 taxonomy table.
REQ101_WRITERS = [
    "memory_capture",
    "pipeline",
    "config_writer",
    "raw_exporter",
    "metrics_writer",
    "embedding_writer",
    "training_exporter",
    "kb_seeder",
    "version_events",
]


class TestWriterMap:
    """REQ-402: every writer maps to a canonical destination."""

    def test_every_req101_writer_has_canonical_destination(self) -> None:
        for writer in REQ101_WRITERS:
            destinations = canonical_destination(writer)
            assert destinations, f"writer {writer!r} has no canonical destination"
            assert all(isinstance(d, str) and d for d in destinations)

    def test_every_mapped_writer_is_in_writer_map(self) -> None:
        for writer in WRITER_DESTINATIONS:
            assert writer in REQ101_WRITERS


class TestConformantPaths:
    """Canonical artifact locations pass conformance."""

    def test_canonical_artifacts_are_conformant(self) -> None:
        cases = [
            ("memory_capture", "agent-memory/research-director/campaign-7/memory.yaml"),
            ("pipeline", "pipeline-runs/run-42.yaml"),
            ("config_writer", "structured/campaign-7/config.yaml"),
            ("raw_exporter", "raw/backtest-1.csv"),
            ("metrics_writer", "structured/campaign-7/metrics.yaml"),
            ("embedding_writer", "embeddings/campaign-7.npy"),
            ("training_exporter", "datasets/train.jsonl"),
            ("kb_seeder", "structured/sqx-kb/144.2953/parameters/Ranking/entry.yaml"),
            ("version_events", "structured/sqx-version/144.2953→144.2954/checklist.yaml"),
        ]
        for writer, rel_path in cases:
            assert is_conformant(writer, rel_path), (
                f"{rel_path!r} should be conformant for writer {writer!r}"
            )
            assert_conformance(writer, rel_path)  # must not raise

    def test_campaign_dir_matches_config_writer(self) -> None:
        # Triangulation: a campaign directory with non-metric files is a
        # config_writer destination, not a metrics_writer destination.
        assert is_conformant("config_writer", "structured/campaign-7/stats.yaml")
        assert not is_conformant("metrics_writer", "structured/campaign-7/stats.yaml")

    def test_metrics_writer_requires_metrics_yaml_basename(self) -> None:
        # Different code path: same directory, wrong basename -> off-layout.
        assert not is_conformant("metrics_writer", "structured/campaign-7/summary.yaml")


class TestOffLayoutWrites:
    """REQ-402 scenario: off-layout writes fail, naming the offending path."""

    def test_off_layout_write_fails_naming_path(self) -> None:
        with pytest.raises(ConformanceError) as exc:
            assert_conformance("metrics_writer", "raw/leaked-metrics.yaml")
        assert "raw/leaked-metrics.yaml" in str(exc.value)

    def test_unknown_writer_refused_with_destinations(self) -> None:
        with pytest.raises(ConformanceError) as exc:
            assert_conformance("mystery_writer", "raw/x.yaml")
        message = str(exc.value)
        assert "mystery_writer" in message
        assert "raw" in message  # valid destinations are listed

    def test_traversal_escape_is_off_layout(self) -> None:
        # A `..` escape must never match raw/**.
        assert not is_conformant("raw_exporter", "../secrets.env")
        with pytest.raises(ConformanceError):
            assert_conformance("raw_exporter", "../secrets.env")
