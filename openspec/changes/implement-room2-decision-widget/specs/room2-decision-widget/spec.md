## ADDED Requirements

### Requirement: Room-2 SHALL Publish Widget Launch Context
The system SHALL publish Room-2 decision context with a deterministic widget launch contract that includes case identity and decision metadata needed by the widget UI.

#### Scenario: Worker posts Room-2 decision request
- **WHEN** a case reaches `R2_POST_WIDGET`
- **THEN** Room-2 output MUST include a widget launch URL/context bound to the case id
- **AND** the existing Room-2 ack message behavior MUST remain available for audit reactions

### Requirement: Widget Submission SHALL Preserve Decision Contract
The widget submission path SHALL map to the same decision contract already used by doctor callbacks (`case_id`, `doctor_user_id`, `decision`, `support_flag`, `reason`, optional metadata).

#### Scenario: Doctor submits ACCEPT in widget
- **WHEN** an authenticated admin user submits `decision=accept`
- **THEN** the system MUST persist doctor decision fields with existing semantics
- **AND** it MUST enqueue the same next-step job used today for accepted decisions

#### Scenario: Doctor submits DENY in widget
- **WHEN** an authenticated admin user submits `decision=deny`
- **THEN** `support_flag` MUST be normalized/validated as `none`
- **AND** it MUST enqueue the same next-step job used today for denied decisions

### Requirement: Widget Submission SHALL Enforce Role-Based Access
The widget submission path SHALL require authenticated role `admin` and reject unauthenticated or non-admin callers.

#### Scenario: Reader role attempts submission
- **WHEN** a valid token for role `reader` is used to submit a decision
- **THEN** the request MUST be rejected with authorization failure
- **AND** no case mutation or job enqueue MUST happen

### Requirement: Widget Path SHALL Remain Idempotent Under Races
Widget submissions SHALL preserve existing compare-and-set behavior for `WAIT_DOCTOR`, avoiding duplicate state transitions.

#### Scenario: Duplicate submit after first decision applied
- **WHEN** a second submission targets a case no longer in `WAIT_DOCTOR`
- **THEN** the system MUST return a non-applied outcome consistent with current behavior
- **AND** it MUST NOT enqueue duplicate next-step jobs
