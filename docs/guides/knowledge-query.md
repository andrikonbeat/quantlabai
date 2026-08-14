# Knowledge Query

Query, tag, link, and export campaigns from the Knowledge Lake — the filesystem-first research artifact repository.

> **SDK Reference**: [`sdk/quantlab/knowledge/`](../sdk/quantlab/knowledge/)

---

## CLI Commands

### `knowledge query`

Query campaigns with metric filters, tag matching, date ranges, and full-text search.

```bash
# Basic query — list all campaigns
quantlab knowledge query

# Filter by Sharpe ratio
quantlab knowledge query --sharpe ">1.5"
quantlab knowledge query --sharpe "<0.5"

# Filter by profit factor
quantlab knowledge query --pf ">1.2"

# Filter by win rate
quantlab knowledge query --win-rate ">0.5"

# Filter by max drawdown
quantlab knowledge query --dd "<10"

# Filter by tags (AND logic)
quantlab knowledge query --tags trend_following breakout

# Filter by date range
quantlab knowledge query --date 2024-01-01..2024-12-31

# Full-text search across campaign names and tags
quantlab knowledge query --text "EURUSD"

# Sort results
quantlab knowledge query --sort sharpe
quantlab knowledge query --sort created --desc

# Pagination
quantlab knowledge query --limit 10 --offset 20

# JSON output
quantlab knowledge query --sharpe ">1.0" --json

# Set knowledge root
quantlab knowledge query --knowledge-root /path/to/knowledge

# Combined
quantlab knowledge query \
  --sharpe ">1.0" \
  --pf ">1.2" \
  --tags trend_following \
  --sort sharpe \
  --json
```

#### Filter Options

| Option | Example | Description |
|--------|---------|-------------|
| `--sharpe` | `>1.5`, `<2.0` | Sharpe ratio filter |
| `--pf` | `>1.2` | Profit factor filter (min) |
| `--win-rate` | `>0.5` | Win rate filter (min) |
| `--dd` | `<10` | Max drawdown filter (upper bound) |
| `--tags` | `trend_following breakout` | Tag filters (AND match) |
| `--date` | `2024-01-01..2024-12-31` | Creation date range (`..` separator) |
| `--text` | `EURUSD` | Full-text search on name + tags |
| `--sort` | `created`, `sharpe`, `pf`, `win_rate`, `dd` | Sort field |
| `--desc` | — | Sort descending (default: yes) |
| `--limit` | `10` | Max results (default: 50) |
| `--offset` | `20` | Pagination offset |

#### Range Syntax

| Syntax | Meaning | Example |
|--------|---------|---------|
| `>value` | Greater than | `--sharpe ">1.5"` |
| `<value` | Less than | `--dd "<10"` |
| `start..end` | Date range | `--date 2024-01-01..2024-12-31` |

### `knowledge tag`

Add or remove tags from campaigns.

```bash
# Add tags
quantlab knowledge tag my_campaign trend_following breakout

# Remove tags
quantlab knowledge tag my_campaign breakout --remove

# Set knowledge root
quantlab knowledge tag my_campaign trend_following --knowledge-root /path/to/knowledge
```

Tags are stored in `knowledge/tags/{campaign_id}.yaml`.

### `knowledge link`

Create parent-child relationships between campaigns.

```bash
# Create links (parent → children)
quantlab knowledge link --parent campaign_v1 --children v1a v1b v1c

# List links for a campaign
quantlab knowledge link --list my_campaign

# JSON output for listing
quantlab knowledge link --list my_campaign --json
```

Links are stored bidirectionally in `knowledge/links/{campaign_id}.yaml`.

### `knowledge export`

Export filtered query results to CSV or JSON files.

```bash
# Export to CSV
quantlab knowledge export --sharpe ">1.0" --format csv --output results.csv

# Export to JSON
quantlab knowledge export --tags trend_following --format json --output results.json

# All filter options from `query` command are available
quantlab knowledge export \
  --sharpe ">1.5" \
  --pf ">1.2" \
  --format csv \
  --output top_campaigns.csv
```

#### Export Columns

| Column | Type | Description |
|--------|------|-------------|
| `campaign_id` | string | Campaign identifier |
| `name` | string | Campaign name |
| `sharpe_ratio` | float | Sharpe ratio |
| `profit_factor` | float | Profit factor |
| `win_rate` | float | Win rate (0.0–1.0) |
| `max_drawdown` | float | Maximum drawdown |
| `total_trades` | int | Total number of trades |
| `net_profit` | float | Net profit |
| `tags` | string | Comma-separated tags |
| `created` | string | ISO 8601 creation timestamp |
| `path` | string | Path in Knowledge Lake |

