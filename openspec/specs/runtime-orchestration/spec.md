# runtime-orchestration Specification

## Purpose

Define runtime process startup requirements and parity constraints for local and compose execution.

## Requirements

### Requirement: Bot API Runtime Serving

The system SHALL run `bot-api` as a long-lived ASGI process that supports runtime HTTP needs outside medical decision submission, while standard Room-2 doctor decisions are executed through Matrix structured replies.

#### Scenario: Bot API process starts in runtime mode

- **WHEN** the `bot-api` runtime entrypoint is launched with valid settings
- **THEN** the process MUST remain running and serve non-decision runtime routes required by the current product scope
- **AND** medical decisions MUST remain driven by Matrix structured reply flow

### Requirement: Compose and UV Runtime Parity

The system SHALL provide behaviorally equivalent runtime startup paths for local `uv` execution and Docker Compose execution, and production runtime commands SHALL remain compatible with Ansible-managed deployment automation.

#### Scenario: Runtime command parity

- **WHEN** operators launch services via `uv` entrypoints or via Compose commands
- **THEN** both paths MUST execute the same application startup composition and dependency wiring

#### Scenario: Production deploy automation executes runtime commands

- **WHEN** operators run official Ansible deployment playbooks for production
- **THEN** deployed runtime commands MUST be compatible with the same supported startup composition
- **AND** production automation MUST NOT depend on an ad-hoc runtime path outside declared supported commands

### Requirement: No Workflow Redesign During Runtime Wiring

Runtime orchestration changes SHALL NOT alter authoritative triage workflow behavior.

#### Scenario: Runtime orchestration code is introduced

- **WHEN** runtime-serving and startup wiring are implemented
- **THEN** state-machine semantics, decision contract, and cleanup trigger behavior MUST remain unchanged

### Requirement: Matrix Structured Reply SHALL Be The Single Standard Room-2 Decision Path

Runtime behavior SHALL treat structured Matrix replies in Room-2 as the canonical doctor decision path for normal operations.

#### Scenario: Case awaiting doctor decision in Room-2

- **WHEN** a case is in `WAIT_DOCTOR`
- **THEN** decision processing MUST be driven by structured Matrix replies to Room-2 case context messages
- **AND** no optional parallel standard decision path MUST be required
