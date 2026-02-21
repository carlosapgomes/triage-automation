# user-management-admin Specification

## ADDED Requirements

### Requirement: Admin SHALL Access User Management Surface

The system SHALL provide an authenticated administrative user-management surface
at `GET /admin/users` for users with role `admin`.

#### Scenario: Admin opens user management page

- **WHEN** an authenticated `admin` requests `GET /admin/users`
- **THEN** the system MUST return the user-management HTML page
- **AND** the page MUST include user listing and management controls

#### Scenario: Reader requests user management page

- **WHEN** an authenticated `reader` requests `GET /admin/users`
- **THEN** the system MUST reject access with authorization failure

### Requirement: Admin SHALL Create Reader And Admin Accounts

The system SHALL allow an authenticated `admin` to create new users with role
`reader` or `admin` using normalized unique email and a valid password.

#### Scenario: Admin creates reader account

- **WHEN** an authenticated `admin` submits a valid create-user request with role `reader`
- **THEN** the system MUST persist a new active user account with role `reader`

#### Scenario: Admin creates admin account

- **WHEN** an authenticated `admin` submits a valid create-user request with role `admin`
- **THEN** the system MUST persist a new active user account with role `admin`

#### Scenario: Duplicate email is submitted

- **WHEN** an authenticated `admin` submits a create-user request with an email that already exists after normalization
- **THEN** the system MUST reject the request
- **AND** no new user row MUST be created

### Requirement: Admin SHALL Manage User Lifecycle States

The system SHALL support lifecycle actions for existing users: block, reactivate,
and remove, with explicit account states.

#### Scenario: Admin blocks an active user

- **WHEN** an authenticated `admin` blocks a target user in `active` state
- **THEN** the target user state MUST become `blocked`
- **AND** the target user MUST be prevented from authenticating new sessions
- **AND** active sessions/tokens for the target user MUST be revoked

#### Scenario: Admin reactivates a blocked user

- **WHEN** an authenticated `admin` reactivates a target user in `blocked` state
- **THEN** the target user state MUST become `active`

#### Scenario: Admin removes a user

- **WHEN** an authenticated `admin` removes a target user
- **THEN** the target user state MUST become `removed`
- **AND** the user record MUST be retained as soft-deleted audit history
- **AND** active sessions/tokens for the target user MUST be revoked

### Requirement: Administrative Safety Invariants SHALL Be Enforced

The system SHALL enforce safety invariants that prevent administrative lockout
or unsafe self-management actions.

#### Scenario: Admin attempts self-block or self-remove

- **WHEN** an authenticated `admin` attempts to block or remove their own account
- **THEN** the system MUST reject the action
- **AND** no account state MUST change

#### Scenario: Action would leave zero active admins

- **WHEN** an authenticated `admin` attempts an action that would leave no active `admin` accounts
- **THEN** the system MUST reject the action
- **AND** at least one active `admin` account MUST remain

### Requirement: User Management Actions SHALL Be Auditable

The system SHALL append audit events for user-management actions with actor and
target metadata.

#### Scenario: User-management action succeeds

- **WHEN** an authenticated `admin` successfully creates, blocks, reactivates, or removes a user
- **THEN** the system MUST append an audit event
- **AND** the event MUST include actor identity and target user metadata
- **AND** the event MUST include action type and resulting state
