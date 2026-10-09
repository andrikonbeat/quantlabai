# Delta for sqx-translator

## MODIFIED Requirements

### Requirement: DSL-to-CFX Translation

The system MUST translate a valid research DSL model into a CFX archive using cfx-editor typed Pydantic models. The translation MUST encode market, timeframe, strategy parameters, and entry/exit rules via cfx-editor domain methods (`set_market()`, `add_timeframe()`, etc.), then produce the final archive through CfxWriter.
(Previously: The system MUST translate a valid research model into XML conforming to the `.cfx` schema)

#### Scenario: Complete translation produces multi-file CFX
- GIVEN a valid research model with market EURUSD, timeframe H1, and one strategy with two building blocks
- WHEN the system translates it using cfx-editor models
- THEN a valid multi-file CFX archive is produced with config.xml routing to Build-Task1.xml containing the building blocks

#### Scenario: Empty strategies produce minimal archive
- GIVEN a research model with no building blocks (empty strategies section)
- WHEN the system translates it via cfx-editor
- THEN a minimal CFX archive is produced with config.xml, Build-Task1.xml with empty Blocks section, and no enabled blocks

### Requirement: CFX Packaging

The system MUST produce a CFX archive containing multiple XML files — `config.xml` for task routing and task-specific XML files (e.g., `Build-Task1.xml`) for settings. Each XML MUST use UTF-8 without XML declaration. The archive MUST use ZIP/DEFLATE compression with `.cfx` extension.
(Previously: The system MUST package the translated XML into a ZIP archive with `.cfx` extension. The archive MUST contain exactly one XML file)

#### Scenario: Valid multi-file archive created
- GIVEN translated cfx-editor models for a Build task
- WHEN CfxWriter packages them as `.cfx`
- THEN a valid ZIP with `.cfx` extension is created containing config.xml + Build-Task1.xml

#### Scenario: Dry-run mode returns model JSON without writing
- GIVEN a translated research model in dry-run mode
- WHEN the system is invoked with dry-run flag
- THEN the cfx-editor models are serialized to JSON and returned without creating any file on disk

### Requirement: Translation Validation

The system MUST validate that the input DSL model contains all required fields for CFX generation (market, timeframe, at least one strategy). Missing required fields MUST produce a TranslationError.

#### Scenario: Missing market raises TranslationError
- GIVEN a research model with an empty market field
- WHEN the system attempts translation
- THEN a TranslationError is raised specifying that market is required

#### Scenario: Unsupported timeframe raises error
- GIVEN a research model with a timeframe not supported by SQX (e.g., M1 on a 4-hour-only strategy)
- WHEN the system validates the translation
- THEN a ValidationError is raised listing supported timeframes
