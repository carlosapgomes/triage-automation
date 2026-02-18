# prompt-management-admin Delta Specification

## MODIFIED Requirements

### Requirement: Admin SHALL Manage Prompt Versions

The system SHALL provide prompt-management operations for authenticated `admin` users to list prompt versions, inspect active version state, and activate a selected version through both API endpoints and authenticated web pages.

#### Scenario: Admin lists prompt versions

- **WHEN** an authenticated `admin` requests prompt catalog data
- **THEN** the system MUST return prompt names, versions, and active flags

#### Scenario: Admin activates a prompt version

- **WHEN** an authenticated `admin` activates a specific version for a prompt name
- **THEN** the system MUST set that version as active
- **AND** the system MUST preserve the invariant of a single active version per prompt name

### Requirement: Reader SHALL Have Read-Only Monitoring Access

The system SHALL restrict prompt-management operations to `admin` and MUST reject prompt-management page/API access attempts by `reader`.

#### Scenario: Reader attempts prompt activation

- **WHEN** an authenticated `reader` submits a prompt activation request
- **THEN** the system MUST reject the operation with authorization failure
- **AND** no prompt active-version state MUST change

#### Scenario: Reader requests prompt admin page

- **WHEN** an authenticated `reader` requests the prompt-management HTML page
- **THEN** the system MUST reject access with authorization failure

## ADDED Requirements

### Requirement: Prompt Management SHALL Have An Authenticated HTML Admin Surface

The system SHALL provide server-rendered prompt-management pages for `admin` users inside the operations web shell.

#### Scenario: Admin opens prompt management page

- **WHEN** an authenticated `admin` requests the prompt-management page
- **THEN** the system MUST render prompt names, versions, active state, and activation controls
