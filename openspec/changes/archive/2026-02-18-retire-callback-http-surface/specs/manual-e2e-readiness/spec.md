# Specification Delta

## MODIFIED Requirements

### Requirement: Deterministic Manual Runtime Validation

The project SHALL define deterministic smoke checks for validating live runtime readiness before full manual end-to-end testing using the single structured-reply Room-2 decision path.

#### Scenario: Pre-E2E smoke execution

- **WHEN** operators prepare for manual end-to-end testing
- **THEN** they MUST be able to verify service startup, database readiness, and Room-2 structured reply readiness with documented deterministic checks

## REMOVED Requirements

### Requirement: Cloudflare Tunnel Webhook Validation Path

**Reason**: callback webhook path is removed from runtime and no longer exists as an operational validation surface.

**Migration**: validate external reachability and decision execution through Matrix client flows and Room-2 structured replies.
