# Delta for SQX Translator

## ADDED Requirements

### Requirement: Portfolio CFX Template Generation

The system MUST provide a method to generate Portfolio Master CFX from strategy list and genetic parameters, reusing cfx-editor extensions.

#### Scenario: Generate portfolio CFX from strategy IDs

- GIVEN strategy IDs ["s1", "s2", "s3"], generations=50, population=100
- WHEN `SQXTranslator.generate_portfolio_cfx(strategies, generations=50, population=100)` is called
- THEN a valid Portfolio Master CFX is produced with AutomaticPortfolioBuilder section
- AND all strategies are referenced in the Strategies subsection

#### Scenario: Generate portfolio CFX with custom fitness

- GIVEN strategies and fitness="SharpeRatio"
- WHEN `generate_portfolio_cfx(fitness="SharpeRatio")` is called
- THEN the CFX FitnessFunction element equals "SharpeRatio"

#### Scenario: Generate portfolio CFX reuses cfx-editor models

- GIVEN any valid input
- WHEN portfolio CFX is generated
- THEN cfx-editor's PortfolioCfxModel and CfxWriter are used internally
- AND no duplicate XML construction logic exists

### Requirement: Optimizer CFX Template Generation

The system MUST provide a method to generate Optimizer CFX from parameter specification.

#### Scenario: Generate optimizer CFX from config

- GIVEN `OptimizerConfig(walkforward_cycles=10, method="Genetic", objective="NetProfit")`
- WHEN `SQXTranslator.generate_optimizer_cfx(config, strategy_id="s1")` is called
- THEN a valid Optimizer CFX is produced with Optimization, Parameters, WalkForward, Databanks sections

#### Scenario: Generate optimizer CFX uses cfx-editor extensions

- GIVEN any optimizer config
- WHEN CFX is generated
- THEN cfx-editor's OptimizerCfxModel and CfxWriter are used
- AND the resulting CFX is loadable by SQX Optimizer

### Requirement: Retester CFX Template Generation

The system MUST provide a method to generate Retester CFX from strategy and databank configuration.

#### Scenario: Generate retester CFX from config

- GIVEN `RetesterConfig(databanks=["EURUSD_H1"], monte_carlo_runs=100, walkforward_cycles=5)`
- WHEN `SQXTranslator.generate_retester_cfx(config, strategy_id="s1")` is called
- THEN a valid Retester CFX is produced with Rankings, CrossChecks, Data sections

#### Scenario: Generate retester CFX uses cfx-editor extensions

- GIVEN any retester config
- WHEN CFX is generated
- THEN cfx-editor's RetesterCfxModel and CfxWriter are used
- AND the resulting CFX is loadable by SQX Retester

## MODIFIED Requirements

### Requirement: DSL-to-CFX Translation

The system MUST translate a valid research DSL model into a CFX archive using cfx-editor typed Pydantic models. The translation MUST encode market, timeframe, strategy parameters, and entry/exit rules via cfx-editor domain methods (`set_market()`, `add_timeframe()`, etc.), then produce the final archive through CfxWriter. (Previously: Build CFX only)

#### Scenario: Complete translation produces portfolio CFX

- GIVEN a research model with portfolio=True, strategies=["s1", "s2"], generations=30
- WHEN the system translates it using cfx-editor models
- THEN a valid Portfolio Master CFX archive is produced
(Previously: only Build CFX was produced)

#### Scenario: Complete translation produces optimizer CFX

- GIVEN a research model with optimizer=True, walkforward_cycles=5
- WHEN the system translates it
- THEN a valid Optimizer CFX archive is produced
(Previously: only Build CFX was produced)

#### Scenario: Complete translation produces retester CFX

- GIVEN a research model with retester=True, databanks=["EURUSD_H1"], mc_runs=100
- WHEN the system translates it
- THEN a valid Retester CFX archive is produced
(Previously: only Build CFX was produced)

### Requirement: CFX Packaging

The system MUST produce a CFX archive containing multiple XML files — `config.xml` for task routing and task-specific XML files (e.g., `Build-Task1.xml`) for settings. Each XML MUST use UTF-8 without XML declaration. The archive MUST use ZIP/DEFLATE compression with `.cfx` extension. (Previously: Build task packaging only)

#### Scenario: Portfolio CFX packaged as multi-file archive

- GIVEN translated portfolio cfx-editor models
- WHEN CfxWriter packages them as `.cfx`
- THEN a valid ZIP with `.cfx` extension is created containing config.xml + Portfolio-Task1.xml
(Previously: only Build-Task1.xml was created)

#### Scenario: Optimizer CFX packaged as multi-file archive

- GIVEN translated optimizer cfx-editor models
- WHEN CfxWriter packages them as `.cfx`
- THEN a valid ZIP with `.cfx` extension is created containing config.xml + Optimizer-Task1.xml
(Previously: only Build-Task1.xml was created)

#### Scenario: Retester CFX packaged as multi-file archive

- GIVEN translated retester cfx-editor models
- WHEN CfxWriter packages them as `.cfx`
- THEN a valid ZIP with `.cfx` extension is created containing config.xml + Retester-Task1.xml
(Previously: only Build-Task1.xml was created)

### Requirement: Translation Validation

The system MUST validate that the input DSL model contains all required fields for CFX generation (market, timeframe, at least one strategy). Missing required fields MUST produce a TranslationError. (Previously: Build CFX validation only)

#### Scenario: Portfolio translation requires strategies list

- GIVEN a research model with portfolio=True but empty strategies list
- WHEN the system attempts translation
- THEN a TranslationError is raised specifying that strategies list is required for portfolio
(Previously: only market, timeframe, strategy validation existed)

#### Scenario: Optimizer translation requires strategy and walkforward

- GIVEN a research model with optimizer=True but missing strategy_id or walkforward_cycles
- WHEN the system validates
- THEN a TranslationError is raised listing missing fields
(Previously: only Build validation existed)

#### Scenario: Retester translation requires databanks

- GIVEN a research model with retester=True but empty databanks list
- WHEN the system validates
- THEN a TranslationError is raised specifying databanks are required for retester
(Previously: only Build validation existed)

## REMOVED Requirements

None.

## RENAMED Requirements

None.