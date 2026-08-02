# Packaging Dependencies Specification

## Purpose

Guarantees the runtime dependencies the code actually imports are declared and installed, so installed packages import without module-level errors.

## Requirements

### Requirement: DEP-01 Declared deps match reality

The 4 missing runtime deps `mcp`, `openai`, `feedparser`, `duckduckgo-search` MUST be installed in the venv(s) and declared in `[project].dependencies`.

#### Scenario: Imports resolve
- GIVEN the installed venv
- WHEN `import mcp, openai, feedparser, duckduckgo_search` runs
- THEN all four import without error

#### Scenario: mcp bridge loads
- GIVEN `mcp` installed
- WHEN `sdk/quantlab/mcp/bridge.py` is imported
- THEN no module-level ImportError occurs

**Acceptance**: no module-level ImportError in quantlab packages.
