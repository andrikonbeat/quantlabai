# Delta for mcp-bridge

## ADDED Requirements

### Requirement: generate_strategy MCP tool

The system MUST provide a `generate_strategy` MCP tool that delegates to the StrategyGenerator facade.

#### Scenario: Generate strategy returns ranked candidates
- GIVEN intent parameters (market, timeframe, risk, objective)
- WHEN the `generate_strategy` tool is called
- THEN a JSON array of ranked EvolutionCandidate results is returned
- AND each result includes a fitness_score and validation_status

#### Scenario: Generate strategy with invalid params
- GIVEN empty or invalid intent parameters
- WHEN the `generate_strategy` tool is called
- THEN a structured error is returned
- AND no candidates are generated
