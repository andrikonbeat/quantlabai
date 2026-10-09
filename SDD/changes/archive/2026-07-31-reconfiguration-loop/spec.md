# Delta for Reconfiguration Loop

## ADDED Requirements

### Requirement: Reconfiguration Loop Control

The system MUST branch on review_decision: ITERATE → apply changes and rebuild; REJECT → abort; APPROVE → proceed to portfolio. auto_iterate SHALL enable or disable the loop.

#### Scenario: ITERATE triggers versioned rebuild

- GIVEN review_decision=ITERATE with auto_iterate=True
- WHEN apply_iteration_proposal() succeeds
- THEN a versioned directory is created and a fresh SQX build is launched

#### Scenario: REJECT aborts campaign

- GIVEN review_decision=REJECT
- WHEN the orchestrator evaluates the decision
- THEN the campaign aborts with the rejection reason

#### Scenario: APPROVE exits loop

- GIVEN review_decision=APPROVE
- WHEN the orchestrator evaluates the decision
- THEN the loop exits and portfolio composition begins

#### Scenario: auto_iterate=False bypasses loop

- GIVEN auto_iterate=False
- WHEN the campaign completes an iteration
- THEN no reconfiguration occurs
- AND the campaign proceeds to portfolio

#### Scenario: Max iterations reached

- GIVEN max_iterations is 5
- AND all 5 iterations complete without approval or degradation abort
- WHEN the limit is reached
- THEN the best result across all iterations is returned

### Requirement: Proposal Application

The system MUST implement apply_iteration_proposal() mapping parameter_changes to BuildConfig fields: generations, population, ranking criteria, SL/PT, WF/MC. Unknown changes SHALL warn and be skipped.

#### Scenario: Valid changes applied

- GIVEN parameter_changes with known BuildConfig fields
- WHEN apply_iteration_proposal() processes them
- THEN each known field updates the BuildConfig

#### Scenario: Unknown changes skipped with warning

- GIVEN parameter_changes containing an unrecognized field
- WHEN apply_iteration_proposal() processes them
- THEN a warning is logged
- AND the unknown field is skipped

#### Scenario: Empty changes trigger graceful degradation

- GIVEN empty parameter_changes
- WHEN apply_iteration_proposal() processes them
- THEN no BuildConfig fields are modified
- AND the loop continues with new hypotheses only

### Requirement: Iteration State Management

| Sub-requirement | Behavior |
|-----------------|----------|
| Versioned IDs | MUST use `{campaign_id}_iter{02d}` for iteration project directories |
| Best-result tracking | MUST track best selected_strategies count or aggregate score across iterations |
| Degradation abort | MUST abort when 2+ consecutive iterations yield worse results than the best; return best result |

#### Scenario: Iteration state tracked

- GIVEN multiple iterations with varying results
- WHEN the orchestrator tracks state
- THEN versioned directories are created, best results are preserved, and degradation triggers abort

## MODIFIED Requirements

### Requirement: Campaign Lifecycle

The system MUST execute the campaign flow with optional reconfiguration. When auto_iterate=True and review_decision=ITERATE, the system SHALL apply parameter changes and rebuild in a versioned directory. When REJECT, it SHALL abort. When APPROVE, it SHALL proceed to portfolio. When auto_iterate=False, it SHALL execute a single iteration.

(Previously: Sequential execution without reconfiguration loop)

#### Scenario: Full campaign completes successfully

- GIVEN a valid ResearchConfig and a licensed SQX environment
- AND auto_iterate is True
- WHEN the orchestrator runs a campaign
- THEN the standard flow executes with optional reconfiguration between iterations
- AND a CampaignMonitor asyncio task runs concurrently during the run/poll phases
- AND the monitor is cancelled when the campaign reaches a terminal state

#### Scenario: Campaign fails at translation — no monitor spawned

- GIVEN a ResearchConfig that fails DSL-to-CFX translation
- WHEN the orchestrator runs the campaign
- THEN a CampaignError is raised at the translate phase
- AND no sqcli commands are dispatched
- AND no CampaignMonitor is spawned

#### Scenario: Campaign times out during polling — monitor cancelled

- GIVEN a campaign that exceeds the configured poll timeout
- WHEN the orchestrator polls for status beyond the limit
- THEN a CampaignError with timeout detail is raised
- AND the sqcli project is stopped via `-project action=stop`
- AND the CampaignMonitor task is cancelled

## ADDED Requirements

### Requirement: IterationConfig auto_iterate Flag

The system MUST define IterationConfig with auto_iterate controlling the reconfiguration loop.

#### Scenario: auto_iterate=True enables loop

- GIVEN IterationConfig.auto_iterate=True
- WHEN execute_campaign runs
- THEN the orchestrator evaluates review_decision after each iteration

#### Scenario: auto_iterate=False preserves single-iteration behavior

- GIVEN IterationConfig.auto_iterate=False
- WHEN execute_campaign runs
- THEN a single iteration executes
- AND portfolio composition begins
