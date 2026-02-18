# Specification Delta

## MODIFIED Requirements

### Requirement: Compose and UV Runtime Parity

The system SHALL provide behaviorally equivalent runtime startup paths for local `uv` execution and Docker Compose execution, and production runtime commands SHALL remain compatible with Ansible-managed deployment automation.

#### Scenario: Runtime command parity

- **WHEN** operators launch services via `uv` entrypoints or via Compose commands
- **THEN** both paths MUST execute the same application startup composition and dependency wiring

#### Scenario: Production deploy automation executes runtime commands

- **WHEN** operators run official Ansible deployment playbooks for production
- **THEN** deployed runtime commands MUST be compatible with the same supported startup composition
- **AND** production automation MUST NOT depend on an ad-hoc runtime path outside declared supported commands
