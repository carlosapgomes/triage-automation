## MODIFIED Requirements

### Requirement: Deterministic Manual Runtime Validation
The project SHALL define deterministic smoke checks for validating live runtime readiness, including Matrix-native Room-2 widget execution without secondary app login.

#### Scenario: Pre-E2E smoke execution
- **WHEN** operators prepare for manual end-to-end testing
- **THEN** they MUST be able to verify service startup, database readiness, webhook endpoint reachability, and Matrix-native widget reachability with documented deterministic checks

#### Scenario: Operator validates Matrix-native widget flow
- **WHEN** operator follows the documented manual widget sequence in Element client context
- **THEN** they MUST be able to open the Room-2 widget in-client, submit a decision without app email/password login, and observe expected state/job progression

## ADDED Requirements

### Requirement: Manual E2E SHALL Include Negative Matrix Identity Checks
The manual runbook SHALL define negative checks for missing or invalid Matrix widget identity context.

#### Scenario: Operator validates unauthorized Matrix-native widget submission
- **WHEN** widget bootstrap or submit is attempted without valid Matrix identity assertions
- **THEN** requests MUST be rejected
- **AND** case/job state MUST remain unchanged except expected auth/audit records
