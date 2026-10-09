# Refutation Layer — Design

## Architecture

```
HypothesisBuilder → RefutationLayer → builder
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
     RegimeMismatch  Historical   LLM Adversarial
     Strategy      Counter-       Strategy
                    Example
                    Strategy
            │           │           │
            └───────────┼───────────┘
                        ▼
              Score Aggregation (max)
                        ▼
              RefutationResult
              (annotations, no filtering)
```

## Module Structure

```
agents/refutation/
├── __init__.py          # RefutationLayer facade + RefutationResult
├── strategies/
│   ├── __init__.py       # Strategy ABC
│   ├── regime.py         # RegimeMismatchStrategy
│   ├── historical.py     # HistoricalCounterExampleStrategy
│   └── adversarial.py    # LLMAdversarialStrategy
└── config.py            # RefutationConfig (moved from DSL for cohesion)
```

## Key Decisions

1. **Strategy pattern**: Mismo approach que HypothesisBuilder. Cada estrategia
   implementa `async refute(hyp, context) -> FalsationVerdict`.

2. **Score = max()**: Visión conservadora. Si UNA estrategia encuentra un problema,
   la hypothesis se considera falsada a ese nivel. El builder puede inspeccionar
   los detalles y decidir.

3. **No filtrado**: La capa solo anota. El ResearchDirector o el builder pueden
   usar `falsation_results` para decisiones, pero la RefutationLayer no bloquea.

4. **Reuso de providers existentes**: Historical usa YahooFinanceProvider.
   LLM adversarial usa el mismo call_llm() que LLMResearchAgent.

## PR Breakdown

### PR 1: Core + Regime Strategy
- RefutationConfig model
- FalsationVerdict + RefutationResult dataclasses
- Strategy ABC
- RegimeMismatchStrategy (reusa StatisticsAgent.detect_regime_change)
- RefutationLayer facade
- Tests

### PR 2: Historical + LLM Strategies
- HistoricalCounterExampleStrategy (YahooFinanceProvider)
- LLMAdversarialStrategy (call_llm con temperature=0.2)
- Tests mockeando providers

### PR 3: Stage + Pipeline Wiring
- RefutationStage ABC
- StageRegistry registration
- Pipeline insertion between hypothesis_builder and builder
- Integration tests
