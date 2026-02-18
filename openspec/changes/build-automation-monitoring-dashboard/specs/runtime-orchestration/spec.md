# Specification Delta

## MODIFIED Requirements

### Requirement: Bot API Runtime Serving

The system SHALL run `bot-api` as a long-lived ASGI process that serves monitoring dashboard APIs and admin prompt-management APIs, while standard Room-2 doctor decisions are executed through Matrix structured replies.

#### Scenario: Bot API process starts in runtime mode

- **WHEN** the `bot-api` runtime entrypoint is launched with valid settings
- **THEN** the process MUST remain running and expose monitoring/admin API routes required by the dashboard feature
- **AND** the runtime MUST NOT expose legacy HTTP decision routes

#### Scenario: Legacy HTTP decision route is not part of runtime surface

- **WHEN** operators inspect runtime API routes for decision execution
- **THEN** no legacy HTTP decision path MUST be available
- **AND** decision transitions MUST remain driven by Matrix structured replies

### Requirement: Matrix Structured Reply SHALL Be The Single Standard Room-2 Decision Path

Runtime behavior SHALL treat structured Matrix replies in Room-2 as the canonical doctor decision path for normal operations.

#### Scenario: Case awaiting doctor decision in Room-2

- **WHEN** a case is in `WAIT_DOCTOR`
- **THEN** decision processing MUST be driven by structured Matrix replies to Room-2 case context messages
- **AND** no optional parallel standard decision path MUST be required
