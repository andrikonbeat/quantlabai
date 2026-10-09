# skill-format Specification

## Purpose

LLM-first skill format contract: YAML frontmatter, orchestrator/executor gate, exit conditions.

## Requirements

### Requirement: LLM-First Skill Format (REQ-904)

Every QuantLab skill MUST follow the LLM-first format: YAML frontmatter with `name`, `description`, `disable-model-invocation`, `user-invocable`, `license`, `metadata`, and a `## Execution Role` section defining executor/orchestrator boundaries. Skills MUST include an orchestrator/executor gate and explicit exit conditions.

#### Scenario: Skill loads with valid format

- GIVEN a skill directory with `SKILL.md`
- WHEN the skill registry loads it
- THEN frontmatter parses successfully
- AND the execution role is recognized

#### Scenario: Invalid format rejected

- GIVEN a `SKILL.md` missing frontmatter or execution role
- WHEN the registry loads it
- THEN the skill is flagged as invalid
- AND a repair reference is returned

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | All QuantLab skills have valid YAML frontmatter |
| 2 | All skills include `## Execution Role` section |
| 3 | Skills include orchestrator/executor gate and exit conditions |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/skills/quantlab-run-campaign/SKILL.md` | Deduped to pointer format |
| `ai/opencode/skills/quantlab-deploy-strategy/SKILL.md` | New LLM-first rewrite |
| `ai/opencode/skills/quantlab-monitor-status/SKILL.md` | New LLM-first rewrite |