---

## Index Schema (v2)

The Knowledge Lake index (`knowledge/index.yaml`) uses a v2 schema with campaign metrics:

```yaml
_version: "2"
_generated: "2024-07-18T12:00:00"
directories:
  raw:
    "raw/campaign_123.yaml":
      size: 1234
      sha256: "abc..."
      created: "2024-01-01T00:00:00"
      metrics:
        sharpe_ratio: 1.5
        profit_factor: 1.2
        win_rate: 0.6
        max_drawdown: 5.0
        total_trades: 10
        net_profit: 1500.0
      tags: ["trend_following", "EURUSD"]
campaigns:
  campaign_123:
    campaign_id: "campaign_123"
    indexed_at: "2024-07-18T12:00:00"
    metrics:
      sharpe_ratio: 1.5
      profit_factor: 1.2
      win_rate: 0.6
      max_drawdown: 5.0
      total_trades: 10
      net_profit: 1500.0
    tags: ["trend_following", "EURUSD"]
```

### Indexed Metric Fields

| Field | Source | Description |
|-------|--------|-------------|
| `sharpe_ratio` | `knowledge/stats/{id}.yaml` | Sharpe ratio |
| `profit_factor` | `knowledge/stats/{id}.yaml` | Profit factor |
| `win_rate` | `knowledge/stats/{id}.yaml` | Win rate |
| `max_drawdown` | `knowledge/stats/{id}.yaml` | Max drawdown percentage |
| `total_trades` | `knowledge/stats/{id}.yaml` | Total trade count |
| `net_profit` | `knowledge/stats/{id}.yaml` | Net profit |

---

## Programmatic API

### Query Builder (Fluent)

```python
from pathlib import Path
from quantlab.knowledge.store import KnowledgeStore
from quantlab.knowledge.query import QueryBuilder

store = KnowledgeStore(root="knowledge")
store.initialize()
index = store.read_index()

builder = QueryBuilder(index, Path("knowledge"))

# Build query fluently
result = (
    builder
    .filter_by_sharpe(min_val=1.0)
    .filter_by_profit_factor(min_val=1.2)
    .filter_by_tags(["trend_following"])
    .sort_by("sharpe", ascending=False)
    .limit(10)
    .execute()
)

print(f"Found {result.total_count} campaigns")
for c in result.campaigns:
    print(f"  {c.campaign_id}: Sharpe={c.metrics.sharpe_ratio}")
```

### Tag/Link Management

```python
# Tag a campaign
store.tag("my_campaign", ["trend_following", "breakout"])

# Get tags
tags = store.get_tags("my_campaign")

# Link campaigns
store.link("parent_campaign", ["child_a", "child_b"])

# Get links
links = store.get_links("my_campaign")
print(f"Parents: {links.get('parents', [])}")
print(f"Children: {links.get('children', [])}")
```

### Enhanced Indexing

```python
# Rebuild index with v2 enriched schema
enriched_index = store.enhance_index()
print(f"Version: {enriched_index.get('_version')}")
print(f"Campaigns indexed: {len(enriched_index.get('campaigns', {}))}")
```

### QueryFilter Parameters

```python
from quantlab.knowledge.models import QueryFilter

filter = QueryFilter(
    sharpe_min=1.0,
    sharpe_max=None,
    profit_factor_min=1.2,
    win_rate_min=None,
    max_drawdown_max=10.0,
    tags=["trend_following"],
    date_start=datetime(2024, 1, 1),
    date_end=None,
    text_search="EURUSD",
    sort_by="sharpe",
    sort_ascending=False,
    limit=10,
    offset=0,
)
```

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| `No campaigns found` | Knowledge Lake not initialized | Run `store.initialize()` or call `knowledge query` without filters |
| `--sharpe >1.5` returns nothing | No stats YAML for campaign | Run statistics computation: `store.enhance_index()` |
| `knowledge tag` fails | Campaign not in Knowledge Lake | Verify campaign data exists in `knowledge/stats/` |
| Index not updating | Stale index | Call `store.rebuild_index()` or `store.enhance_index()` |
| Export file is empty | No campaigns match filter | Broaden filter criteria |
| `--date` range returns wrong results | Date format mismatch | Use ISO 8601 format: `YYYY-MM-DD` |
