"""Normalised result models for literature providers.

These dataclasses define the contract between literature providers
(academic papers, quant blogs) and consumers (e.g. ``LLMResearchAgent``).
``NewsItem`` does not fit papers: its ``sentiment`` field is meaningless
for a paper, and it lacks ``authors``, ``arxiv_id`` and ``categories``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, order=True)
class PaperItem:
    """A single academic paper from any literature provider.

    Attributes:
        title: Paper title.
        authors: List of author names.
        abstract: Paper abstract.
        url: Link to the paper (DOI, arXiv abs page, SSRN page).
        arxiv_id: arXiv identifier (e.g. ``"1706.03762"``), if applicable.
        categories: Subject categories (e.g. ``["q-fin.CP", "cs.LG"]``).
        published_at: Publication timestamp, if known.
        source: Provider identifier (e.g. ``"arxiv"``).
    """

    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    url: str = ""
    arxiv_id: str | None = None
    categories: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    source: str = ""
