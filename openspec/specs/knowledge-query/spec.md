# Knowledge Lake Query/Search Specification

## Purpose

Provides a query layer over the Knowledge Lake index enabling filtering and discovery of campaigns by metrics (Sharpe, Profit Factor, Win Rate, Max Drawdown), tags, date ranges, and full-text search. Adds tagging and linking capabilities for campaign relationship management. Stdlib-only implementation (no new dependencies).

---

## Requirements

### Requirement: Extended Index Schema

The system MUST extend `knowledge/index.yaml` with campaign-level metric fields and metadata. Each index entry under `structured/` and `results/` (campaign directories) SHALL include:
- `campaign_id: str` — unique campaign identifier
- `created: str` — ISO8601 timestamp
- `sharpe: float | null` — Sharpe ratio from campaign statistics
- `profit_factor: float | null` — Profit Factor
- `win_rate: float | null` — Win rate percentage (0-100)
- `max_drawdown: float | null` — Max drawdown percentage (0-100)
- `total_trades: int | null` — Total trade count
- `net_profit: float | null` — Net profit
- `tags: dict[str, str]` — user-defined key-value tags (e.g., `{"strategy": "trend", "market": "forex"}`)
- `links: list[str]` — related campaign IDs (parent/child relationships)

Index version increments to `2`. Backward compatibility: missing fields default to `null`/`{}`/`[]`.

#### Scenario: Rebuild index populates metric fields
- GIVEN campaigns with `statistics.yaml` in `structured/{campaign_id}/`
- WHEN `KnowledgeStore.rebuild_index()` runs
- THEN index entries include `sharpe`, `profit_factor`, `win_rate`, `max_drawdown` extracted from statistics

#### Scenario: Tags and links persisted in index
- GIVEN `knowledge_store.tag("campaign-1", {"strategy": "mean_reversion"})`
- WHEN index is rebuilt
- THEN entry for `campaign-1` has `tags: {"strategy": "mean_reversion"}`

#### Scenario: Legacy index entries work without metrics
- GIVEN index.yaml version 1 without metric fields
- WHEN `read_index()` is called
- THEN entries have `sharpe: null`, `tags: {}`, `links: []` defaults

---

### Requirement: QueryBuilder API

The system MUST provide a `QueryBuilder` class with fluent API:

```python
class QueryBuilder:
    def filter_by_sharpe(self, min: float | None = None, max: float | None = None) -> Self
    def filter_by_profit_factor(self, min: float | None = None) -> Self
    def filter_by_win_rate(self, min: float | None = None, max: float | None = None) -> Self
    def filter_by_max_drawdown(self, max: float | None = None) -> Self
    def filter_by_tags(self, tags: dict[str, str]) -> Self          # ALL tags must match
    def filter_by_date(self, start: str | None = None, end: str | None = None) -> Self  # ISO8601 or "YYYY-MM-DD"
    def search_text(self, text: str, fields: list[str] | None = None) -> Self  # searches campaign_id, tags, stats summary
    def sort_by(self, field: str, descending: bool = True) -> Self  # field: sharpe, profit_factor, created, etc.
    def limit(self, n: int) -> Self
    def execute(self) -> QueryResult
```

`QueryResult` contains: `campaigns: list[CampaignSummary]`, `total_matches: int`, `query_time_ms: float`.

`CampaignSummary`: `campaign_id`, `created`, `sharpe`, `profit_factor`, `win_rate`, `max_drawdown`, `tags`, `links`, `artifact_path`.

All filters are AND-combined. `filter_by_tags` requires ALL specified tags to match (subset match). `search_text` does case-insensitive substring match on campaign_id, tag keys/values, and statistics summary text.

#### Scenario: Chain multiple filters
- GIVEN `qb.filter_by_sharpe(min=1.5).filter_by_tags({"market": "forex"}).limit(10)`
- WHEN `execute()` called
- THEN returns campaigns with Sharpe ≥ 1.5 AND tag market=forex, max 10 results, sorted by Sharpe desc

#### Scenario: Date range filter
- GIVEN `qb.filter_by_date("2024-01-01", "2024-12-31")`
- WHEN executed
- THEN returns campaigns with `created` timestamp in 2024

#### Scenario: Text search finds partial matches
- GIVEN campaigns with tags `{"strategy": "trend_following"}`
- WHEN `qb.search_text("trend").execute()`
- THEN matching campaigns returned

#### Scenario: Sort by profit factor ascending
- GIVEN `qb.sort_by("profit_factor", descending=False)`
- WHEN executed
- THEN results ordered by profit_factor low to high

---

### Requirement: Tag and Link Management

The system MUST provide `KnowledgeStore` methods:

