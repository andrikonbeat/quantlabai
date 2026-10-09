# Knowledge Memory Specification

## Purpose

Durable, Git-versioned campaign memory: capture decisions at phase boundaries, complement Engram (session memory) with a training-ready lake, inject retrieved context into later phases, self-correct, and export privacy-scrubbed training data.

## Requirements

### Requirement: REQ-101 Capture Taxonomy

The system MUST persist each data type to one canonical Knowledge Lake location:

| Data type | Where | When | Why / For what |
|---|---|---|---|
| Decisions, Result envelopes | `agent-memory/{agent}/{campaign}/memory.yaml` + Engram | phase boundary | durability; retrieval, teaching |
| Pipeline runs | `pipeline-runs/` | per execution | audit; debugging |
| Configs | `structured/{campaign_id}/` | on save | reuse; KB verification |
| Raw SQX exports | `raw/` | after export | provenance; re-derivation |
| Metrics, tags, links | `structured/{campaign_id}/` + index | post-campaign | search; query |
| Embeddings | `embeddings/` | post-campaign | similarity; retrieval |
| Training data | `datasets/` | on export | LLM training; fine-tuning |
| KB params | `structured/sqx-kb/{ver}/parameters/` | seed/verify | evidence; builder config |
| Version events | `structured/sqx-version/{old}→{new}/` | on drift | migration; checklist |

#### Scenario: Taxonomy conformance

- GIVEN a campaign completing a phase
- WHEN artifacts are persisted
- THEN each artifact lands in its canonical directory and nowhere else

#### Scenario: Unknown data type refused

- GIVEN a save attempt for an unmapped data type
- WHEN the store validates the destination
- THEN the save is refused with an error listing valid destinations

### Requirement: REQ-102 Automatic save_decision at Phase Boundaries

The system MUST invoke `AgentMemoryManager.save_decision` at every phase boundary in `campaign/flow.py` (all 14 phases), capturing the Result Contract envelope (`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`) plus the phase config. MVP capture SHALL include decisions, Result envelopes, and configs; backtest artifacts are deferred.

#### Scenario: Capture at phase boundary

- GIVEN a completed phase with a valid Result Contract
- WHEN the phase transitions to the next
- THEN a decision record is written to `agent-memory/{agent}/{campaign}/memory.yaml`
- AND the same record is persisted to Engram under topic `agent/{agent}/{campaign}`

#### Scenario: Missing envelope fields default

- GIVEN a phase result missing `next_recommended`
- WHEN save_decision runs
- THEN missing fields default to null and the record is still persisted

#### Scenario: Save failure is non-blocking

- GIVEN a Knowledge Lake write failure
- WHEN save_decision attempts persistence
- THEN a warning is logged and the phase flow continues

### Requirement: REQ-103 Engram Complementarity Boundary

The system MUST treat Engram as session/working memory, the Knowledge Lake as durable Git-versioned training-ready memory, and OpenSpec as requirements. save_decision MUST write to both; neither replaces the other.

#### Scenario: Dual write

- GIVEN a captured decision
- WHEN persisted
- THEN it appears in Engram (topic `agent/{agent}/{campaign}`) and in `agent-memory/` YAML

#### Scenario: Engram unavailable

- GIVEN an Engram write failure
- WHEN save_decision runs
- THEN the lake write still succeeds and a warning is logged

### Requirement: REQ-104 Injected-Context Retrieval

The system MUST compose prior-campaign context — QueryBuilder results plus `find_similar_campaigns` embeddings — into a markdown block injected into the next phase's Result Contract envelope, so orchestrator/ResearchDirector receive it in-prompt.

#### Scenario: Prior memory injected

- GIVEN a phase N+1 and prior campaigns in the lake
- WHEN the phase context is composed
- THEN the envelope includes matched prior decisions, risks, and lessons
- AND similar campaigns are ranked by embedding similarity

#### Scenario: Empty lake placeholder

- GIVEN an empty Knowledge Lake
- WHEN context is composed
- THEN a "no prior memory" placeholder is injected and no error is raised

### Requirement: REQ-105 Self-Correction Loop (Later — MVP partial)

The system SHOULD compare phase outcomes against prior decisions to detect repeated failure signatures and recommend corrective actions. MVP SHALL implement detection-and-report only; the full loop is deferred.

#### Scenario: Repeated failure flagged

- GIVEN two prior phases sharing a failure signature
- WHEN a third phase produces the same signature
- THEN a self-correction recommendation is appended to the envelope

### Requirement: REQ-106 Training Dataset Pipeline (Later)

The system MUST export curated JSONL training data to `datasets/`, kept local. Curation SHALL restrict to archived, verified campaigns; dedupe by config hash; and privacy-scrub per REQ-107.

#### Scenario: Curated export

- GIVEN verified archived campaigns
- WHEN the export runs
- THEN JSONL holds one decision per line, deduplicated by config hash, deny-list-clean

### Requirement: REQ-107 Privacy Deny-List

The system MUST apply a privacy deny-list (license codes, API keys, `.env` contents, credentials, personal data) on every lake write and export. Campaign IDs in training exports MUST be hashed. A conformance test MUST assert exports are deny-list-clean.

#### Scenario: Secret redacted at write

- GIVEN a decision containing license code `FUTLABF255`
- WHEN it is persisted
- THEN the secret is redacted from the lake record and the Engram record

#### Scenario: Hashed campaign IDs in exports

- GIVEN a training export containing `campaign_id: campaign-7`
- WHEN the export is written
- THEN the ID appears as its SHA-256 hash, not the raw ID

#### Scenario: Privacy conformance test

- GIVEN a staged training export
- WHEN the conformance test runs
- THEN it fails if any deny-listed pattern or raw campaign ID is present
