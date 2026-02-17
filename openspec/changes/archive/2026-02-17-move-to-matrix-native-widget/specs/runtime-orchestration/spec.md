## MODIFIED Requirements

### Requirement: Bot API Runtime Serving
The system SHALL run `bot-api` as a long-lived ASGI process that serves existing webhook routes and Matrix-native widget runtime routes used for Room-2 doctor decisions.

#### Scenario: Bot API process starts in runtime mode
- **WHEN** the `bot-api` runtime entrypoint is launched with valid settings
- **THEN** the process MUST remain running and serve `/callbacks/triage-decision` and Matrix-native Room-2 widget runtime routes/assets

#### Scenario: Widget route behavior remains unchanged for business outcomes
- **WHEN** a valid Matrix-native widget decision request is submitted
- **THEN** decision persistence, state transitions, and downstream enqueue behavior MUST match existing decision service contracts

## ADDED Requirements

### Requirement: Widget Runtime SHALL Not Depend on App Login for Doctor Actions
Runtime widget decision flow SHALL NOT require app login token issuance from `/auth/login` for doctor operation.

#### Scenario: Doctor uses widget from Matrix client context
- **WHEN** a doctor executes bootstrap and submit through Matrix-native widget context
- **THEN** runtime MUST authorize using Matrix-derived widget identity context
- **AND** no `/auth/login` token exchange MUST be required for the widget decision path
