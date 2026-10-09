# Delta for Retester Automation

## MODIFIED Requirements

### Requirement: Retester Configuration Model

The system MUST provide a configuration class encapsulating all retester parameters including optional cost-related parameters.
(Previously: No cost parameters existed in RetesterConfig)

#### Scenario: RetesterConfig with cost params

- GIVEN `RetesterConfig(strategy_id="s1", databanks=["EURUSD_H1"], broker_profile="ib")`
- WHEN instantiated
- THEN broker_profile is stored
- AND cost_config defaults to None

#### Scenario: RetesterConfig without cost params (backward compatible)

- GIVEN `RetesterConfig(strategy_id="s1", databanks=["EURUSD_H1"])`
- WHEN instantiated
- THEN broker_profile is None
- AND cost_config is None
- AND existing params (monte_carlo_runs, walkforward_cycles, etc.) are unchanged

### Requirement: Generate Retester CFX

The system MUST generate a CFX file configuring the Retester with Monte Carlo and Walk-Forward sections, optionally including commission/cost parameters when a broker profile is provided.

#### Scenario: CFX with cost injection

- GIVEN `RetesterConfig(..., broker_profile="ib")`
- WHEN generating CFX
- THEN the CFX includes commission and spread settings matching the broker profile

#### Scenario: CFX without costs (backward compatible)

- GIVEN `RetesterConfig(..., broker_profile=None)`
- WHEN generating CFX
- THEN CFX has no commission/cost sections — identical to pre-change output
