"""Tests for WikiAdapter (REQ-KDI-03/04, U5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantlab.knowledge.ingest.wiki import WikiAdapter


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def knowledge_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    root.mkdir()
    return root


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestWikiAdapter:
    """WikiAdapter ingests public wiki pages and skips gated URLs."""

    def test_gated_url_skipped(self, knowledge_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = WikiAdapter(
            urls=["https://example.com/login", "https://example.com/manual"],
            version="144.2953",
            knowledge_root=knowledge_root,
        )
        records = list(adapter.iter_records())
        assert records == []

    def test_public_url_fetched_and_normalized(
        self, knowledge_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_html = "<html><body><h1>JForex API</h1><p>Hello world.</p></body></html>"

        class FakeResponse:
            status_code = 200
            text = fake_html

            def raise_for_status(self) -> None:
                pass

        monkeypatch.setattr("httpx.get", lambda url, **kwargs: FakeResponse())

        adapter = WikiAdapter(
            urls=["https://example.com/wiki/jforex-api"],
            version="144.2953",
            knowledge_root=knowledge_root,
        )
        records = list(adapter.iter_records())
        assert len(records) == 1
        assert "JForex API" in records[0].content
        assert records[0].kind == "jforex"
        assert records[0].version == "144.2953"

    def test_provenance_has_license_public_wiki(
        self, knowledge_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_html = "<html><body><p>Public content.</p></body></html>"

        class FakeResponse:
            status_code = 200
            text = fake_html

            def raise_for_status(self) -> None:
                pass

        monkeypatch.setattr("httpx.get", lambda url, **kwargs: FakeResponse())

        adapter = WikiAdapter(
            urls=["https://example.com/public-page"],
            version="144.2953",
            knowledge_root=knowledge_root,
        )
        records = list(adapter.iter_records())
        assert records[0].provenance["license"] == "public-wiki"
        assert "source:" in records[0].content

    def test_gated_patterns_cover_common_urls(self) -> None:
        gated = [
            "https://example.com/login",
            "https://example.com/account/settings",
            "https://example.com/manual/intro",
            "https://example.com/user-manual",
            "https://example.com/members/area",
            "https://example.com/premium/docs",
            "https://example.com/paid/content",
        ]
        for url in gated:
            assert WikiAdapter._is_gated(url), f"Expected gated: {url}"
