# Specification Delta

## ADDED Requirements

### Requirement: Scheduler SHALL Enqueue Two Daily Room-4 Summary Jobs In America/Bahia

The system SHALL support scheduler-driven summary job creation at exactly 07:00 and 19:00 in timezone `America/Bahia`, where each execution covers the immediately preceding 12-hour window.

#### Scenario: Scheduler run at morning cutoff

- **WHEN** the scheduler executes at 07:00 `America/Bahia`
- **THEN** the system MUST enqueue one `post_room4_summary` job for window `[19:00 previous day, 07:00 current day)`
- **AND** the job payload MUST include deterministic `window_start` and `window_end` values

#### Scenario: Scheduler run at evening cutoff

- **WHEN** the scheduler executes at 19:00 `America/Bahia`
- **THEN** the system MUST enqueue one `post_room4_summary` job for window `[07:00 current day, 19:00 current day)`
- **AND** the job payload MUST include deterministic `window_start` and `window_end` values

### Requirement: Worker SHALL Publish Supervisor Summary To Room-4

The system SHALL process `post_room4_summary` jobs in worker runtime and publish one consolidated summary message to the configured Room-4 target.

#### Scenario: Processing queued summary job

- **WHEN** the worker claims a due `post_room4_summary` job
- **THEN** it MUST compute metrics for the exact window defined in job payload
- **AND** it MUST post one text summary message to configured Room-4

### Requirement: Summary Message SHALL Include Required Window And Metric Fields

The summary message SHALL include the reporting window and the minimum required metrics for supervisory operations.

#### Scenario: Rendering supervisor summary payload

- **WHEN** the worker renders the Room-4 summary message
- **THEN** the message MUST include local window reference in `America/Bahia`
- **AND** the message MUST include totals for `pacientes recebidos`, `relatórios processados`, `casos avaliados`, `aceitos`, and `recusados`

### Requirement: Final Outcome Metrics SHALL Reflect End-Of-Flow Semantics

Summary counting SHALL use event timestamps within the requested window and final-outcome semantics for acceptance/refusal.

#### Scenario: Counting accepted final outcomes

- **WHEN** final scheduling decisions in the window have `appointment_status = confirmed`
- **THEN** the system MUST count them as `aceitos`

#### Scenario: Counting refused final outcomes

- **WHEN** final outcomes in the window include medical denial or scheduling denial
- **THEN** the system MUST count both classes as `recusados`

### Requirement: Summary Dispatch SHALL Be Idempotent Per Room-4 Window

The system SHALL prevent duplicate Room-4 postings for the same `(room_id, window_start, window_end)` even when scheduler or operators re-execute the same window.

#### Scenario: Manual re-execution of already-sent window

- **WHEN** a `post_room4_summary` job is retriggered for a window that was already posted to Room-4
- **THEN** the system MUST NOT publish a second Matrix message for that same window
- **AND** it MUST preserve a dispatch record that indicates the prior successful send

### Requirement: Summary Dispatch SHALL Be Auditable

The system SHALL persist dispatch metadata for each attempted Room-4 summary window.

#### Scenario: Successful Room-4 summary send

- **WHEN** a Room-4 summary is posted successfully
- **THEN** the system MUST persist window identity, room id, send timestamp, and Matrix event id for that dispatch
