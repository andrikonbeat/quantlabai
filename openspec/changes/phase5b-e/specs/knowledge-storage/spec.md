# Delta Spec: knowledge-storage (Phase 5b-5e)

## MODIFIED Requirements

### Requirement: Extended Index Schema

The system MUST extend `knowledge/index.yaml` from version 1 to version 2 with campaign-level metric fields and metadata. Each entry under `structured/` and `results/` directories (campaign artifacts) SHALL include:

```yaml
# index.yaml v2 example
_generated: "2024-07-18T12:00:00Z"
_version: "2"
directories:
  structured:
    "structured/campaign-123/":
      size: 4096
      sha256: "abc123..."
      created: "2024-07-18T10:00:00Z"
      campaign_id: "campaign-123"
      sharpe: 1.85
      profit_factor: 1.42
      win_rate: 58.5
      max_drawdown: 12.3
      total_trades: 247
      net_profit: 15420.50
      tags:
        strategy: "trend_following"
        market: "forex"
        timeframe: "H1"
      links:
        - "campaign-456"
        - "campaign-789"
```

**New fields per campaign entry:**
| Field | Type | Description |
|-------|------|-------------|
| `campaign_id` | string | Unique campaign identifier |
| `sharpe` | float/null | Sharpe ratio from statistics.yaml |
| `profit_factor` | float/null | Profit Factor |
| `win_rate` | float/null | Win rate percentage (0-100) |
| `max_drawdown` | float/null | Max drawdown percentage (0-100) |
| `total_trades` | int/null | Total trade count |
| `net_profit` | float/null | Net profit |
| `tags` | dict[str,str] | User-defined tags (default: {}) |
| `links` | list[string] | Related campaign IDs (default: []) |

Backward compatibility: v1 entries (without these fields) are valid — missing fields default to `null`, `{}`, `[]`.

#### Scenario: Rebuild index populates new metric fields
- GIVEN campaigns with `statistics.yaml` in `structured/{campaign_id}/`
- WHEN `KnowledgeStore.rebuild_index()` called
- THEN index v2 includes all metric fields extracted from statistics

#### Scenario: Tags and links stored in index
- GIVEN `store.tag("campaign-1", {"strategy": "mean_reversion"})` and `store.link("campaign-1", ["campaign-2"])`
- WHEN index rebuilt
- THEN campaign-1 entry has `tags: {strategy: mean_reversion}` and `links: [campaign-2]`

#### Scenario: Legacy index v1 entries work
- GIVEN existing index.yaml with `_version: "1"` and no metric fields
- WHEN `read_index()` called
- THEN returns index with v2 defaults for missing fields

---

### Requirement: Tag Management API

The system MUST add to `KnowledgeStore`:

```python
def tag(self, campaign_id: str, tags: dict[str, str]) -> None:
    """Add/update tags for a campaign. Merges with existing tags."""
    
def get_tags(self, campaign_id: str) -> dict[str, str]:
    """Retrieve tags for a campaign. Returns {} if none."""
```

Tags persisted in `structured/{campaign_id}/metadata.yaml` under `tags:` key. Index updated on next rebuild.

#### Scenario: Tag merge preserves existing
- GIVEN campaign has `tags: {author: "alice"}`
- WHEN `store.tag(campaign, {"version": "v2"})`
- THEN metadata has `{author: "alice", version: "v2"}`

#### Scenario: Empty tags returns empty dict
- GIVEN campaign with no metadata.yaml
- WHEN `get_tags(campaign)` called
- THEN returns `{}`

---

### Requirement: Link Management API

The system MUST add to `KnowledgeStore`:

```python
def link(self, parent_id: str, children_ids: list[str]) -> None:
    """Create bidirectional links: parent→children, children→parent."""
    
def get_links(self, campaign_id: str) -> list[str]:
    """Return all linked campaign IDs (parents + children)."""
```

Links persisted in `metadata.yaml` under `links:` key for both parent and children. Index updated on rebuild.

