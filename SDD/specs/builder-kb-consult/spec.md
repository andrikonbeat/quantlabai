# Builder KB Consult Specification

## Purpose

Contract for `builder_agent` to consult the SQX Parameter KB before configuring builder parameters, ensuring every configured parameter has a KB entry or explicit override justification.

## Requirements

### Requirement: REQ-204 Builder KB Consult

The system MUST require `builder_agent` to call `KbStore.consult()` for each builder-relevant parameter or tab before translation/configuration proceeds. If `consult()` returns an empty list for a configured parameter, the agent MUST emit a warning or block configuration per the missing-entry contract. The agent SHALL record consulted parameters and their KB status in the build envelope.

#### Scenario: KB hit — config proceeds

- GIVEN `builder_agent` has a `ResearchConfig` with parameters in "Trading options" and "Ranking"
- AND the KB has verified entries for all configured parameters
- WHEN `builder_agent.run()` reaches parameter configuration
- THEN `KbStore.consult()` returns guidance metadata for each parameter
- AND translation proceeds without KB warnings

#### Scenario: Missing entry blocks configuration

- GIVEN `builder_agent` has a `ResearchConfig` referencing a parameter with no KB entry
- WHEN `KbStore.consult()` returns an empty list for that parameter
- THEN `builder_agent` emits a warning or raises a `ConfigurationError`
- AND the build envelope records the missing parameter name and tab
- AND translation halts (blocking) or proceeds with a warning (non-blocking mode)

#### Scenario: Empty KB — graceful degradation

- GIVEN the SQX KB is unseeded or the lake directory is empty
- WHEN `builder_agent` attempts to consult any parameter
- THEN `KbStore.consult()` returns empty lists for all parameters
- AND `builder_agent` emits a warning for each configured parameter
- AND translation halts with a consolidated missing-entry error

#### Scenario: Needs-review entry surfaces warning

- GIVEN a KB entry exists with `status: needs_review`
- WHEN `builder_agent` consults that parameter
- THEN the guidance metadata is returned
- AND a warning is logged noting the entry is not yet verified
- AND translation proceeds (needs_review does not block, only absence blocks)

## Non-Goals

- No changes to `config_reviewer.py` (REQ-205 blocked by concurrent edits)
- No dashboard changes or new `/kb` routes
- No changelog polling (Task 6.3 deferred)
- No modifications to `compiler.py`, `jforex_deploy.py`, `project_builder.py`, or `test_project_builder.py`

## Test Mapping

| Scenario | Test Case |
|----------|-----------|
| KB hit — config proceeds | `test_builder_consult_kb_hit_allows_translation` |
| Missing entry blocks configuration | `test_builder_consult_missing_entry_raises_block` |
| Empty KB — graceful degradation | `test_builder_consult_empty_kb_halts_with_warning` |
| Needs-review entry surfaces warning | `test_builder_consult_needs_review_proceeds_with_warning` |
