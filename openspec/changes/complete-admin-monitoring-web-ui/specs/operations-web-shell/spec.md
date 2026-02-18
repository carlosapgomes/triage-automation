# operations-web-shell Specification

## ADDED Requirements

### Requirement: Web Pages SHALL Share A Unified Operations Shell

The system SHALL render dashboard and admin pages within one shared shell containing consistent navigation, visual hierarchy, and page framing.

#### Scenario: Authenticated user opens dashboard list

- **WHEN** an authenticated user requests `GET /dashboard/cases`
- **THEN** the response MUST use the shared shell layout
- **AND** the shell MUST include a visible logout action

#### Scenario: Authenticated admin opens prompt management page

- **WHEN** an authenticated admin requests the admin prompts page
- **THEN** the response MUST use the same shared shell layout
- **AND** the active navigation item MUST reflect the current page

### Requirement: Shell Navigation SHALL Be Role-Aware

The system SHALL render navigation options according to role permissions.

#### Scenario: Reader navigates authenticated shell

- **WHEN** an authenticated `reader` renders any shell page
- **THEN** the shell MUST include dashboard navigation
- **AND** the shell MUST NOT include prompt-admin navigation

#### Scenario: Admin navigates authenticated shell

- **WHEN** an authenticated `admin` renders any shell page
- **THEN** the shell MUST include dashboard and prompt-admin navigation

### Requirement: Unauthorized Shell Access SHALL Be Rejected Deterministically

The system SHALL enforce authorization for all shell pages using server-side checks.

#### Scenario: Reader requests admin prompts HTML page

- **WHEN** an authenticated `reader` requests an admin prompts page
- **THEN** the system MUST deny access with authorization failure
- **AND** no prompt state MUST change
