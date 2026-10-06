# SQX Doc Provider Specification

## Purpose

Reads structured SQX parameter metadata and general official documentation from the Knowledge Lake, with transparent fallback when YAML is missing.

## Requirements

### Requirement: Parameter YAML Lookup

The provider MUST read parameter metadata from `structured/sqx-kb/{ver}/parameters/{tab}/{param}.yaml` and return type, range, enum values, and description. When YAML is missing, it MUST probe `_BUILD_CONFIG_MAP` for type and range hints without crashing.

#### Scenario: YAML-backed lookup returns metadata

- GIVEN a parameter YAML exists for `RSI/period` under `144.2953`
- WHEN `get_valid_range("RSI", "period", "144.2953")` is called
- THEN the declared `(min, max)` tuple is returned

#### Scenario: Missing YAML falls back to template defaults

- GIVEN no YAML exists for the requested parameter
- WHEN the provider probes `_BUILD_CONFIG_MAP`
- THEN a warning is emitted and inferred metadata is returned

### Requirement: General Doc Lookup (ADDED)

The provider MUST expose doc lookup beyond parameter YAML — `get_doc(kind, name, sqx_version)` for `block`, `api`, and `cheat-sheet` kinds backed by ingested docs. Parameter YAML behavior (REQ-F2-01..03) is unchanged.

#### Scenario: block doc resolves to Markdown file

- GIVEN `structured/sqx-kb/144.2953/docs/blocks/rsi.md` exists
- WHEN `get_doc("block", "RSI", "144.2953")` is called
- THEN a `DocRef` is returned with `kind="block"`, `path` pointing to the file, and `content` containing the Markdown body

#### Scenario: missing doc returns None with warning

- GIVEN no doc exists for the requested kind/name/version
- WHEN `get_doc("api", "Unknown", "144.2953")` is called
- THEN `None` is returned and a warning is logged

#### Scenario: version isolation applies

- GIVEN docs exist for `144.2953` but not `144.4000`
- WHEN `get_doc("block", "RSI", "144.4000")` is called
- THEN `None` is returned (no cross-version leakage)

### Requirement: KB-Driven Indicator Ranges (ADDED)

The provider MUST expose `get_indicator_range(indicator, sqx_version)` returning a mapping of parameter names to `(min, max)` tuples for known indicators, or `None` when the indicator is unknown.

#### Scenario: known indicator returns ranges

- GIVEN `RSI` is a known indicator with documented ranges
- WHEN `get_indicator_range("RSI", "144.2953")` is called
- THEN a dict like `{"period": (2.0, 200.0)}` is returned

#### Scenario: unknown indicator returns None

- GIVEN `FOOBAR` is not in the indicator registry
- WHEN `get_indicator_range("FOOBAR", "144.2953")` is called
- THEN `None` is returned
