"""Tests for DocIndexer ingest core (REQ-KDI-02/03, U4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantlab.knowledge.ingest import DocIndexer, IngestStats


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def fake_sqx_install(tmp_path: Path) -> Path:
    install = tmp_path / "SQX"
    install.mkdir()
    (install / "internal" / "autocomplete").mkdir(parents=True)
    (install / "internal" / "extend" / "Snippets" / "SQ" / "Blocks").mkdir(parents=True)
    (install / "internal" / "extend" / "Code" / "JForex").mkdir(parents=True)

    docs_json = {
        "com.strategyquant.tradinglib.blocks.RSI": "RSI indicator block",
        "com.strategyquant.tradinglib.blocks.MACD": "MACD indicator block",
        "com.strategyquant.tradinglib.results.stats.IOrderComputer": "Order computer interface",
    }
    (install / "internal" / "autocomplete" / "docs.json").write_text(
        json.dumps(docs_json), encoding="utf-8"
    )
    (install / "internal" / "extend" / "Snippets" / "SQ" / "Blocks" / "RSI").mkdir(parents=True)
    (install / "internal" / "extend" / "Snippets" / "SQ" / "Blocks" / "RSI" / "RSIIndicator.java").write_text(
        "public class RSI {}", encoding="utf-8"
    )
    (install / "internal" / "extend" / "Code" / "JForex" / "Main.tpl").write_text(
        "// template", encoding="utf-8"
    )
    return install


@pytest.fixture()
def knowledge_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    root.mkdir()
    return root


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDocIndexer:
    """DocIndexer writes version-pinned docs with provenance."""

    def test_ingest_writes_docs_from_docs_json(
        self, fake_sqx_install: Path, knowledge_root: Path
    ) -> None:
        indexer = DocIndexer(knowledge_root=knowledge_root, install_path=fake_sqx_install)
        stats = indexer.ingest(version="144.2953", source="sqx-install")

        assert stats.docs_written >= 3
        blocks_dir = knowledge_root / "structured" / "sqx-kb" / "144.2953" / "docs" / "blocks"
        assert any("rsi" in p.name for p in blocks_dir.glob("*.md"))
        apis_dir = knowledge_root / "structured" / "sqx-kb" / "144.2953" / "docs" / "apis"
        assert any("iordercomputer" in p.name for p in apis_dir.glob("*.md"))

    def test_ingest_idempotent_skips_unchanged(
        self, fake_sqx_install: Path, knowledge_root: Path
    ) -> None:
        indexer = DocIndexer(knowledge_root=knowledge_root, install_path=fake_sqx_install)
        first = indexer.ingest(version="144.2953", source="sqx-install")
        second = indexer.ingest(version="144.2953", source="sqx-install")
        assert second.docs_skipped >= first.docs_written

    def test_ingest_version_pinning_does_not_overwrite(
        self, fake_sqx_install: Path, knowledge_root: Path
    ) -> None:
        indexer = DocIndexer(knowledge_root=knowledge_root, install_path=fake_sqx_install)
        indexer.ingest(version="144.2953", source="sqx-install")
        indexer.ingest(version="144.4000", source="sqx-install")
        assert (knowledge_root / "structured" / "sqx-kb" / "144.2953").is_dir()
        assert (knowledge_root / "structured" / "sqx-kb" / "144.4000").is_dir()

    def test_provenance_front_matter_present(
        self, fake_sqx_install: Path, knowledge_root: Path
    ) -> None:
        indexer = DocIndexer(knowledge_root=knowledge_root, install_path=fake_sqx_install)
        indexer.ingest(version="144.2953", source="sqx-install")
        blocks_dir = knowledge_root / "structured" / "sqx-kb" / "144.2953" / "docs" / "blocks"
        rsi_doc = next(p for p in blocks_dir.glob("*.md") if "rsi" in p.name)
        content = rsi_doc.read_text(encoding="utf-8")
        assert "source:" in content
        assert "license:" in content
        assert "fetched_at:" in content
        assert "sha256:" in content
