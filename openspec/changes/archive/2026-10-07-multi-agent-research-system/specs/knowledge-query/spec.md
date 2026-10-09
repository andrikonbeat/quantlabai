# Delta for Knowledge Query

## MODIFIED Requirements

### Requirement: Extended Index Schema

The system MUST extend `knowledge/index.yaml` with agent-memory entries and campaign embedding references. Each index entry under `agent-memory/` SHALL include:
- `agent_name: str` — one of 8 agent names
- `campaign_id: str` — campaign identifier
- `memory_path: str` — relative path to memory.yaml
- `checkpoint_paths: list[str]` — checkpoint snapshots
- `last_updated: str` — ISO8601 timestamp
- `embedding_ref: str | null` — path to campaign embedding if available

Index version increments to `3`. Backward compatibility: missing fields default to `null`/`{}`/`[]`.
(Previously: version 2 with campaign metrics only)

#### Scenario: Rebuild index includes agent-memory entries
- GIVEN agent-memory directories with memory.yaml files
- WHEN `KnowledgeStore.rebuild_index()` runs
- THEN index entries include agent_name, campaign_id, memory_path, last_updated
- AND version = 3

#### Scenario: Legacy index entries work without agent-memory fields
- GIVEN index.yaml version 2 without agent-memory fields
- WHEN `read_index()` is called
- THEN entries have agent_name: null, memory_path: null defaults

### Requirement: QueryBuilder API

The system MUST extend `QueryBuilder` with agent-memory query support and campaign similarity search via embeddings.

```python
class QueryBuilder:
    # ... existing methods ...

    def filter_by_agent(self, agent_name: str) -> Self:
        """Filter to specific agent's memory entries."""

    def filter_by_campaign(self, campaign_id: str) -> Self:
        """Filter to specific campaign across all agents."""

    def search_similar_campaigns(
        self,
        campaign_id: str,
        top_k: int = 10,
        min_similarity: float = 0.7
    ) -> Self:
        """Find campaigns similar to given campaign using embeddings."""

    def search_agent_memory(
        self,
        text: str,
        agent_name: str | None = None,
        campaign_id: str | None = None
    ) -> Self:
        """Full-text search in agent memory.yaml files."""
```
(Previously: Only campaign metrics, tags, date, text search)

#### Scenario: Query agent memory for specific agent
- GIVEN `qb.filter_by_agent("research-agent").filter_by_campaign("campaign-123")`
- WHEN `execute()` called
- THEN returns agent memory entries for research-agent in campaign-123

#### Scenario: Cross-campaign similarity search
- GIVEN campaign "campaign-123" with embedding
- WHEN `qb.search_similar_campaigns("campaign-123", top_k=5, min_similarity=0.75)`
- THEN returns top 5 campaigns with cosine similarity ≥ 0.75

#### Scenario: Agent memory text search
- GIVEN `qb.search_agent_memory("RSI overshoot", agent_name="research-agent")`
- WHEN executed
- THEN returns memory entries containing "RSI overshoot" in research-agent memories

## ADDED Requirements

### Requirement: Campaign Similarity Search

The system MUST provide `KnowledgeStore.find_similar_campaigns(campaign_id, top_k, min_similarity)` using embedding vectors from `knowledge/embeddings/`.

#### Scenario: Similar campaigns found for re-optimization
- GIVEN campaign with Sharpe=1.6, EURUSD H1, mean_reversion
- WHEN `store.find_similar_campaigns(campaign_id, top_k=3, min_similarity=0.8)`
- THEN returns 3 campaigns with similar market/strategy profile
- AND results include similarity_score, campaign_id, key_metrics

### Requirement: Cross-Agent Query

The system MUST provide `KnowledgeStore.query_agent_memory(agent_name, campaign_id, query_text)` for ResearchDirector to access all agent memories.

#### Scenario: Director queries all agent memories
- GIVEN completed campaign with 8 agent memories
- WHEN `store.query_agent_memory(None, campaign_id, "drawdown")`
- THEN returns relevant entries from all 8 agents mentioning "drawdown"
- AND results tagged with agent_name for traceability

---

## REMOVED Requirements

None.

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Index v3 includes agent-memory fields | Unit test: rebuild_index → assert index.yaml v3 with fields |
| filter_by_agent filters correctly | Unit test: mock index, assert only target agent entries |
| search_similar_campaigns uses embeddings | Unit test: mock embeddings, assert cosine similarity |
| search_agent_memory finds text in memory.yaml | Integration: write memory, search, assert match |
| find_similar_campaigns returns scored results | Unit test: assert similarity_score in results |
| query_agent_memory aggregates across agents | Unit test: 8 agents queried, results have agent_name |

---