```python
def tag(self, campaign_id: str, tags: dict[str, str]) -> None:
    """Add/update tags for a campaign. Merges with existing tags."""

def get_tags(self, campaign_id: str) -> dict[str, str]:
    """Retrieve tags for a campaign."""

def link(self, parent_id: str, children_ids: list[str]) -> None:
    """Create bidirectional links: parent→children, children→parent."""

def get_links(self, campaign_id: str) -> list[str]:
    """Return all linked campaign IDs (parents + children)."""
```

Tags are stored in the campaign's `metadata.yaml` and reflected in index on next rebuild. Links are stored in both campaigns' metadata.

#### Scenario: Add tags to existing campaign
- GIVEN campaign `campaign-1` exists
- WHEN `store.tag("campaign-1", {"author": "alice", "version": "v2"})`
- THEN `metadata.yaml` updated, index reflects new tags after rebuild

#### Scenario: Link parent to children
- GIVEN `campaign-parent` and `campaign-child-1`, `campaign-child-2`
- WHEN `store.link("campaign-parent", ["campaign-child-1", "campaign-child-2"])`
- THEN parent's `links` contains children, each child's `links` contains parent

#### Scenario: Tag merge preserves existing
- GIVEN campaign has `{"strategy": "trend"}`
- WHEN `tag(campaign, {"market": "forex"})`
- THEN tags become `{"strategy": "trend", "market": "forex"}`

---

### Requirement: Knowledge Query CLI

The system MUST provide `quantlab knowledge query [options]` CLI command:

Options:
- `--sharpe RANGE` — e.g., `">1.5"`, `">=1.0"`, `"<2.0"`, `"1.0..2.0"`
- `--pf RANGE` — profit factor range, same syntax
- `--win-rate RANGE` — win rate percentage range
- `--mdd RANGE` — max drawdown range
- `--tag KEY=VALUE` — repeatable, all must match (e.g., `--tag strategy=trend --tag market=forex`)
- `--date RANGE` — date range `START..END` (ISO8601 dates)
- `--text TEXT` — full-text search
- `--sort FIELD` — `sharpe`, `profit_factor`, `win_rate`, `max_drawdown`, `created`, `net_profit` (default: `sharpe`)
- `--desc` / `--asc` — sort direction (default: `--desc`)
- `--limit N` — max results (default: 20)
- `--json` — output as JSON array of CampaignSummary
- `--show-tags` / `--show-links` — include tags/links in output (default: on)

Output format (default): table with columns `campaign_id`, `created`, `sharpe`, `pf`, `win%`, `mdd%`, `trades`, `tags`.

#### Scenario: Query by Sharpe and tag
- GIVEN campaigns in Knowledge Lake
- WHEN `quantlab knowledge query --sharpe ">1.5" --tag strategy=trend`
- THEN table shows matching campaigns, exit code 0

#### Scenario: JSON output for scripting
- GIVEN `quantlab knowledge query --sharpe ">1.0" --json --limit 5`
- WHEN command runs
- THEN valid JSON array printed to stdout, each object has CampaignSummary fields

#### Scenario: Date range with text search
- GIVEN `quantlab knowledge query --date "2024-01-01..2024-06-30" --text "eurusd"`
- WHEN command runs
- THEN campaigns created in H1 2024 matching "eurusd" returned

#### Scenario: No matches returns empty result
- GIVEN `quantlab knowledge query --sharpe ">5.0"`
- WHEN no campaigns match
- THEN empty table/JSON array, exit code 0, message "No campaigns found"

---

### Requirement: Indexer Module

The system MUST provide an `Indexer` class (in `knowledge/indexer.py`) that:
- Scans `structured/{campaign_id}/statistics.yaml` and `metadata.yaml`
- Extracts metrics and tags
- Builds the extended index structure
- Handles missing/corrupt files gracefully (logs warning, uses defaults)

```python
class Indexer:
    def __init__(self, knowledge_root: Path):
        ...

    def extract_campaign_metrics(self, campaign_id: str) -> CampaignMetrics | None:
        """Read statistics.yaml, return CampaignMetrics or None if missing."""

    def extract_campaign_tags(self, campaign_id: str) -> dict[str, str]:
        """Read metadata.yaml tags section, return dict."""

    def build_index(self) -> dict:
        """Walk knowledge root, build full index dict with version 2 schema."""
```

#### Scenario: Missing statistics.yaml handled gracefully
- GIVEN campaign dir exists but no `statistics.yaml`
- WHEN `extract_campaign_metrics()` called
- THEN returns `None`, index entry gets `null` metrics

