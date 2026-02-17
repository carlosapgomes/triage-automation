## ADDED Requirements

### Requirement: Room-2 SHALL Launch Matrix-Native Widget Context
The system SHALL publish Room-2 output with Matrix-native widget metadata so Element clients render the decision widget in-client for the target case.

#### Scenario: Case reaches Room-2 decision stage
- **WHEN** a case is posted for doctor review
- **THEN** Room-2 output MUST include deterministic widget launch context bound to the case id
- **AND** the launch context MUST target Matrix-native widget rendering semantics

### Requirement: Widget Submit SHALL Derive Doctor Identity From Matrix Context
The widget submit path SHALL derive the acting doctor identity from validated Matrix widget/client context, not from user-entered identity fields.

#### Scenario: Doctor submits decision in widget
- **WHEN** a decision is submitted from a valid Matrix-native widget session
- **THEN** the backend MUST resolve `doctor_user_id` from server-validated Matrix identity context
- **AND** any conflicting user-entered identity value MUST be ignored or rejected

### Requirement: Matrix-Native Widget Submit SHALL Preserve Existing Decision Semantics
Matrix-native widget submission SHALL preserve the same business decision contract and state/job outcomes already defined for doctor decisions.

#### Scenario: Doctor submits ACCEPT
- **WHEN** a validated widget actor submits `decision=accept`
- **THEN** the case MUST transition with existing accepted semantics
- **AND** the same downstream accepted job path MUST be enqueued

#### Scenario: Doctor submits DENY
- **WHEN** a validated widget actor submits `decision=deny`
- **THEN** `support_flag` MUST be constrained to existing deny semantics (`none`)
- **AND** the same downstream denied job path MUST be enqueued

### Requirement: Widget Flow SHALL Not Require Secondary App Login
Doctor widget operation SHALL NOT require the separate application email/password login flow.

#### Scenario: Widget flow executes in Element client
- **WHEN** doctor opens and uses the Room-2 widget from Matrix client context
- **THEN** bootstrap and submit MUST succeed without obtaining an app token from `/auth/login`

### Requirement: Invalid Matrix Widget Identity Context SHALL Be Rejected
Widget requests without valid Matrix-native identity assertions SHALL be rejected with no decision mutation.

#### Scenario: Missing or invalid widget identity context
- **WHEN** bootstrap or submit is attempted without valid Matrix identity proof
- **THEN** the request MUST be rejected with authorization failure
- **AND** case state and queued jobs MUST remain unchanged
