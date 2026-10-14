# Spec: ParamMapper — ExplorationDecision → Task Parameters

## Overview

The ParamMapper is the deterministic mapping layer that transforms the 13-field ExplorationDecision artifact into per-task parameter dictionaries for the SQX CustomProject pipeline.

## Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| PM-01 | Map all 13 ExplorationDecision fields to relevant task parameters | Must |
| PM-02 | Support all 14 SQX task types (Build, Filtering, Retest, etc.) | Must |
| PM-03 | Apply 37 mapping rules in deterministic order | Must |
| PM-04 | Provide transform functions for derived values | Must |
| PM-05 | Coerce output to task schema (types, ranges, enums) | Must |
| PM-06 | Be deterministic: same input → identical output | Must |

### Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| PM-NF-01 | Deterministic: same input → bit-identical output |
| PM-NF-02 | Extensible: custom rules injectable |
| PM-NF-03 | Testable: pure functions, no side effects |
| PM-NF-04 | Performant: < 10ms per mapping |

---

## Interface

```python
class ParamMapper:
    def __init__(
        self,
        template_name: str = "standard_research",
        custom_rules: list[tuple] | None = None,
    ) -> None:
        ...

    def map(
        self,
        exploration: ExplorationDecision,
        template_tasks: list[CustomProjectTask],
    ) -> dict[str, dict[str, Any]]:
        """
        Map ExplorationDecision to per-task parameter dicts.

        Args:
            exploration: The 13-field ExplorationDecision artifact
            template_tasks: List of CustomProjectTask from selected template

        Returns:
            Dict mapping task_name -> {param_name: value}
        """
```

---

## Mapping Rules (37 Rules)

| # | Source Field | Target Tasks | Target Param | Transform | Condition |
|-----|-------------|--------------|--------------|-----------|-----------|
| 1 | capital_usd | Build, Optimize, Retest, AutoRetest | risk_per_trade_usd | capital_to_risk_usd | - |
| 2 | capital_usd | Build, Optimize, Retest, AutoRetest | max_lot_size | capital_to_max_lot | - |
| 3 | leverage | Build, Optimize | leverage | - | - |
| 4 | market | Build, Filtering, Retest, Optimize, AutoRetest | symbol | market_to_symbol | - |
| 5 | instruments | Build, Optimize, Retest, AutoRetest | instruments | - | - |
| 6 | timeframe | Build, Retest, Optimize, AutoRetest | timeframe | - | - |
| 7 | timeframe | Retest, Optimize, AutoRetest | walkforward_cycles | timeframe_to_wf_cycles | - |
| 8 | capital_limits.max_drawdown_pct | Build, Optimize, Retest | max_drawdown_pct | - | - |
| 9 | capital_limits.risk_per_trade_pct | Build, Optimize, Retest | risk_per_trade_pct | - | - |
| 10 | capital_limits.max_concurrent_positions | Build, Optimize | max_concurrent_positions | - | - |
| 11 | capital_limits.min_lot_size | Build, Optimize | min_lot_size | - | - |
| 12 | capital_limits.max_lot_size | Build, Optimize | max_lot_size | - | - |
| 13 | capital_limits.instruments | Build, Optimize, Retest | instruments | - | - |
| 13 | capital_limits.timeframe | Build, Retest, Optimize | timeframe | - | - |
| 14 | operational_restrictions.trading_hours_utc | Build | trading_hours_utc | - | - |
| 15 | operational_restrictions.forbidden_days | Build | forbidden_days | - | - |
| 15 | operational_restrictions.max_daily_trades | Build | max_daily_trades | - | - |
| 16 | operational_restrictions.news_filter | Build, Filtering | news_filter | - | - |
| 16 | operational_restrictions.max_spread_pips | Build, Filtering | max_spread_pips | - | - |
| 17 | risk_management.stop_loss_pips | Build, Retest, Optimize | stop_loss_pips | - | - |
| 18 | risk_management.take_profit_pips | Build, Retest, Optimize | take_profit_pips | - | - |
| 19 | risk_management.rr_ratio | Build, Optimize | rr_ratio | - | - |
| 20 | risk_management.max_portfolio_heat_pct | Build, Optimize | max_portfolio_heat_pct | - | - |
| 21 | money_management.position_sizing_method | Build, Optimize | position_sizing_method | - | - |
| 22 | money_management.fixed_fractional_pct | Build, Optimize | fixed_fractional_pct | - | - |
| 23 | money_management.compounding | Build, Optimize | compounding | - | - |
| 23 | statistical_edge.expected_sharpe | Retest, Optimize | expected_sharpe | - | - |
| 24 | statistical_edge.win_rate | Retest, Optimize | win_rate | - | - |
| 24 | statistical_edge.profit_factor | Retest, Optimize | profit_factor | - | - |
| 24 | statistical_edge.expectancy_per_trade | Retest, Optimize | expectancy_per_trade | - | - |
| 25 | hypothesis | Retest, Optimize, AutoRetest | hypothesis | - | - |
| 26 | broker_info.commission_per_lot | Build, Optimize, Retest | commission_per_lot | - | - |
| 27 | broker_info.slippage_pips | Build, Retest, Optimize | slippage_pips | - | - |
| 28 | broker_info.spread_pips | Build, Filtering, Retest, Optimize | spread_pips | - | - |
| 29 | broker_info.swap_long | Build, Retest | swap_long | - | - |
| 30 | broker_info.swap_short | Build, Retest | swap_short | - | - |
| 31 | broker_info.triple_swap_day | Build, Retest | triple_swap_day | - | - |

