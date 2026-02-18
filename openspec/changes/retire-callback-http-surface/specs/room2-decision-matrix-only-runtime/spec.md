# Specification Delta

## ADDED Requirements

### Requirement: Runtime SHALL Expose Matrix-Only Decision Surface For Room-2

The runtime SHALL process Room-2 medical decisions exclusively through Matrix structured replies and MUST NOT expose HTTP decision endpoints for callback or widget submission.

#### Scenario: Operator inspects runtime API surface

- **WHEN** `bot-api` starts with valid runtime settings
- **THEN** `/callbacks/triage-decision` MUST NOT be registered
- **AND** `/widget/room2` and related widget submit/bootstrap paths MUST NOT be registered

### Requirement: Runtime Documentation SHALL Declare Matrix-Only Decision Path

Operational documentation SHALL declare Matrix structured replies as the single decision path for Room-2 and MUST NOT instruct callback or widget HTTP usage for medical decision execution.

#### Scenario: Operator follows decision-path runbook

- **WHEN** operators read runtime smoke or manual E2E guidance
- **THEN** decision execution instructions MUST reference only Matrix structured replies in Room-2
- **AND** no callback signing/tunnel steps for decision submission MUST be present