#### Scenario: Malformed YAML logs warning
- GIVEN `statistics.yaml` has invalid YAML
- WHEN indexer processes it
- THEN warning logged, campaign skipped, index continues building

---

## Data Flow

```
Knowledge Lake (filesystem)
       │
       ├─► Indexer.scan()
       │     ├─► Read structured/{id}/statistics.yaml → metrics
       │     ├─► Read structured/{id}/metadata.yaml → tags, links
       │     └─► Build index.yaml v2 with all fields
       │
       ├─► QueryBuilder
       │     ├─► Load index.yaml
       │     ├─► Apply filters (sharpe, tags, date, text)
       │     ├─► Sort, limit
       │     └─► Return QueryResult
       │
       └─► KnowledgeStore.tag()/link()
             ├─► Update metadata.yaml
             └─► Next rebuild_index() reflects changes
```

---

## Interface Specifications

```python
# quantlab.knowledge.models
class CampaignMetrics(BaseModel):
    sharpe: float | None = None
    profit_factor: float | None = None
    win_rate: float | None = None
    max_drawdown: float | None = None
    total_trades: int | None = None
    net_profit: float | None = None

class CampaignSummary(BaseModel):
    campaign_id: str
    created: str
    metrics: CampaignMetrics
    tags: dict[str, str] = Field(default_factory=dict)
    links: list[str] = Field(default_factory=list)
    artifact_path: str

class QueryResult(BaseModel):
    campaigns: list[CampaignSummary]
    total_matches: int
    query_time_ms: float

# quantlab.knowledge.query
class QueryBuilder:
    def __init__(self, index: dict):
        ...

    def filter_by_sharpe(self, min: float | None = None, max: float | None = None) -> Self: ...
    def filter_by_profit_factor(self, min: float | None = None) -> Self: ...
    def filter_by_win_rate(self, min: float | None = None, max: float | None = None) -> Self: ...
    def filter_by_max_drawdown(self, max: float | None = None) -> Self: ...
    def filter_by_tags(self, tags: dict[str, str]) -> Self: ...
    def filter_by_date(self, start: str | None = None, end: str | None = None) -> Self: ...
    def search_text(self, text: str, fields: list[str] | None = None) -> Self: ...
    def sort_by(self, field: str, descending: bool = True) -> Self: ...
    def limit(self, n: int) -> Self: ...
    def execute(self) -> QueryResult: ...

# quantlab.knowledge.indexer
class Indexer:
    def __init__(self, knowledge_root: Path): ...
    def extract_campaign_metrics(self, campaign_id: str) -> CampaignMetrics | None: ...
    def extract_campaign_tags(self, campaign_id: str) -> dict[str, str]: ...
    def build_index(self) -> dict: ...

# quantlab.knowledge.store (extended)
class KnowledgeStore:
    # ... existing methods ...
    def tag(self, campaign_id: str, tags: dict[str, str]) -> None: ...
    def get_tags(self, campaign_id: str) -> dict[str, str]: ...
    def link(self, parent_id: str, children_ids: list[str]) -> None: ...
    def get_links(self, campaign_id: str) -> list[str]: ...
    def query(self) -> QueryBuilder:  # returns QueryBuilder with current index
        ...
```

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Index v2 includes sharpe, pf, win_rate, mdd, tags, links | Unit test: `rebuild_index()` → assert index.yaml has fields |
| QueryBuilder chain returns correct filtered results | Unit test: create mock index, apply filters, assert results |
| Tag merge preserves existing tags | Integration: tag → re-tag → assert both present |
| Link creates bidirectional relationship | Integration: link A→B → assert B links to A |
| CLI `--sharpe ">1.5" --tag k=v` works | Integration test: run CLI, parse output |
| CLI `--json` outputs valid JSON array | Integration: run with `--json`, `json.loads()` succeeds |
| Text search finds substring in tags | Unit test: `search_text("trend")` matches `{"strategy": "trend_following"}` |
| Date range parses ISO8601 and YYYY-MM-DD | Unit test: `filter_by_date("2024-01-01", "2024-12-31")` |
| Sort by profit_factor ascending works | Unit test: `sort_by("profit_factor", descending=False)` |
| No new dependencies (stdlib only) | Check `pyproject.toml` — no new deps for knowledge |

---

## Non-Functional Requirements

- **Performance**: Query on 10k campaigns < 500ms (in-memory index filtering)
- **Index size**: ~1KB per campaign entry, ~10MB for 10k campaigns
- **Rebuild time**: < 30s for 10k campaigns (single-threaded)
- **Dependencies**: Zero new dependencies (uses `yaml`, `pathlib`, `dataclasses`, `datetime`)
- **Backward compatibility**: Index v1 entries work with defaults