---

## Transform Functions

| Name | Signature | Description |
|------|-----------|-------------|
| capital_to_risk_usd | (capital: float, risk_pct: float=1.0) → float | risk_usd = capital * risk_pct/100 |
| capital_to_max_lot | (capital: float, leverage: float=30.0, min_lot: float=0.01) → float | max_lot = max(min_lot, (capital*leverage)/100000) |
| capital_to_risk_pips | (capital, risk_pct=1.0, min_lot=0.01, pip_value=10.0) → int | sl_pips = risk_usd / (min_lot * pip_value) |
| market_to_symbol | (market: str) → str | Identity for forex |
| timeframe_to_wf_cycles | (tf: str) → int | M1=20, M5=15, M15=12, M30=10, H1=8, H4=6, D1=5, W1=3, MN=2 |

---

## Task Default Parameters (TASK_DEFAULTS)

Each task type has default parameters applied before exploration mapping:

| Task Type | Key Defaults |
|-----------|--------------|
| Build | 54 params (exit_at_end_of_day=False, max_trades=0, sl_required=True, min_sl_pips=10, etc.) |
| Filtering | conditions="NetProfit > 1000" |
| Retest | monte_carlo_runs=500, walkforward_cycles=5 |
| GoToTask | target="Filtering", condition="retest_failed" |
| Optimize | walkforward_cycles=10, optimize_params="maxOptimizations=100" |
| AutomaticRetest | retest_with_higher_precision=False, precision=4, spread=2 |
| AutomaticPortfolioBuilder | search_type="bruteforce", min_strategies=2, max_strategies=8 |
| CreatePortfolio | — (moved to TASK_PARAM_SCHEMAS: maxStrategies=100) |
| CustomAnalysis | — (no documented default; the 9 declared keys default to None) |
| LogDatabankStats | — (moved to TASK_PARAM_SCHEMAS: databank="Results") |
| SaveToFiles | — (no documented default; the 25 declared keys default to None) |
| LoadFromFiles | — (no documented default; the 4 declared keys default to None) |
| UpdateData | — (moved to TASK_PARAM_SCHEMAS: type="project") |
| WaitFor | — (moved to TASK_PARAM_SCHEMAS: action="user") |

> Since T13 the seven single-parameter types above no longer appear here at all:
> their defaults live in `TASK_PARAM_SCHEMAS`
> (`sdk/quantlab/exploration/params_schema.py`). The schema is what decides
> which keys survive `coerce_params`, so a second copy in this module is exactly
> what let the two vocabularies drift apart: this table declared
> `portfolio_name`, `analysis_type`, `log_details`, `save_path`, `load_path`,
> `update_mode` and `wait_seconds`, and no serializer reads any of them — a
> caller could set them and the value never reached the `.cfx`. The serializer
> vocabulary harvested from SQX 144/2953 is authoritative
> (`odd/notes/sqx-task-xml-dialect.md`), and
> `tests/customproject/test_t13_param_vocabulary_reaches_the_cfx.py` proves every
> declared key changes the generated task XML.

---

## Acceptance Criteria

| Scenario | Expected |
|---------|----------|
| Valid ExplorationDecision + standard template | Returns dict with all 21 catalog task types, params coerced to schema |
| Missing optional fields | Uses the `TASK_PARAM_SCHEMAS` default for the missing param |
| Invalid param value | validate_task_params() returns error list |
| Custom rules injected | Custom rules applied after built-in rules |
| Deterministic | Same input → byte-identical output dict |

---

## Test Cases

| Test | Description |
|------|-------------|
| test_param_mapper_basic | Maps capital_usd=1000 → risk_per_trade_usd=10.0 |
| test_param_mapper_leverage | Maps leverage=50 → Build.leverage=50 |
| test_param_mapper_timeframe | Maps timeframe="H1" → walkforward_cycles=8 |
| test_param_mapper_instruments | Maps instruments=["EURUSD","GBPUSD"] → Build.instruments |
| test_coerce_params | Coerces string "true" → bool True |
| test_validate_params | Catches invalid enum, out-of-range values |
| test_custom_rules | Custom rules appended and executed |
| test_deterministic | Same input → byte-identical output dict |

---

## Implementation Notes

- **Module**: `sdk/quantlab/exploration/param_mapper.py`
- **Dependencies**: `exploration.models.ExplorationDecision`, `customproject.models.CustomProjectTask`, `exploration.params_schema`
- **Registry**: `TRANSFORM_REGISTRY` decorator for transform functions
- **Schema**: `exploration.params_schema.TASK_PARAM_SCHEMAS` (14 task types, 200+ params total)

---

## Related Specs

- `specs/params_schema.md` — Parameter schemas per task type
- `specs/config_builder.md` — ConfigBuilderStage
- `specs/mobile_notifier.md` — Mobile notifications (C6)
- `specs/backtest_comparator.md` — Backtest comparison (C9)
- `specs/live_ops.md` — Live-ops pool + Guardian (C10)