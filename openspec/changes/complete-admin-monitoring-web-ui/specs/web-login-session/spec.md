# web-login-session Specification

## ADDED Requirements

### Requirement: System SHALL Provide Browser Login Entry Point

The system SHALL expose a browser-accessible landing/login flow so operational users can authenticate without manually sending API headers.

#### Scenario: Anonymous user opens root path

- **WHEN** an unauthenticated user requests `GET /`
- **THEN** the system MUST redirect to `GET /login`

#### Scenario: Anonymous user opens login page

- **WHEN** an unauthenticated user requests `GET /login`
- **THEN** the system MUST render an HTML login form with `email` and `password` fields

### Requirement: System SHALL Create Web Session On Successful Login

The system SHALL authenticate credentials and set an HTTP-only session cookie backed by persisted opaque token state.

#### Scenario: Valid credentials submitted in login form

- **WHEN** a user submits valid credentials to `POST /login`
- **THEN** the system MUST authenticate the user
- **AND** the system MUST set an `HttpOnly` session cookie
- **AND** the system MUST redirect to `/dashboard/cases`

#### Scenario: Invalid credentials submitted in login form

- **WHEN** a user submits invalid credentials to `POST /login`
- **THEN** the system MUST return login error feedback in HTML
- **AND** the system MUST NOT issue a valid session cookie

### Requirement: System SHALL Destroy Web Session On Logout

The system SHALL provide explicit logout that invalidates browser session access.

#### Scenario: Authenticated user logs out

- **WHEN** an authenticated user submits `POST /logout`
- **THEN** the system MUST clear the session cookie in the response
- **AND** the system MUST redirect to `GET /login`
