# Refutation Layer — Proposal

## Problem Statement

El pipeline genera hypotheses desde datos de mercado (LLM Research Agent) y las
convierte en building blocks concretos (Hypothesis Builder). Pero no hay ningún
mecanismo que **proactivamente intente refutar** esas hypotheses antes de invertir
recursos computacionales en traducirlas a CFX y ejecutarlas en SQX.

El ReviewerAgent existente hace revisión post-execución (detecta overfitting en
walk-forward/MC), pero es reactivo — ya se quemaron recursos de simulación.

## Scope

### In scope (6 deliverables)

1. **RefutationLayer** — componente que toma hypotheses + building blocks +
   market_context y produce anotaciones de falsación para cada hypothesis:
   - `falsification_score: float` (0 = no refutada, 1 = completamente refutada)
   - `falsification_evidence: list[str]` (explicación de por qué se refutó)
   - `falsification_details: dict` (métrica por estrategia)

2. **Estrategia: Regime Mismatch** — Reutiliza `detect_regime_change()` de
   StatisticsAgent. Si una hypothesis asume trending pero el régimen actual es
   range-bound o volátil, sube el score de falsación.

3. **Estrategia: Historical Counter-example** — Usa YahooFinanceProvider para
   buscar períodos históricos donde la hypothesis habría fallado (ej: si la
   hypothesis es "buy on RSI < 30", buscar períodos donde RSI < 30 y el precio
   siguió cayendo).

4. **Estrategia: LLM Adversarial** — Usa el mismo LLMConfig pero con temperatura
   baja (0.2) para que el LLM intente activamente refutar la hypothesis con
   datos contrarios de `source_urls` y `data_sources`.

5. **RefutationStage** — Nuevo stage pipeline insertado entre `hypothesis_builder`
   y `builder`. No bloquea hypotheses, solo las anota.

6. **RefutationConfig** — Config opcional en el DSL:
   ```python
   class RefutationConfig(BaseModel):
       enabled: bool = True
       strategies: list[str] = ["regime_mismatch", "historical_counterexample", "llm_adversarial"]
       threshold: float = 0.5
       llm_config: Optional[LLMConfig] = None
   ```

### Out of scope
- No modificar ReviewerAgent
- No ejecutar backtests reales para falsar
- No persistencia separada (va en PipelineContext)
- No filtrado binario de hypotheses (solo anotación continua)
- No UI para visualizar falsaciones

## Approach

La RefutationLayer sigue el mismo patrón que HypothesisBuilder:
- Facade con Strategy pattern: `refute(hypotheses, building_blocks, market_context)`
- Cada estrategia produce un `FalsationVerdict(score, evidence, strategy_name)`
- El score final es el máximo de todas las estrategias (visión conservadora)
- Stage wrapper que llama `refute()` y escribe en PipelineContext

## Success Criteria

1. RefutationLayer anota hypotheses con falsation_score y evidence sin modificar
   las hypotheses originales
2. Cada estrategia produce resultados deterministas para los mismos inputs
3. Stage se registra y ejecuta sin romper el pipeline existente
4. Tests mockean Yahoo Finance / LLM calls — no requieren API real
5. Pipeline existente funciona igual con refutation deshabilitada

## Risks

| Riesgo | Mitigación |
|--------|------------|
| LLM adversarial puede ser caro | Mismo rate limiting + caching que LLMResearchAgent |
| Regime mismatch muy simplista | Reutilizar lógica existente de StatisticsAgent |
| Historical counter-example lento | Cachear resultados por período + símbolo |
| Falsaciones falsas positivas | Score continuo, no bloqueante — el builder decide |
