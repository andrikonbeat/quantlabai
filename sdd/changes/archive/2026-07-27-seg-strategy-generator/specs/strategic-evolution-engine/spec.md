# Delta for strategic-evolution-engine

## MODIFIED Requirements

### Requirement: GeneticOptimizer produces real candidates

The GeneticOptimizer MUST produce EvolutionCandidate objects with real CFX content, not empty lists.
(Previously: returned `[]` regardless of input)

#### Scenario: Optimize mutates CFX parameters
- GIVEN a valid CFX strategy string
- WHEN `GeneticOptimizer.optimize(strategy_id, cfx_content)` is called
- THEN a list of EvolutionCandidate objects is returned with modified CFX content
- AND each candidate has a unique candidate_id with parent_trace

#### Scenario: Optimize returns empty for invalid CFX
- GIVEN an invalid or empty CFX string
- WHEN `GeneticOptimizer.optimize()` is called
- THEN an empty list is returned
- AND no candidates are added to the pool

### Requirement: NoveltyGenerator produces real candidates

The NoveltyGenerator MUST produce EvolutionCandidate objects with DSL-generated strategies, not empty lists.
(Previously: returned `[]` regardless of context)

#### Scenario: Generate creates new strategies from context
- GIVEN a context dict with market, timeframe, and risk profile
- WHEN `NoveltyGenerator.generate(context)` is called
- THEN a list of EvolutionCandidate objects is returned
- AND each candidate has DSL content describing its strategy

#### Scenario: Generate returns empty for empty context
- GIVEN an empty context dict
- WHEN `NoveltyGenerator.generate({})` is called
- THEN an empty list is returned

### Requirement: CandidateValidator runs real pipeline validation

The CandidateValidator MUST run backtest → walk-forward → Monte Carlo via PipelineRunner.
(Previously: returned the candidate unchanged)

#### Scenario: Validate passes a good candidate
- GIVEN a candidate with valid CFX content
- WHEN `CandidateValidator.validate(candidate)` is called
- THEN the candidate's status is updated to PASSED
- AND validation_results contain backtest, walk_forward, and monte_carlo results

#### Scenario: Validate fails a weak candidate
- GIVEN a candidate with poor strategy CFX
- WHEN `CandidateValidator.validate(candidate)` is called
- THEN the candidate's status is updated to FAILED
- AND validation_results contain the failure reason
