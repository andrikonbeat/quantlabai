# Delta for quantlab-orchestrator

## ADDED Requirements

### Requirement: Legacy Agent Retirement (G4)

The live `~/.config/opencode/opencode.json` MUST NOT register `quantlab-deploy` or `quantlab-monitor`. Dangling references to `quantlab-run`, `quantlab-status`, and `quantlab-compare` MUST be pruned from the orchestrator bash allowlist, task allowlist, and `orchestrator.md` routing table.

#### Scenario: Legacy entries absent

- GIVEN the updated opencode.json
- WHEN the agents map is inspected
- THEN `quantlab-deploy` and `quantlab-monitor` are not present
- AND no routing rows for run/status/compare remain

#### Scenario: Dangling refs pruned

- GIVEN the updated orchestrator config and prompt
- WHEN allowlists and routing tables are scanned
- THEN no `quantlab-run|status|compare` reference remains

### Requirement: Deny-First Bash Scope (G4)

`quantlab-campaign` MUST adopt a deny-first bash block: `{*: deny, sdk/quantlab/pipeline/*: allow, sdk/quantlab/campaign/*: allow}`. The stale `sdk/pipeline/*` allow on `quantlab-orchestrator` MUST be corrected to `sdk/quantlab/pipeline/*`.

#### Scenario: Campaign agent is deny-first

- GIVEN the quantlab-campaign agent config
- WHEN its permission block is read
- THEN bash defaults to deny with only the two SDK paths allowed

#### Scenario: Orchestrator path corrected

- GIVEN the quantlab-orchestrator agent config
- WHEN the auto_approve list is read
- THEN it references `sdk/quantlab/pipeline/*`, not `sdk/pipeline/*`

### Requirement: Live Config Restore Path (G4)

Changes to the live config MUST be rollback-safe: a backup of `opencode.json` MUST be created before editing, the installer overlay (`installer/internal/opencode/overlay.json`) MUST be updated in the same change, and `tests/test_orchestrator_prompt.py` MUST stay green (or its updates MUST be deliberate and documented).

#### Scenario: Backup and rollback

- GIVEN the pre-edit config backup exists
- WHEN the change is rolled back
- THEN the backup is restored byte-for-byte
- AND the installer overlay matches the restored config

#### Scenario: Pinned tests stay green

- GIVEN the change applied
- WHEN `test_orchestrator_prompt.py` runs
- THEN the pinned campaign/orchestrator/guardian/14-phase assertions pass
- AND any test change is intentional, not collateral