# Refutation Layer — Tasks

## PR 1: Core + Regime Strategy

- [x] 1.1 Crear `agents/refutation/config.py` — `RefutationConfig` Pydantic model
- [x] 1.2 Crear `agents/refutation/__init__.py` — `FalsationVerdict`, `RefutationResult` dataclasses + `RefutationLayer` facade
- [x] 1.3 Crear `agents/refutation/strategies/__init__.py` — `RefutationStrategy` ABC
- [x] 1.4 Crear `agents/refutation/strategies/regime.py` — `RegimeMismatchStrategy`
- [x] 1.5 Tests: models, regime strategy, facade dispatch

## PR 2: Historical + LLM Strategies

- [x] 2.1 Crear `agents/refutation/strategies/historical.py` — `HistoricalCounterExampleStrategy` con YahooFinanceProvider
- [x] 2.2 Crear `agents/refutation/strategies/adversarial.py` — `LLMAdversarialStrategy` con temperature=0.2
- [x] 2.3 Score aggregation max() en facade
- [x] 2.4 Tests: historical con mock YahooFinance, LLM adversarial mock

## PR 3: Stage + Pipeline Wiring

- [x] 3.1 Crear `RefutationStage` ABC en `pipeline/stages/agent_stages.py`
- [x] 3.2 Registrar `"refutation"` en `StageRegistry`
- [x] 3.3 Insertar entre `hypothesis_builder` y `builder` en `research_director.py`
- [x] 3.4 Tests: registry, stage contract, pipeline insertion
