# Pipeline Core — Hypothesis Builder Delta

## Added Requirements

### Requirement: Hypothesis Builder Stage

The system MUST support an optional ``hypothesis_builder`` stage inserted between
the research stage (classic or LLM) and the builder stage.

The stage MUST be registered in ``StageRegistry`` as ``"hypothesis_builder"``.

#### Scenario: Stage registered

- GIVEN the StageRegistry is initialised
- WHEN a lookup for ``"hypothesis_builder"`` is performed
- THEN a stage class is returned with ``name="hypothesis_builder"``

#### Scenario: Stage inserted between research and builder

- GIVEN a pipeline with research and builder stages
- WHEN ``hypothesis_builder`` is configured
- THEN the pipeline order is research → hypothesis_builder → builder

#### Scenario: Stage contract

- GIVEN a ``HypothesisBuilderStage`` instance
- THEN ``requires`` includes ``["research_config", "hypotheses", "objectives"]``
- AND ``provides`` includes ``["building_blocks", "strategies"]``
