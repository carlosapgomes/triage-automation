# operations-web-shell Specification

## MODIFIED Requirements

### Requirement: Shell Navigation SHALL Be Role-Aware

The system SHALL render navigation options according to role permissions.

#### Scenario: Reader navigates authenticated shell

- **WHEN** an authenticated `reader` renders any shell page
- **THEN** the shell MUST include dashboard navigation
- **AND** the shell MUST NOT include prompt-admin navigation
- **AND** the shell MUST NOT include user-admin navigation

#### Scenario: Admin navigates authenticated shell

- **WHEN** an authenticated `admin` renders any shell page
- **THEN** the shell MUST include dashboard, prompt-admin, and user-admin navigation

### Requirement: Unauthorized Shell Access SHALL Be Rejected Deterministically

The system SHALL enforce authorization for all shell pages using server-side checks.

#### Scenario: Reader requests admin prompts HTML page

- **WHEN** an authenticated `reader` requests an admin prompts page
- **THEN** the system MUST deny access with authorization failure
- **AND** no prompt state MUST change

#### Scenario: Reader requests admin users HTML page

- **WHEN** an authenticated `reader` requests an admin users page
- **THEN** the system MUST deny access with authorization failure
- **AND** no user-account state MUST change
