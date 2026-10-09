# Delta for autonomous-monitor

## ADDED Requirements

### Requirement: Live Feed and Feedback Wiring (REQ-41)

The autonomous monitor MUST stream live demo-account equity/positions during the demo phase and deliver the feed to MetaGuardian (REQ-40) and the Guardian feedback record (REQ-34). All existing daemon behaviors (heartbeat, reconnect, alerts) SHALL remain; alert dispatch SHALL also route to the mobile push channel (REQ-35).

#### Scenario: Demo feed streamed

- GIVEN a running demo phase with the daemon active
- WHEN `stream_live(campaign_id)` consumes the account feed
- THEN equity/positions are streamed to MetaGuardian
- AND heartbeat/metrics continue as before

#### Scenario: Alerts reach mobile

- GIVEN a CRITICAL alert during demo
- WHEN the daemon dispatches
- THEN the mobile push channel receives it (REQ-35)
- AND console/webhook still receive it
