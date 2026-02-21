# manual-e2e-readiness Specification

## MODIFIED Requirements

### Requirement: Manual E2E Runbook SHALL Define Operational Validation Flow

The project SHALL keep one human-readable manual E2E runbook that is actionable for operations and support teams before production usage.

#### Scenario: Operator performs manual E2E checks

- **WHEN** a team member follows the manual runbook
- **THEN** the runbook MUST cover startup prerequisites, execution flow, and expected outputs
- **AND** each step MUST be concrete enough to execute without code changes
- **AND** language navigation MUST provide Portuguese default and English mirror to support mixed-language teams

#### Scenario: Role, prompt, and user governance checks are reviewed

- **WHEN** manual validation reaches authorization, prompt-management, and user-management checks
- **THEN** the runbook MUST include role matrix expectations (`reader` vs `admin`)
- **AND** the runbook MUST include prompt activation/create verification points consistent with current admin surface
- **AND** the runbook MUST include user-management verification points for create, block, reactivate, and remove actions with expected authorization outcomes
- **AND** the runbook MUST include expected audit-event verification points for user-management actions
