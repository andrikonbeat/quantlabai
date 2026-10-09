## Exploration: Broker Cost Engine

### Current State

**sdk/quantlab/costs/** está **vacío** — solo tiene `__pycache__/`. No hay ningún módulo de costes implementado.

Sin embargo, hay rastros de una arquitectura de costes a medio construir repartida por el codebase:

1. **sqx/project_builder.py** — Tiene defaults hardcoded para broker JForex/Dukascopy:
   - `_JFOREX_COMMISSION = 3.5` (USD/lot)
   - `_JFOREX_SLIPPAGE = 1` (pip)
   - `_JFOREX_SPREAD = 3` (pips base)
   - `create_project()` acepta `slippage`, `spread`, `commission` como parámetros
   - Línea 951-955: Comentario explícito "Commission handling ($3.5/lot JForex Dukascopy) requires further research into SQX's internal format or plugin-based commission models" — las comisiones están en `type="None"`

2. **guardian/execution.py** — `ExecutionGuardian` espera un `cost_collector` con:
   - `get_recent_slippage()` → devuelve slippage en bps
   - Atributo `.slippage`
   - Este cost_collector NO existe implementado en ninguna parte

3. **guardian/market.py** — `MarketGuardian` espera un `cost_collector` con:
   - `collect_all(major_pairs)` → devuelve datos con `spread_pips`
   - `_score_liquidity()` usa spreads como proxy de liquidez
   - `_score_session()` es placeholder (devuelve 0.8 fijo)

4. **DataManager** — Referenciado en `builder_agent.py` vía `from quantlab.data import DataManager`, pero no existe implementado (import dinámico con try/except).

### Affected Areas

- `sdk/quantlab/costs/` — Directorio objetivo para el nuevo módulo (actualmente vacío)
- `sdk/quantlab/dsl/models.py` — `ResearchConfig` necesita extensión para aceptar config de costes
- `sdk/quantlab/dsl/parser.py` — Parser YAML necesita soportar sección `costs` en ResearchConfig
- `sdk/quantlab/sqx/project_builder.py` — `create_project()` ya acepta slippage/spread/commission, hay que conectar el cost engine
- `sdk/quantlab/translate/translator.py` — `generate_cfx_archive()` necesita inyectar costes en CFX
- `sdk/quantlab/guardian/execution.py` — Necesita `CostCollector` real
- `sdk/quantlab/guardian/market.py` — Necesita `CostCollector` real con spread_pips + session info
- `sdk/quantlab/pipeline/base.py` — `PipelineContext` podría llevar cost config
- `sdk/quantlab/pipeline/config/models.py` — `MultiAgentPipelineConfig` podría tener sección de costs
- `sdk/quantlab/agents/builder_agent.py` — Podría pasar cost config al pipeline
- `sdk/quantlab/phase4/campaign_orchestrator.py` — `CampaignConfig` necesita extender para cost profile
- `sdk/quantlab/phase4/stages/__init__.py` — Posible nuevo stage de cost injection
- `sdk/quantlab/phase4/retester.py` — `RetesterConfig` no incluye costes
- `sdk/quantlab/cfx/models.py` — `BuildTask` podría tener sección de commissions
- `sdk/quantlab/stats/engine.py` — `StatisticsEngine` podría beneficiarse de cost-adjusted metrics

### Approaches

1. **Módulo costs/ separado + integración vía pipeline stage (RECOMENDADO)**:
   - Crear `costs/models.py` con Pydantic models: `CommissionSchema`, `SwapRule`, `SlippageProfile`, `MarketSession`, `BrokerProfile`
   - Crear `costs/engine.py` con `CostEngine` que calcula coste total por trade/símbolo
   - Crear `costs/profiles.py` con perfiles predefinidos (IB, Dukascopy, OANDA, etc.)
   - Crear `costs/collector.py` con `CostCollector` que implementa la interfaz que esperan los guardians
   - Extender `ResearchConfig` con campo `broker_profile` o `costs` section
   - Pipeline stage opcional `CostInjectionStage` que inyecta costes en el CFX antes del dispatch
   - Modificar `project_builder.create_project()` para recibir `BrokerProfile` en lugar de parámetros sueltos
   - **Pros**: Separación limpia, testable, reutilizable por guardians y pipeline
   - **Cons**: Requiere modificar varios puntos de integración
   - **Effort**: High (pero es lo correcto)

2. **Extender project_builder + CFX existente**:
   - Agregar más parámetros a `create_project()` y `BuildConfig`
   - Extender `CfxPatcher` con instrucciones para commissions/spread
   - Perfiles como dicts YAML simples
   - **Pros**: Menos código nuevo, toca menos archivos
   - **Cons**: Sigue siendo frágil (regex en XML), difícil de testear, no hay modelo de datos real, los guardians siguen sin collector
   - **Effort**: Medium

3. **Cost Engine como servicio externo / plugin**:
   - Módulo separado que calcula costes post-backtest
   - No toca CFX, solo ajusta estadísticas después
   - **Pros**: Independiente de SQX, fácil de implementar inicialmente
   - **Cons**: Los costes no afectan la generación de estrategias (solo post-procesamiento), los backtests de SQX no reflejan costes reales
   - **Effort**: Low (pero incorrecto arquitectónicamente)

4. **Extender solo el DSL/ResearchConfig + injectar en CFX vía translator**:
   - Models de costes en `dsl/models.py`
   - Inyección directa en `translator.py` → `CfxArchive`
   - Sin módulo separado, sin pipeline stage
   - **Pros**: Menos archivos nuevos, integración directa con el pipeline existente
   - **Cons**: Mezcla dominios (DSL + costes), difícil de mantener, los guardians siguen rotos
   - **Effort**: Medium

### Recommendation

**Approach 1: Módulo costs/ separado con integración pipeline + guardians.**

Es el que mejor se alinea con la arquitectura existente del proyecto:
- Sigue el patrón de `guardian/` (models.py → engine → integration)
- Sigue el patrón de `stats/` (models.py → engine.py → pipeline stage)
- Resuelve los `cost_collector` pendientes en guardian/execution.py y guardian/market.py
- Permite configuración vía YAML (ResearchConfig) Y vía API (Python SDK)
- La inyección en CFX vía el translator o project_builder es técnicamente compleja (SQX XML), pero necesaria para backtests realistas

Estructura propuesta:

```
sdk/quantlab/costs/
├── __init__.py
├── models.py          # CommissionSchema, SwapRule, SlippageProfile, MarketSession, BrokerProfile
├── engine.py          # CostEngine — cálculo de coste total por trade/symbol
├── profiles.py        # BrokerProfile presets (IB, Dukascopy, OANDA, etc.)
├── collector.py       # CostCollector — interfaz concreta para guardians
└── sessions.py        # MarketSession calendar / horarios de mercado
```

### Risks

1. **Complejidad técnica de CFX**: SQX usa un formato XML interno para commissions que no está bien documentado. El código actual en `project_builder.py` línea 951-955 admite que "Commission handling requires further research". Podría requerir parchar el template .sqx o usar un plugin.
2. **Integración con guardians**: Los guardians esperan una interfaz `cost_collector` que no está formalmente definida. Habrá que definir un protocol/ABC e implementarlo.
3. **Datos de mercado reales**: El slippage variable necesita datos de volatilidad/liquidez que pueden no estar disponibles sin conexión a data feed.
4. **Testing**: 531 tests existentes — hay que asegurar que los cambios no rompan el pipeline actual. Los nuevos modelos y engine deben tener cobertura completa.
5. **Timing de inyección**: Si los costes se inyectan en el CFX ANTES del backtest de SQX, es más realista pero más complejo. Si se aplican DESPUÉS (post-procesamiento), es más simple pero menos preciso.

### Dependencies & Prerequisites

- La interfaz `DataManager` referenciada en `builder_agent.py` debería existir para que el cost engine pueda consultar market data (volatilidad, spreads históricos)
- Se necesita entender el formato exacto de commissions en CFX XML (posible research con SQX)
- Los perfiles de broker necesitan datos reales de comisiones (IB, Dukascopy, OANDA)

### Ready for Proposal

**Yes** — pero con la advertencia de que la fase de diseño deberá investigar el formato CFX para commissions antes de definir la implementación concreta de inyección. Se recomienda proceder con sdd-propose usando el Approach 1 como base, y en sdd-design investigar la viabilidad técnica de la inyección CFX.