#### Scenario: Bidirectional link created
- GIVEN `store.link("parent", ["child1", "child2"])`
- WHEN `get_links("parent")` → `["child1", "child2"]`
- AND `get_links("child1")` → `["parent"]`
- AND `get_links("child2")` → `["parent"]`

#### Scenario: Duplicate link idempotent
- GIVEN link already exists
- WHEN `link()` called again
- THEN no duplicate entries in links list

---

## ADDED Requirements (New Capabilities from Knowledge Query)

These are NEW requirements that extend knowledge-storage to support Feature 5c (Knowledge Query). They are part of the same delta because they modify the same module.

### Requirement: QueryBuilder Support via KnowledgeStore

The system MUST add to `KnowledgeStore`:

```python
def query(self) -> QueryBuilder:
    """Return a QueryBuilder initialized with current index."""
```

Returns `QueryBuilder` from `quantlab.knowledge.query` (new module in Feature 5c) with the loaded index.

---

## Interface Specifications (Delta)

```python
# quantlab.knowledge.models (NEW FILE - shared with 5c)
class CampaignMetrics(BaseModel):
    sharpe: float | None = None
    profit_factor: float | None = None
    win_rate: float | None = None
    max_drawdown: float | None = None
    total_trades: int | None = None
    net_profit: float | None = None

class CampaignIndexEntry(BaseModel):  # Extends existing entry concept
    path: str
    size: int
    sha256: str
    created: str
    campaign_id: str | None = None
    metrics: CampaignMetrics = Field(default_factory=CampaignMetrics)
    tags: dict[str, str] = Field(default_factory=dict)
    links: list[str] = Field(default_factory=list)

# quantlab.knowledge.store (EXTENDED)
class KnowledgeStore:
    # ... existing methods ...
    
    def tag(self, campaign_id: str, tags: dict[str, str]) -> None: ...
    def get_tags(self, campaign_id: str) -> dict[str, str]: ...
    def link(self, parent_id: str, children_ids: list[str]) -> None: ...
    def get_links(self, campaign_id: str) -> list[str]: ...
    def query(self) -> QueryBuilder: ...
    
    # Modified: rebuild_index now produces v2 index
    def rebuild_index(self) -> dict: ...  # Returns v2 index with metrics/tags/links
```

---

## Data Flow (Extended)

```
KnowledgeStore.rebuild_index()
       │
       ├─► Walk structured/{campaign_id}/
       │       ├─► Read statistics.yaml → CampaignMetrics
       │       ├─► Read metadata.yaml → tags, links
       │       └─► Build CampaignIndexEntry
       │
       ├─► Walk results/ (same)
       │
       └─► Write index.yaml v2 with all fields
       
KnowledgeStore.tag(campaign_id, tags)
       │
       └─► Update structured/{campaign_id}/metadata.yaml tags section

KnowledgeStore.link(parent, children)
       │
       ├─► Update parent metadata.yaml links += children
       └─► For each child: update child metadata.yaml links += parent
```

---

## Acceptance Criteria (Delta)

| Criterion | Verification |
|-----------|--------------|
| Index v2 includes sharpe, pf, win_rate, mdd, tags, links | Unit test: `rebuild_index()` → inspect index.yaml |
| v1 index readable with defaults | Unit test: load v1 fixture, `read_index()` has defaults |
| `tag()` merges with existing | Integration: tag → re-tag → assert both |
| `link()` creates bidirectional | Integration: link A→B → assert B links to A |
| `get_tags()` returns {} for no tags | Unit test: campaign without metadata |
| `get_links()` returns combined parents+children | Integration: A→B, C→A → `get_links(A)` = [B, C] |
| `query()` returns QueryBuilder with loaded index | Unit test: mock index, assert builder has data |
| Existing 507 tests pass | Run full test suite |
| Index rebuild < 30s for 10k campaigns | Performance test (optional) |

---

## Migration Notes

- **Index version bump**: `_version: "2"` in index.yaml
- **Backward compatible**: v1 index entries work (defaults applied)
- **No breaking changes** to existing `KnowledgeStore` methods
- **New file**: `models.py` for shared types (used by 5c QueryBuilder)
- **Rebuild required**: After upgrade, run `rebuild_index()` to populate new fields