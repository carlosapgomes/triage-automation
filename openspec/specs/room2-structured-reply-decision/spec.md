# room2-structured-reply-decision Specification

## Purpose
TBD - created by archiving change room2-single-path-matrix-reply. Update Purpose after archive.
## Requirements
### Requirement: Room-2 SHALL Publish Three-Message Decision Combo
The system SHALL publish a deterministic three-message combo in Room-2 for each case requiring doctor decision.

#### Scenario: Case enters Room-2 doctor decision stage
- **WHEN** a case is ready for doctor decision in Room-2
- **THEN** the bot MUST post message I with the original PDF report
- **AND** the bot MUST post message II with extracted data + summary + recommendation
- **AND** the bot MUST post message III with strict reply template and instructions to reply to message I

### Requirement: Room-2 Combo SHALL Be Grouped By Flat Reply Relations
The bot SHALL preserve case context grouping by posting messages II and III as replies to message I, without deep nested reply chains.

#### Scenario: Bot posts message combo for a case
- **WHEN** messages I, II, and III are published for a Room-2 case
- **THEN** messages II and III MUST include reply relation metadata targeting message I
- **AND** message III MUST NOT rely on reply-of-reply nesting for required context

### Requirement: Decision Replies SHALL Be Strictly Structured
The system SHALL accept only strict structured decision replies and SHALL NOT infer decisions from free-form text.

#### Scenario: Doctor submits decision in valid template
- **WHEN** a doctor reply contains a syntactically valid decision template
- **THEN** the system MUST parse structured fields deterministically
- **AND** the parsed decision MUST be validated against existing contract rules (`accept|deny`, `support_flag`, `reason` semantics)

#### Scenario: Doctor submits free-form text
- **WHEN** a doctor reply does not match the strict template
- **THEN** the system MUST reject the submission with explicit feedback
- **AND** no decision mutation or job enqueue MUST occur

### Requirement: Decision Reply SHALL Reference Active Room-2 Root Case Message
A decision reply SHALL be accepted only when it is a Matrix reply to the active Room-2 root case message (message I).

#### Scenario: Reply targets active case message
- **WHEN** the decision event is a valid `m.in_reply_to` reply to the active Room-2 root case message
- **THEN** the system MUST treat the reply as eligible for decision parsing and validation

#### Scenario: Reply targets wrong or missing parent
- **WHEN** the decision event is not a reply to the active Room-2 root case message
- **THEN** the system MUST reject the submission
- **AND** no decision mutation or job enqueue MUST occur

### Requirement: Doctor Identity SHALL Be Derived From Matrix Sender
The system SHALL derive `doctor_user_id` from Matrix event sender identity, not from user-entered fields.

#### Scenario: Structured reply is accepted
- **WHEN** a valid decision reply is processed
- **THEN** `doctor_user_id` MUST be set from the Matrix sender on the reply event
- **AND** any user-entered identity value MUST be ignored or rejected

### Requirement: Room-2 Membership SHALL Be Authorization Boundary
Only users who are able to post in Room-2 SHALL be authorized to submit doctor decisions through this path.

#### Scenario: Room-2 member submits decision
- **WHEN** a Room-2 member submits a valid structured reply
- **THEN** the system MUST authorize and process the decision subject to state validation

#### Scenario: Non-authorized actor cannot submit decision
- **WHEN** a decision-like event is produced by an actor not authorized by Room-2 membership policy
- **THEN** the system MUST reject processing
- **AND** no decision mutation or job enqueue MUST occur

### Requirement: Structured Reply Path SHALL Preserve Existing Decision Semantics
The structured reply path SHALL preserve existing state-machine gating, idempotency, and downstream job outcomes used by the current decision service.

#### Scenario: ACCEPT decision is applied
- **WHEN** a valid structured reply submits `decision=accept`
- **THEN** the case MUST follow existing accepted-state transition behavior
- **AND** the same accepted downstream job path MUST be enqueued

#### Scenario: DENY decision is applied
- **WHEN** a valid structured reply submits `decision=deny`
- **THEN** `support_flag` MUST satisfy existing deny constraints (`none`)
- **AND** the same denied downstream job path MUST be enqueued

#### Scenario: Duplicate or race reply after decision already applied
- **WHEN** a subsequent decision reply is received after case leaves `WAIT_DOCTOR`
- **THEN** the system MUST return a non-applied outcome consistent with existing behavior
- **AND** it MUST NOT enqueue duplicate downstream jobs

### Requirement: Bot SHALL Emit Decision Result Feedback In Room-2
The bot SHALL publish deterministic success/error feedback in Room-2 after processing a structured decision reply.

#### Scenario: Decision accepted and applied
- **WHEN** structured decision processing succeeds
- **THEN** the bot MUST send a Room-2 confirmation message describing successful processing
- **AND** the confirmation message MUST be persisted as a reaction-ack target for Room-2 acknowledgment tracking

#### Scenario: Decision rejected by validation or state
- **WHEN** structured decision processing fails due to format, authorization, or state constraints
- **THEN** the bot MUST send a Room-2 error message with actionable correction guidance

### Requirement: Room-2 Final Acknowledgment SHALL Be Positive-Only And Non-Blocking
The system SHALL treat positive reaction on the Room-2 decision confirmation message as an optional doctor acknowledgment audit signal and SHALL NOT gate decision progression on reaction.

#### Scenario: Positive acknowledgment reaction received
- **WHEN** a doctor reacts with a supported positive key to the Room-2 decision confirmation message
- **THEN** the system MUST record acknowledgment audit metadata for that case
- **AND** no additional state transition or job enqueue MUST be required for already-applied decision progression

#### Scenario: Non-positive or missing acknowledgment reaction
- **WHEN** reaction key is not a supported positive acknowledgment key, or no reaction is sent
- **THEN** the system MUST continue normal workflow without blocking
- **AND** no rollback or re-opening of decision state MUST occur

