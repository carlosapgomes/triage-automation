# Specification Delta

## ADDED Requirements

### Requirement: Admin SHALL Manage Prompt Versions

The system SHALL provide prompt-management operations for authenticated `admin` users to list prompt versions, inspect active version state, and activate a selected version.

#### Scenario: Admin lists prompt versions

- **WHEN** an authenticated `admin` requests prompt catalog data
- **THEN** the system MUST return prompt names, versions, and active flags

#### Scenario: Admin activates a prompt version

- **WHEN** an authenticated `admin` activates a specific version for a prompt name
- **THEN** the system MUST set that version as active
- **AND** the system MUST preserve the invariant of a single active version per prompt name

### Requirement: Reader SHALL Have Read-Only Monitoring Access

The system SHALL restrict prompt-management mutation operations to `admin` and MUST reject mutation attempts by `reader`.

#### Scenario: Reader attempts prompt activation

- **WHEN** an authenticated `reader` submits a prompt activation request
- **THEN** the system MUST reject the operation with authorization failure
- **AND** no prompt active-version state MUST change

### Requirement: Prompt Management Actions SHALL Be Auditable

The system SHALL create audit records for prompt-management actions containing actor identity, action type, target prompt/version, and timestamp.

#### Scenario: Prompt activation succeeds

- **WHEN** an `admin` activation operation completes
- **THEN** the system MUST append an audit event describing the change
- **AND** the event MUST include actor id and target prompt metadata
