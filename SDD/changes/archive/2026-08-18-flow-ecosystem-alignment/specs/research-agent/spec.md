# Delta for research-agent

## ADDED Requirements

### Requirement: Research Stage Canon (G5)

The research stage names in the canonical pipeline MUST be `research` (classic) and `research_llm` (LLM-routed), positioned as the first agent stage of `build_pipeline`. The retired "8 agents + 5 gates" wording MUST be superseded by the canonical counts in full-campaign-lifecycle.

#### Scenario: Research is the first agent stage

- GIVEN the orchestrated pipeline
- WHEN the stage list is inspected
- THEN the first agent entry is `research` or `research_llm`
- AND no doc claims a fixed 8-agent set