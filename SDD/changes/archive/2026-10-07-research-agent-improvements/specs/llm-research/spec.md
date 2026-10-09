# Delta for LLM Research

## ADDED Requirements

### Requirement: SQXDocProvider in Prompts

LLMResearchAgent MUST inject SQXDocProvider descriptions into LLM prompts when building parameter suggestions. Descriptions SHALL be appended as a "SQX Reference" section.

#### Scenario: Prompt includes parameter docs

- GIVEN LLMResearchAgent builds a prompt for RSI configuration
- WHEN SQXDocProvider.get_description("RSI") returns text
- THEN the prompt includes the description under "SQX Reference"
- AND the LLM uses it for grounded suggestions

### Requirement: ParameterValidator in Output Validation

LLMResearchAgent MUST validate parsed LLM responses against SQXDocProvider before returning ResearchConfig. Invalid parameters SHALL cause the hypothesis to be dropped with a logged warning.

#### Scenario: Invalid LLM output rejected

- GIVEN LLM returns RSI period=500
- WHEN ParameterValidator.validate_hypothesis() runs
- THEN the hypothesis is dropped
- AND ResearchConfig contains only valid hypotheses
