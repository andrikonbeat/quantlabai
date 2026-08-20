"""Tests for SQXDocProvider.get_doc general doc lookup (REQ-SDP-01, tasks T-02/T-03).

Covers:
- block/api kinds resolve ``structured/sqx-kb/{ver}/docs/{kind}s/{slug}.md``
  and return a DocRef carrying the Java snippet reference.
- cheat-sheet kind resolves ``structured/sqx-kb/{ver}/cheat-sheets/``
  (design D7, mirrors the educational/ pattern).
- Missing docs return None with a logged warning; version isolation applies
  (REQ-F2-02); the parameter YAML API is unchanged (backward compatibility).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from quantlab.knowledge.sqX_doc_provider import DocRef, SQXDocProvider


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def knowledge_root(tmp_path: Path) -> Path:
    return tmp_path / "knowledge"


@pytest.fixture()
def provider(knowledge_root: Path) -> SQXDocProvider:
    return SQXDocProvider(knowledge_root=knowledge_root)


def _write_doc(
    root: Path,
    version: str,
    *,
    kind: str,
    slug: str,
    content: str,
) -> Path:
    kind_dir = {
        "block": "docs/blocks",
        "api": "docs/apis",
        "cheat-sheet": "cheat-sheets",
    }[kind]
    path = root / "structured" / "sqx-kb" / version / kind_dir / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


_RSI_DOC = """\
---
source: internal/autocomplete/docs.json
snippet: Snippets/SQ/Blocks/Indicators/RSI.java
---
# RSI block

Relative Strength Index with configurable period and applied price.
"""


# ── Task T-02: get_doc block/api lookup ───────────────────────────────────────


class TestGetDocBlockLookup:
    """get_doc('block', ...) resolves version-pinned docs with snippet refs."""

    def test_block_doc_returns_docref_with_snippet(
        self, provider: SQXDocProvider, knowledge_root: Path
    ) -> None:
        _write_doc(knowledge_root, "144.2953", kind="block", slug="rsi", content=_RSI_DOC)
        doc = provider.get_doc("block", "RSI", "144.2953")
        assert doc is not None
        assert isinstance(doc, DocRef)
        assert doc.kind == "block"
        assert doc.name == "RSI"
        assert doc.version == "144.2953"
        assert doc.path.endswith("docs/blocks/rsi.md")
        assert "Relative Strength Index" in doc.content
        assert doc.snippet == "Snippets/SQ/Blocks/Indicators/RSI.java"

    def test_missing_doc_returns_none_and_warns(
        self, provider: SQXDocProvider, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(
            logging.WARNING, logger="quantlab.knowledge.sqX_doc_provider"
        ):
            doc = provider.get_doc("block", "NoSuchBlock", "144.2953")
        assert doc is None
        assert any("NoSuchBlock" in record.message for record in caplog.records)

    def test_unknown_kind_returns_none_and_warns(
        self, provider: SQXDocProvider, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(
            logging.WARNING, logger="quantlab.knowledge.sqX_doc_provider"
        ):
            doc = provider.get_doc("manual", "RSI", "144.2953")
        assert doc is None
        assert any("manual" in record.message for record in caplog.records)

    def test_version_isolation(
        self, provider: SQXDocProvider, knowledge_root: Path
    ) -> None:
        _write_doc(knowledge_root, "144.2953", kind="block", slug="rsi", content=_RSI_DOC)
        _write_doc(
            knowledge_root,
            "145.0",
            kind="block",
            slug="rsi",
            content="# RSI v145\n\nNew semantics for 145.0.\n",
        )
        doc_old = provider.get_doc("block", "RSI", "144.2953")
        doc_new = provider.get_doc("block", "RSI", "145.0")
        assert doc_old is not None and doc_new is not None
        assert "145.0" in doc_new.content
        assert "145.0" not in doc_old.content

    def test_api_kind_resolves_apis_dir(
        self, provider: SQXDocProvider, knowledge_root: Path
    ) -> None:
        _write_doc(
            knowledge_root,
            "144.2953",
            kind="api",
            slug="strategy-new",
            content="# POST /strategy/new\n\nCreates a strategy.\n",
        )
        doc = provider.get_doc("api", "strategy-new", "144.2953")
        assert doc is not None
        assert doc.path.endswith("docs/apis/strategy-new.md")
        assert "POST /strategy/new" in doc.content

    def test_slug_normalization(
        self, provider: SQXDocProvider, knowledge_root: Path
    ) -> None:
        _write_doc(
            knowledge_root,
            "144.2953",
            kind="block",
            slug="stop-loss",
            content="# Stop Loss block\n",
        )
        doc = provider.get_doc("block", "Stop Loss", "144.2953")
        assert doc is not None
        assert doc.path.endswith("docs/blocks/stop-loss.md")

    def test_parameter_api_unchanged(
        self, provider: SQXDocProvider, knowledge_root: Path
    ) -> None:
        # Backward compatibility: parameter YAML lookups keep working next to
        # the new doc surface (REQ-SDP-01: REQ-F2-01..03 unchanged).
        _write_doc(knowledge_root, "144.2953", kind="block", slug="rsi", content=_RSI_DOC)
        yaml_dir = knowledge_root / "structured" / "sqx-kb" / "144.2953" / "parameters" / "Indicators"
        yaml_dir.mkdir(parents=True, exist_ok=True)
        import yaml

        (yaml_dir / "RSI.yaml").write_text(
            yaml.dump(
                {"name": "RSI", "type": "int", "range": [2, 200], "description": "RSI"},
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        assert provider.get_valid_range("Indicators", "RSI", "144.2953") == (2, 200)
        assert provider.get_description("Indicators", "RSI", "144.2953") == "RSI"


# ── Task T-03: cheat-sheet kind ───────────────────────────────────────────────


class TestGetDocCheatSheet:
    """get_doc('cheat-sheet', ...) reads structured/sqx-kb/{ver}/cheat-sheets/."""

    def test_cheat_sheet_from_fixture_root(
        self, provider: SQXDocProvider, knowledge_root: Path
    ) -> None:
        _write_doc(
            knowledge_root,
            "144.2953",
            kind="cheat-sheet",
            slug="block-to-snippet",
            content="# Block -> Snippet\n\nCurated mapping.\n",
        )
        doc = provider.get_doc("cheat-sheet", "block-to-snippet", "144.2953")
        assert doc is not None
        assert doc.path.endswith("cheat-sheets/block-to-snippet.md")
        assert "Curated mapping" in doc.content

    def test_committed_cheat_sheets_reachable_from_repo_root(self) -> None:
        # The 3 curated cheat-sheets committed in this PR must be reachable
        # through the default knowledge root (design D7).
        provider = SQXDocProvider()
        for slug in ("block-to-snippet", "jforex-lifecycle", "sqx-http-api"):
            doc = provider.get_doc("cheat-sheet", slug, "144.2953")
            assert doc is not None, f"committed cheat-sheet '{slug}' not found"
            assert doc.content.strip(), f"cheat-sheet '{slug}' is empty"
            assert "knowledge/raw" not in doc.content, (
                f"cheat-sheet '{slug}' must not embed raw corpus content"
            )