# Campaign Reconfiguration Specification

## Purpose

Adaptive reconfiguration loop for the campaign lifecycle. After each iteration, ReviewerAgent ITERATE decisions trigger BuildConfig changes and a fresh SQX build, enabling strategy refinement across iterations.

## Requirements

### Requirement: Reconfiguration Loop Control

The system MUST branch on review_decision: ITERATE → apply changes and rebuild; REJECT → abort campaign; APPROVE → proceed to portfolio. auto_iterate SHALL enable or disable the loop.

#### Scenario: ITERATE triggers versioned rebuild

- GIVEN review_decision=ITERATE with auto_iterate=True
- WHEN apply_iteration_proposal() succeeds
- THEN a versioned project directory is created and a fresh SQX build is launched

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

The system MUST implement apply_iteration_proposal() mapping ReviewerAgent parameter_changes to BuildConfig fields: generations, population, ranking criteria, SL/PT, WF/MC. Unknown changes SHALL warn and be skipped.

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
