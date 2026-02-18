# Specification Delta

## ADDED Requirements

### Requirement: Dashboard SHALL List Cases For Operational Monitoring

The system SHALL provide a dashboard case list view for operational users, including at minimum case identifier, current status, latest update timestamp, and pagination/filter controls for daily monitoring.

#### Scenario: Reader lists cases processed in a period

- **WHEN** an authenticated `reader` requests the case list filtered by date range
- **THEN** the system MUST return paginated case entries ordered by most recent activity
- **AND** each entry MUST include case id, status, and latest activity timestamp

### Requirement: Dashboard SHALL Show Chronological Case Thread Across Rooms

The system SHALL provide a per-case timeline view that includes the chronological sequence of messages/events across Room-1, Room-2, and Room-3 with visual room identification.

#### Scenario: Reader opens a case timeline

- **WHEN** an authenticated `reader` opens the detail view for a case
- **THEN** the system MUST return events ordered chronologically for that case
- **AND** each event MUST include room identifier, timestamp, actor/sender, and event type

### Requirement: Timeline SHALL Include ACKs And Human Replies

The timeline view SHALL include bot acknowledgments and user replies as first-class events to preserve end-to-end auditability.

#### Scenario: Case contains ACK and human response events

- **WHEN** a case includes acknowledgments and human replies in its flow
- **THEN** those events MUST appear in the same timeline sequence
- **AND** they MUST remain distinguishable by event type and actor metadata

### Requirement: Dashboard UI SHALL Use Server-Rendered Boring Stack

The dashboard UI SHALL be implemented as server-rendered HTML using `FastAPI` + `Jinja2`, with styling based on `Bootstrap 5.3` and partial navigation/interactions based on `Unpoly`, avoiding mandatory frontend build steps.

#### Scenario: Operator accesses dashboard without frontend build artifacts

- **WHEN** runtime services are started using standard Python entrypoints
- **THEN** dashboard pages MUST be served directly by `bot-api` templates/static assets
- **AND** no Node.js/npm bundling pipeline MUST be required for normal dashboard operation
