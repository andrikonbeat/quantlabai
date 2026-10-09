# Campaign Artifact Writers Specification

## Purpose

SDK-owned, deterministic writers that persist per-campaign user-facing artifacts — `proposal.md`, `spec.md`, and per-phase envelopes — so the campaign flow leaves durable records that survive agent failure. Phase agents keep the REQ-820 "artifacts not bytes" boundary; the SDK writes files.

## Requirements

### Requirement: Proposal Artifact Writer

The system MUST persist `knowledge/structured/{campaign_id}/proposal.md` from the in-memory research output (research_config, hypotheses, sources, evidence) when a campaign reaches the research stage. The writer SHALL be SDK-owned and MUST NOT depend on LLM-generated text.

#### Scenario: Research stage persists proposal

- GIVEN a campaign "camp_001" whose research stage produced hypotheses
- WHEN the stage completes
- THEN `knowledge/structured/camp_001/proposal.md` exists on disk
- AND it contains the research_config and hypothesis entries

#### Scenario: Missing knowledge_root degrades

- GIVEN a stage payload without `knowledge_root`
- WHEN the writer attempts to persist
- THEN the phase records the gap in `risks` and completes without crashing
- AND no envelope claims the proposal artifact

### Requirement: Spec Artifact Writer

The system MUST persist `knowledge/structured/{campaign_id}/spec.md` — the technical contract — covering builder/retester/optimizer/portfolio configuration and acceptance criteria. It SHALL be regenerable and testable.

#### Scenario: Spec written with empty hypotheses

- GIVEN a campaign with zero hypotheses
- WHEN the spec writer runs
- THEN `spec.md` is written with the configuration sections
- AND the hypotheses section is empty

### Requirement: Envelope Writer Wiring

`_run_sdk_stage` (campaign/delegation.py) MUST call `save_phase_envelope` (knowledge/store.py:638) for every completed stage, persisting each claimed artifact key (`{phase}_{stage}.json`) as a real file.

#### Scenario: Claimed artifact becomes a file

- GIVEN a completed research stage claiming artifact "research_research_llm.json"
- WHEN the stage result is returned
- THEN `campaign-phases/{campaign_id}/research/envelope.json` exists
- AND its artifacts list resolves to files on disk

#### Scenario: Write failure is recorded

- GIVEN an unwritable Knowledge Lake path
- WHEN the envelope write fails
- THEN the envelope carries failed status with the error listed
- AND folding halts per REQ-802