# model-assignments Specification

## Purpose

Uniform model policy for all QuantLab agents: single model assignment, no splits.

## Requirements

### Requirement: Uniform Model Policy (REQ-903)

All QuantLab agents MUST use `model: "opencode/deepseek-v4-flash-free"` in repo `opencode.json`. No agent MAY split models without an explicit change to this policy. `default_agent` MUST remain intact.

#### Scenario: All 19 agents share one model

- GIVEN the repo `opencode.json`
- WHEN the agent set loads
- THEN all 19 QuantLab agents declare `opencode/deepseek-v4-flash-free`
- AND `default_agent` is intact

#### Scenario: Split model rejected

- GIVEN an `opencode.json` edit that assigns different models
- WHEN validation runs
- THEN the validation fails
- AND the change is rejected

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | All 19 QuantLab agents declare `opencode/deepseek-v4-flash-free` |
| 2 | `default_agent` remains intact |
| 3 | Split model assignments are rejected by validation |

## Affected Files

| File | Change |
|------|--------|
| `opencode.json` | `model` on all QuantLab agents |
