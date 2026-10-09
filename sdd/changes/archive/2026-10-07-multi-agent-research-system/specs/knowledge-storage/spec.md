# Delta for Knowledge Storage

## MODIFIED Requirements

### Requirement: Directory Initialization

The system MUST create the 5-directory Knowledge Lake skeleton PLUS an agent-memory directory: `raw/`, `structured/`, `graph/`, `embeddings/`, `datasets/`, `agent-memory/`. The `agent-memory/` directory SHALL contain per-agent subdirectories. Each directory SHALL contain a `.gitkeep` or metadata file.
(Previously: 5 directories only)

#### Scenario: Fresh initialization creates agent-memory directory
- GIVEN a `knowledge/` path that does not exist
- WHEN the system initializes the Knowledge Lake
- THEN 6 subdirectories are created each with a `.gitkeep` marker file
- AND `agent-memory/` contains subdirectories: `research-director/`, `research-agent/`, `builder-agent/`, `statistics-agent/`, `reviewer-agent/`, `portfolio-agent/`, `deployment-agent/`, `monitoring-agent/`

#### Scenario: Re-initialization on existing structure is idempotent
- GIVEN an already-initialized Knowledge Lake with files present
- WHEN the system initializes again
- THEN no existing files are modified or deleted, and no error is raised
- AND agent-memory subdirectories preserved

### Requirement: Path Resolution

The system MUST resolve Knowledge Lake paths including agent-memory paths relative to a configurable root, with cross-platform separator handling.
(Previously: Only 5 base directories)

#### Scenario: Agent memory paths resolved
- GIVEN a Knowledge Lake at `/home/user/knowledge` on Linux
- WHEN the system resolves `agent-memory/research-agent/campaign-123/memory.yaml`
- THEN the resolved path is `/home/user/knowledge/agent-memory/research-agent/campaign-123/memory.yaml`

## ADDED Requirements

### Requirement: Agent Memory Directory Structure

The system MUST provide `agent-memory/{agent_name}/{campaign_id}/` structure for each agent to store: `memory.yaml` (decisions, hypotheses, learned patterns), `checkpoints/` (periodic state snapshots), `audit.log` (decision trail).

#### Scenario: Agent writes memory artifact
- GIVEN ResearchAgent with campaign_id="campaign-123"
- WHEN ResearchAgent stores hypothesis decision
- THEN file written to `knowledge/agent-memory/research-agent/campaign-123/memory.yaml`
- AND memory.yaml contains: hypotheses, confidence_scores, query_patterns, timestamp

#### Scenario: Campaign embedding stored
- GIVEN completed campaign with statistics and portfolio result
- WHEN KnowledgeStorage.store_campaign_embedding() called
- THEN embedding vector saved to `knowledge/embeddings/{campaign_id}.parquet`
- AND metadata in `knowledge/structured/{campaign_id}/embedding_metadata.yaml`

### Requirement: Campaign Embedding Persistence

The system MUST store campaign-level embeddings (vector representations of campaign characteristics: market, strategy type, metrics, regime) for similarity search.

#### Scenario: Embedding generated and stored
- GIVEN campaign with market=EURUSD, strategy=mean_reversion, sharpe=1.6, regime=trending
- WHEN KnowledgeStorage.compute_and_store_embedding() called
- THEN 384-dim embedding vector generated (sentence-transformers or compatible)
- AND stored in embeddings/ with metadata linking to campaign_id

---

## REMOVED Requirements

None.

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| 6 directories created on init | Unit test: assert all 6 dirs exist with .gitkeep |
| Agent memory subdirectories created | Unit test: assert 8 agent subdirs under agent-memory/ |
| Agent memory path resolution works | Unit test: Linux and Windows path resolution |
| Memory artifact written to correct path | Integration: agent stores → assert file content |
| Campaign embedding stored in embeddings/ | Unit test: assert .parquet and metadata.yaml exist |
| Embedding dimension correct | Unit test: assert vector shape (384,) |

---