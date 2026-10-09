# Delta for campaign-monitor

## ADDED Requirements

### Requirement: Substrate-Backed Event Detection (REQ-42)

`CampaignMonitor` MUST run as the event-detection component of the unified execution substrate (REQ-26), parameterized per phase, detecting stalls/config errors across build/retest/optimize/portfolio phases. Existing signals (status text, exported `strategies.csv`, REQ-21) SHALL remain.

#### Scenario: Monitor runs on substrate

- GIVEN the unified flag enabled and a running phase
- WHEN the substrate executes the phase
- THEN event detection runs on the substrate's polling
- AND stall/config events flow as WatcherEvents

#### Scenario: Legacy monitor unchanged

- GIVEN the unified flag disabled
- WHEN dispatch spawns a monitor
- THEN prior standalone behavior is preserved
