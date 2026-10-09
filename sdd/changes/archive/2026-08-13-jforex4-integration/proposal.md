# JForex4 Integration Proposal

## Intent

Integrar JForex4 como plataforma de ejecución y visualización oficial de las estrategias generadas por QuantLab/SQX, cerrando el loop investigación → backtest → deploy → live → análisis LLM.

## Contexto

- SQX ya genera estrategias compilables a `.jfx`
- JForex4 es el platform desktop de Dukascopy para ejecutar esas estrategias
- QuantLab hoy carece de: broker adapter real, live feed desde JForex, deploy automático de `.jfx`, y acceso a indicadores para LLM
- JForex4 no expone API REST/WS pública; la integración debe usar el SDK/desktop + lectura de estado local

## Scope

### Incluido
- `JForexBrokerAdapter` para `ExecutionGuardian`
- `JForexLiveFeed` + `JForexStrategyBridge` para `LiveEvaluation`
- `DataManager` extensible (sqcli deja de ser único)
- Export de indicadores desde `.jfx` hacia LLM
- Pipeline stage de deploy post-SQX

### Excluido
- Modo live con captcha/PIN automático
- Dashboard web propio de trading
- Multi-broker/multi-cuenta

## Enforzamiento

- Demo automation total desde día 1
- Live queda como “connect once” manual; QuantLab maneja el resto mientras la sesión viva
- No se implementa proxy REST sobre JForex4

## Entregable

5 ciclos SDD ejecutables en modo automático, cada uno con tests y commit propio.
