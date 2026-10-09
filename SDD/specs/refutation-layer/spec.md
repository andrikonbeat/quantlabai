# Refutation Layer Spec

## Overview

Proactive falsation system that annotates hypotheses with falsification scores
and evidence before they reach the BuilderAgent, without blocking execution.

## Requirements

### RF-1 — FalsationContract

The ``RefutationLayer`` SHALL accept ``list[HypothesisConfig]`` + optional
``list[BuildingBlock]`` + optional ``market_context`` and SHALL return a
``RefutationResult`` with per-hypothesis verdicts.

```python
@dataclass
class FalsationVerdict:
    hypothesis_name: str
    falsification_score: float       # 0.0 (not refuted) – 1.0 (fully refuted)
    evidence: list[str]              # why this score
    strategy: str                    # which strategy produced this

@dataclass
class RefutationResult:
    verdicts: list[FalsationVerdict]
    summary: dict[str, Any]          # aggregated stats
```

### RF-2 — Regime Mismatch Strategy

The layer SHALL reutilise ``StatisticsAgent.detect_regime_change()`` to compare
the hypothesis's assumed market regime against the current/forecast regime.

If the assumed regime (derived from hypothesis description + data_sources) does
not match the detected regime, ``falsification_score`` SHALL increase by up to
0.6 points.

### RF-3 — Historical Counter-Example Strategy

The layer SHALL use ``YahooFinanceProvider.fetch()`` to retrieve historical
OHLCV + fundamental data for relevant symbols and search for periods where the
hypothesis's expected conditions existed but the expected outcome failed.

If a counter-example is found, ``falsification_score`` SHALL increase by up to
0.8 points.

### RF-4 — LLM Adversarial Strategy

The layer SHALL use the same ``LLMConfig`` (with temperature=0.2) to prompt the
LLM to actively refute the hypothesis using the ``llm_rationale``,
``source_urls``, and ``data_sources``.

The LLM SHALL return a JSON with ``score`` (0-1) and ``evidence`` (list of
counter-arguments). If the LLM is unavailable, this strategy SHALL be skipped
without affecting other strategies.

### RF-5 — Score Aggregation

The final ``falsification_score`` for a hypothesis SHALL be the MAX of all
enabled strategy scores (conservative: if ANY strategy finds a problem, the
hypothesis is considered falsified at that level).

### RF-6 — Non-blocking

The RefutationLayer SHALL NOT filter or remove hypotheses. It SHALL only annotate
via ``PipelineContext.artifacts["falsation_results"]``.

### RF-7 — RefutationStage Contract

The ``RefutationStage`` SHALL be a Stage ABC with:
- ``name = "refutation"``
- ``requires = ["research_config", "hypotheses", "building_blocks", "strategies"]``
- ``provides`` preserves existing artifacts + adds ``["falsation_results"]``

### RF-8 — Stage Registration

The stage SHALL be registered in ``StageRegistry`` as ``"refutation"`` and SHALL
be inserted between ``hypothesis_builder`` and ``builder`` in the pipeline.

### RF-9 — Disablable

When ``RefutationConfig.enabled = False``, the RefutationLayer SHALL produce an
empty ``RefutationResult`` with no strategy execution and no performance impact.

## Scenarios

### S-1: Regime mismatch detected
Given hypothesis assumes "trend-following momentum" and StatisticsAgent detects
"range-bound" regime
When regime_mismatch strategy runs
Then falsification_score >= 0.3

### S-2: Historical counter-example found
Given hypothesis "buy when RSI < 30" with symbol "EURUSD"
When historical_counterexample searches 10y of data
Then if RSI < 30 preceded further declines in >40% of cases, score increases

### S-3: LLM adversarial refutes
Given hypothesis with rationale "CPI rising benefits USD"
When LLM adversarial strategy runs with temperature=0.2
Then the LLM returns score + evidence citing counter-arguments

### S-4: All strategies pass = low score
Given a robust hypothesis with supporting data across all checks
When all strategies run
Then falsification_score < 0.3

### S-5: Disabled = no-op
Given RefutationConfig.enabled = False and 5 hypotheses
When refute() is called
Then all verdicts have score = 0.0 and evidence = []

### S-6: Stage contract
Given RefutationStage is looked up in StageRegistry
Then name = "refutation", requires include hypotheses + building_blocks

### S-7: Pipeline insertion
Given a pipeline with hypothesis_builder and builder stages
When pipeline is built
Then refutation stage appears between them
