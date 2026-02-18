# case-thread-monitoring-dashboard Delta Specification

## MODIFIED Requirements

### Requirement: Dashboard SHALL List Cases For Operational Monitoring

The system SHALL provide a dashboard case list view for authenticated operational users, including at minimum case identifier, current status, latest update timestamp, and pagination/filter controls for daily monitoring.

#### Scenario: Reader lists cases processed in a period

- **WHEN** an authenticated `reader` requests the case list filtered by date range
- **THEN** the system MUST return paginated case entries ordered by most recent activity
- **AND** each entry MUST include case id, status, and latest activity timestamp

#### Scenario: Admin lists cases processed in a period

- **WHEN** an authenticated `admin` requests the case list filtered by date range
- **THEN** the system MUST return the same paginated monitoring list behavior available to `reader`

### Requirement: Dashboard SHALL Show Chronological Case Thread Across Rooms

The system SHALL provide a per-case timeline view that includes the chronological sequence of messages/events across Room-1, Room-2, and Room-3 with visual room identification for authenticated operational users.

#### Scenario: Reader opens a case timeline

- **WHEN** an authenticated `reader` opens the detail view for a case
- **THEN** the system MUST return events ordered chronologically for that case
- **AND** each event MUST include room identifier, timestamp, actor/sender, and event type

#### Scenario: Admin opens a case timeline

- **WHEN** an authenticated `admin` opens the detail view for a case
- **THEN** the system MUST return events ordered chronologically for that case
- **AND** each event MUST include room identifier, timestamp, actor/sender, and event type

## ADDED Requirements

### Requirement: Dashboard Pages SHALL Be Accessible Through Web Session Authentication

The system SHALL allow dashboard pages to be accessed through authenticated browser session flow without requiring manual Bearer header injection.

#### Scenario: Authenticated browser session opens dashboard

- **WHEN** a logged-in user with role `reader` or `admin` requests `GET /dashboard/cases`
- **THEN** the system MUST authorize the request from session state
- **AND** the system MUST render dashboard HTML without requiring explicit Authorization header
