# project-agents Specification

## Purpose

Repo-root AGENTS.md contract: single source of truth for project stack, testing conventions, harness conventions, and OpenSpec workflow.

## Requirements

### Requirement: Repo-Root AGENTS.md Contract (REQ-902)

The repo MUST contain a root `AGENTS.md` defining the project stack, testing conventions, harness conventions, and OpenSpec workflow. It SHALL be the single source of truth for agent onboarding. All QuantLab agents SHALL reference it at session start.

#### Scenario: New agent reads AGENTS.md

- GIVEN a new agent joining the project
- WHEN it reads `AGENTS.md`
- THEN it finds stack, testing, conventions, and workflow
- AND can start contributing without additional context

#### Scenario: Agent validates against AGENTS.md

- GIVEN an agent about to execute a task
- WHEN it checks `AGENTS.md` for conventions
- THEN the conventions are current
- AND the agent follows the documented workflow

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | `AGENTS.md` exists at repo root |
| 2 | `AGENTS.md` covers stack, testing, harness conventions, OpenSpec workflow |
| 3 | All QuantLab agents reference `AGENTS.md` at session start |

## Affected Files

| File | Change |
|------|--------|
| `AGENTS.md` | New repo-root technical English contract |
