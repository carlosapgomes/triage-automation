## MODIFIED Requirements

### Requirement: Bot API Runtime Serving
The system SHALL run `bot-api` as a long-lived ASGI process that serves compatibility callback routes, while standard Room-2 doctor decisions are executed through Matrix structured replies.

#### Scenario: Bot API process starts in runtime mode
- **WHEN** the `bot-api` runtime entrypoint is launched with valid settings
- **THEN** the process MUST remain running and serve `/callbacks/triage-decision` for emergency compatibility usage

#### Scenario: Callback route remains compatibility path
- **WHEN** a valid request is sent to `/callbacks/triage-decision`
- **THEN** response and state-transition behavior MUST match existing decision service contracts

### Requirement: Compose and UV Runtime Parity
The system SHALL provide behaviorally equivalent runtime startup paths for local `uv` execution and Docker Compose execution.

#### Scenario: Runtime command parity
- **WHEN** operators launch services via `uv` entrypoints or via Compose commands
- **THEN** both paths MUST execute the same application startup composition and dependency wiring

### Requirement: No Workflow Redesign During Runtime Wiring
Runtime orchestration changes SHALL NOT alter authoritative triage workflow behavior.

#### Scenario: Runtime orchestration code is introduced
- **WHEN** runtime-serving and startup wiring are implemented
- **THEN** state-machine semantics, decision contract, and cleanup trigger behavior MUST remain unchanged

## ADDED Requirements

### Requirement: Matrix Structured Reply SHALL Be The Single Standard Room-2 Decision Path
Runtime behavior SHALL treat structured Matrix replies in Room-2 as the canonical doctor decision path for normal operations.

#### Scenario: Case awaiting doctor decision in Room-2
- **WHEN** a case is in `WAIT_DOCTOR`
- **THEN** decision processing MUST be driven by structured Matrix replies to Room-2 case context messages
- **AND** no optional parallel standard decision path MUST be required

### Requirement: Callback Endpoint SHALL Be Marked For Deprecation
The callback endpoint SHALL be retained only for emergency compatibility and explicitly marked for near-term deprecation in runtime documentation.

#### Scenario: Runtime documentation is reviewed
- **WHEN** operators inspect runtime decision paths
- **THEN** documentation MUST identify callback as emergency-only compatibility path
- **AND** documentation MUST indicate planned deprecation status
