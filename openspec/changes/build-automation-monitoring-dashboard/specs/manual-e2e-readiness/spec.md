# Specification Delta

## MODIFIED Requirements

### Requirement: Deterministic Manual Runtime Validation

The project SHALL define deterministic smoke checks for validating live runtime readiness before full manual end-to-end testing using the single structured-reply Room-2 decision path and the monitoring/admin dashboard APIs.

#### Scenario: Pre-E2E smoke execution

- **WHEN** operators prepare for manual end-to-end testing
- **THEN** they MUST be able to verify service startup, database readiness, and Room-2 structured reply readiness with documented deterministic checks
- **AND** they MUST be able to verify dashboard API reachability with authenticated role-based access

## ADDED Requirements

### Requirement: Manual E2E SHALL Validate Dashboard Timeline Auditability

Manual runbooks SHALL validate that case timeline views expose chronological records across rooms with actor, timestamp, and ACK visibility.

#### Scenario: Operator reviews a processed case in dashboard

- **WHEN** operator opens a case detail in the monitoring dashboard
- **THEN** the timeline MUST display chronological events across Room-1/Room-2/Room-3
- **AND** ACK and human reply events MUST be visible with actor and timestamp metadata

### Requirement: Manual E2E SHALL Validate Prompt Management Authorization

Manual runbooks SHALL validate role-based authorization for prompt-management operations.

#### Scenario: Admin and reader execute prompt-management actions

- **WHEN** an `admin` performs prompt activation and a `reader` attempts the same action
- **THEN** admin action MUST succeed and produce an audit event
- **AND** reader action MUST be rejected with no mutation of active prompt version
