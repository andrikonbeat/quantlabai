"""Tests for QueryBuilder.query_docs (REQ-KDQ-01/02, U6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantlab.knowledge.query import QueryBuilder


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def knowledge_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    root.mkdir()
    return root


@pytest.fixture()
def index_with_docs(knowledge_root: Path) -> dict:
    docs_dir = knowledge_root / "structured" / "sqx-kb" / "144.2953" / "docs" / "blocks"
    docs_dir.mkdir(parents=True)
    (docs_dir / "rsi.md").write_text("RSI indicator block parameters", encoding="utf-8")
    (docs_dir / "macd.md").write_text("MACD indicator block parameters", encoding="utf-8")

    api_dir = knowledge_root / "structured" / "sqx-kb" / "144.2953" / "docs" / "apis"
    api_dir.mkdir(parents=True)
    (api_dir / "iordercomputer.md").write_text("Order computer interface", encoding="utf-8")

    return {
        "_version": "5",
        "docs": {
            "structured/sqx-kb/144.2953/docs/blocks/rsi.md": {"size": 100, "sha256": "abc", "kind": "block", "version": "144.2953"},
            "structured/sqx-kb/144.2953/docs/blocks/macd.md": {"size": 100, "sha256": "def", "kind": "block", "version": "144.2953"},
            "structured/sqx-kb/144.2953/docs/apis/iordercomputer.md": {"size": 50, "sha256": "ghi", "kind": "api", "version": "144.2953"},
        },
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestQueryDocs:
    """query_docs returns ranked docs with optional filters."""

    def test_query_docs_returns_results(self, knowledge_root: Path, index_with_docs: dict) -> None:
        qb = QueryBuilder(index=index_with_docs, root=knowledge_root)
        result = qb.query_docs("RSI indicator parameters", top_k=2)
        assert len(result.docs) <= 2
        assert result.total_count == 3

    def test_query_docs_filters_by_version(self, knowledge_root: Path, index_with_docs: dict) -> None:
        index_with_docs["docs"]["structured/sqx-kb/999.0/docs/blocks/other.md"] = {"size": 10, "sha256": "zzz", "kind": "block", "version": "999.0"}
        qb = QueryBuilder(index=index_with_docs, root=knowledge_root)
        result = qb.query_docs("RSI", version="144.2953")
        assert all(doc["version"] == "144.2953" for doc in result.docs)

    def test_query_docs_filters_by_kind(self, knowledge_root: Path, index_with_docs: dict) -> None:
        qb = QueryBuilder(index=index_with_docs, root=knowledge_root)
        result = qb.query_docs("interface", kind="api", top_k=5)
        assert all(doc["kind"] == "api" for doc in result.docs)

    def test_query_docs_empty_query_returns_empty(self, knowledge_root: Path, index_with_docs: dict) -> None:
        qb = QueryBuilder(index=index_with_docs, root=knowledge_root)
        result = qb.query_docs("", top_k=5)
        assert result.docs == []
        assert result.total_count == 0

    def test_query_docs_scores_descending(self, knowledge_root: Path, index_with_docs: dict) -> None:
        qb = QueryBuilder(index=index_with_docs, root=knowledge_root)
        result = qb.query_docs("RSI indicator block parameters", top_k=5)
        scores = [doc["score"] for doc in result.docs]
        assert scores == sorted(scores, reverse=True)
