"""Wiki adapter for public JForex/SQX documentation sources.

Fetches public wiki pages, normalizes HTML to Markdown, and writes
version-pinned docs under ``structured/jforex-kb/{ver}/``. Gated/account-only
URLs are skipped with a warning (REQ-KDI-04).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import yaml

from quantlab.knowledge.ingest.adapters import DocRecord, _front_matter, _sha256_of, _slugify

logger = logging.getLogger(__name__)

# URL patterns that indicate gated/account-only content (REQ-KDI-04).
_GATED_PATTERNS = (
    "/login",
    "/account",
    "/manual",
    "/user-manual",
    "/members",
    "/premium",
    "/paid",
)


class WikiAdapter:
    """Fetch and normalize public wiki pages into Markdown docs.

    Args:
        urls: Public wiki URLs to ingest.
        version: Version bucket for the output docs.
        knowledge_root: Knowledge Lake root.
    """

    def __init__(self, urls: list[str], version: str, knowledge_root: Path | str | None = None) -> None:
        self._urls = urls
        self._version = version
        self._root = Path(knowledge_root) if knowledge_root else Path("knowledge")

    def iter_records(self) -> Iterator[DocRecord]:
        for url in self._urls:
            if self._is_gated(url):
                logger.warning("WikiAdapter: skip gated URL %s", url)
                continue

            try:
                import httpx

                response = httpx.get(url, follow_redirects=True, timeout=15.0)
                response.raise_for_status()
                html = response.text
            except Exception as exc:
                logger.warning("WikiAdapter: failed to fetch %s (%s)", url, exc)
                continue

            markdown = self._html_to_markdown(html, url)
            slug = _slugify(url.split("/")[-1] or "wiki-page")
            provenance = {
                "source": url,
                "license": "public-wiki",
                "fetched_at": _sha256_of(markdown)[:16],  # stable pseudo-timestamp
            }
            provenance["sha256"] = _sha256_of(provenance["source"] + markdown)
            content = (
                f"---\n"
                f"{_front_matter(provenance)}"
                f"---\n"
                f"{markdown}"
            )
            yield DocRecord(
                slug=slug,
                kind="jforex",
                version=self._version,
                content=content,
                provenance=provenance,
            )

    @staticmethod
    def _is_gated(url: str) -> bool:
        lowered = url.lower()
        return any(pattern in lowered for pattern in _GATED_PATTERNS)

    @staticmethod
    def _html_to_markdown(html: str, source_url: str) -> str:
        """Minimal HTML→Markdown normalization for wiki pages."""
        # Remove scripts, styles, and comments.
        cleaned = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<style[^>]*>.*?</style>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
        # Headings.
        cleaned = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", lambda m: f"\n{'#' * int(m.group(0)[2])} {m.group(1)}\n", cleaned, flags=re.DOTALL | re.IGNORECASE)
        # Paragraphs and line breaks.
        cleaned = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
        # Links.
        cleaned = re.sub(r'<a[^>]+href="([^"]*)"[^>]*>(.*?)</a>', lambda m: f"[{m.group(2)}]({m.group(1)})", cleaned, flags=re.DOTALL | re.IGNORECASE)
        # Lists.
        cleaned = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", cleaned, flags=re.DOTALL | re.IGNORECASE)
        # Strip remaining tags.
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        # Normalize whitespace.
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = cleaned.strip()
        if not cleaned:
            cleaned = f"_Source: {source_url}_\n"
        return cleaned


__all__ = ["WikiAdapter"]
