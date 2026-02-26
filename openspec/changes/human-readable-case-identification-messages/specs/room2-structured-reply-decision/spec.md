# Specification Delta

## MODIFIED Requirements

### Requirement: Room-2 SHALL Publish Three-Message Decision Combo

The system SHALL publish a deterministic three-message combo in Room-2 for each case requiring doctor decision, adding human-readable identification context to doctor-facing text messages.

#### Scenario: Case enters Room-2 doctor decision stage

- **WHEN** a case is ready for doctor decision in Room-2
- **THEN** the bot MUST post message I with the original PDF report
- **AND** the bot MUST post message II with extracted data + summary + recommendation, including `no. ocorrência` and `paciente` near the top
- **AND** the bot MUST post message III with strict reply template and instructions to reply to message I, including `no. ocorrência` and `paciente`

### Requirement: Bot SHALL Emit Decision Result Feedback In Room-2

The bot SHALL publish deterministic success/error feedback in Room-2 after processing a structured decision reply, with human-readable identification context and UUID preservation only where structurally required.

#### Scenario: Decision accepted and applied

- **WHEN** structured decision processing succeeds
- **THEN** the bot MUST send a Room-2 confirmation message describing successful processing and including `no. ocorrência` and `paciente`
- **AND** the confirmation message MUST be persisted as a reaction-ack target for Room-2 acknowledgment tracking

#### Scenario: Decision rejected by validation or state

- **WHEN** structured decision processing fails due to format, authorization, or state constraints
- **THEN** the bot MUST send a Room-2 error message with actionable correction guidance and including `no. ocorrência` and `paciente`
- **AND** when a strict correction model is shown, it MUST preserve the UUID case line required by parser validation
