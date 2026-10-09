# Delta for pipeline-core

## ADDED Requirements

### Requirement: Stage Registry — research_llm

The system MUST register `"research_llm"` as a valid stage type in `StageRegistry`, mapping to `LLMResearchStage`.

#### Scenario: research_llm is registered

- GIVEN StageRegistry
- WHEN looking up "research_llm"
- THEN the registry returns LLMResearchStage class
- AND the stage is available for pipeline composition

#### Scenario: Unknown stage gracefully handled

- GIVEN a stage name that is not registered
- WHEN StageRegistry.lookup() is called
- THEN RegistryError is raised
- AND the existing classic stages remain unaffected

### Requirement: ResearchDirector Routing

`ResearchDirector` MUST route between `"research"` and `"research_llm"` stages based on `AgentConfig.model`. If `model != ""`, the director SHALL use `LLMResearchAgent`; if `model == ""`, it SHALL use the classic `ResearchAgent`.

#### Scenario: LLM configured routes to LLM agent

- GIVEN AgentConfig.model = "gpt-4"
- WHEN ResearchDirector resolves the research stage
- THEN "research_llm" stage is selected
- AND the pipeline uses LLMResearchAgent

#### Scenario: Empty model routes to classic

- GIVEN AgentConfig.model = ""
- WHEN ResearchDirector resolves the research stage
- THEN "research" stage is selected
- AND the pipeline uses classic ResearchAgent

#### Scenario: LLM fallback on failure

- GIVEN LLMResearchAgent fails with timeout
- WHEN ResearchDirector receives the failure
- THEN the director falls back to classic ResearchAgent
- AND the pipeline completes without LLM
