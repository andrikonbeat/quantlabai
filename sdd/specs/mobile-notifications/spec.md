# Mobile Notifications Specification

## Purpose

Adds a mobile push notifier channel and a 24-7 operations surface so Guardian and demo-window alerts reach the user outside the desktop.

## Requirements

### Requirement: Mobile Push Channel (REQ-35)

The system MUST provide a mobile push notifier registered in `NotifierDispatcher` alongside console/webhook/email/slack, routing by severity per policy (CRITICAL → push; WARNING → push configurable). Push delivery failures MUST be logged without breaking the alert pipeline.

#### Scenario: CRITICAL alert pushes

- GIVEN the push notifier registered and a CRITICAL alert
- WHEN the dispatcher routes
- THEN the push channel sends the full payload
- AND other configured channels still receive it

#### Scenario: Push failure degrades gracefully

- GIVEN the push provider unreachable
- WHEN an alert fires
- THEN the failure is logged at WARNING
- AND the remaining channels deliver

### Requirement: 24-7 Ops Surface (REQ-36)

The system SHALL support 24-7 monitoring via daemon mode with mobile escalation for Guardian state changes (NORMAL → VIGILANCE → DEFENSIVE → QUARANTINE) and demo window expiry.

#### Scenario: Overnight escalation

- GIVEN the daemon running and a Guardian DEFENSIVE transition at night
- WHEN the transition fires
- THEN a push alert is dispatched with state and reason
- AND the alert is acknowledged via the ops surface
