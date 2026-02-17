## ADDED Requirements

### Requirement: Manual E2E SHALL Include Widget Decision Path
The manual runtime runbook SHALL include deterministic validation for Room-2 widget open, authenticate, submit, and workflow progression.

#### Scenario: Operator validates widget flow in local runtime
- **WHEN** operator follows the documented manual test sequence
- **THEN** they MUST be able to open the widget from Room-2 context, authenticate, submit decision, and observe expected state/job transitions

### Requirement: Manual E2E SHALL Include Negative Widget Auth Checks
The manual runbook SHALL define negative checks for unauthenticated and non-admin widget submissions.

#### Scenario: Operator validates unauthorized widget submission
- **WHEN** a widget submit request is attempted without valid admin authentication
- **THEN** submission MUST be rejected
- **AND** case/audit state MUST remain unchanged except expected auth/audit records
