# manual-e2e-readiness Specification

## Purpose
Define deterministic runtime smoke checks and tunnel validation steps used before manual end-to-end testing.
## Requirements
### Requirement: Deterministic Manual Runtime Validation
The project SHALL define deterministic smoke checks for validating live runtime readiness before full manual end-to-end testing using the single structured-reply Room-2 decision path.

#### Scenario: Pre-E2E smoke execution
- **WHEN** operators prepare for manual end-to-end testing
- **THEN** they MUST be able to verify service startup, database readiness, webhook endpoint reachability, and Room-2 structured reply readiness with documented deterministic checks

### Requirement: Cloudflare Tunnel Webhook Validation Path
The project SHALL provide an explicit validation path for tunneled webhook callbacks using existing HMAC authentication behavior.

#### Scenario: Tunneling webhook traffic
- **WHEN** operators expose `bot-api` via Cloudflare tunnel for callback testing
- **THEN** they MUST be able to send a signed callback request that reaches `/callbacks/triage-decision` and follows existing callback validation rules

### Requirement: Configurable External Dependency Test Modes
Runtime execution SHALL support explicit configuration modes that enable deterministic manual validation when external providers are unavailable.

#### Scenario: LLM provider unavailable in manual testing
- **WHEN** deterministic runtime mode is enabled for manual validation
- **THEN** LLM-dependent workflow steps MUST remain executable via configured deterministic adapters without altering triage business semantics

### Requirement: Manual E2E SHALL Validate Single Room-2 Structured Reply Decision Path
Manual runbooks SHALL validate the three-message Room-2 combo protocol and structured doctor replies as the only standard decision path.

#### Scenario: Operator validates doctor decision in mobile-capable client workflow
- **WHEN** operator follows the documented Room-2 decision runbook
- **THEN** they MUST verify message I + II + III publication, grouped relations for II/III to I, structured reply submission to message I, and expected state/job progression
- **AND** they MUST verify a Room-2 decision confirmation message is posted by the bot after successful decision handling
- **AND** they MUST verify positive acknowledgment reaction is optional and non-blocking for workflow progression

### Requirement: Manual E2E SHALL Validate Structured Reply Rejection Cases
Manual runbooks SHALL include negative checks for malformed template content and wrong reply-parent targeting.

#### Scenario: Malformed structured reply submitted
- **WHEN** a reply does not satisfy strict decision template rules
- **THEN** the decision MUST be rejected and no state/job mutation MUST occur

#### Scenario: Reply targets wrong parent event
- **WHEN** a structured reply is posted without referencing the active Room-2 case message
- **THEN** the decision MUST be rejected and no state/job mutation MUST occur

