# Specification Delta

## ADDED Requirements

### Requirement: Operations Runbook SHALL Define End-To-End Deploy Procedure

The project SHALL provide an operations runbook that defines the complete procedure for initial install, upgrade, and rollback using the official Ansible playbooks.

#### Scenario: TI executes initial installation procedure

- **WHEN** hospital IT follows the documented initial installation runbook
- **THEN** the runbook MUST provide ordered commands and required preconditions for successful execution
- **AND** the documented flow MUST map directly to the maintained Ansible playbooks

### Requirement: Runbook SHALL Declare Mandatory Inventory And Variables

The operations documentation SHALL explicitly define required inventory structure, mandatory variables, and secret input expectations for remote deployment.

#### Scenario: Operator prepares environment configuration

- **WHEN** an operator fills inventory and variable files before deployment
- **THEN** the runbook MUST identify which fields are mandatory
- **AND** missing mandatory values MUST be detectable before runtime deployment starts

### Requirement: Runbook SHALL Provide Post-Deploy Validation Checklist

The operations runbook SHALL include deterministic post-deploy checks for service health and runtime readiness.

#### Scenario: Operator validates deployment outcome

- **WHEN** deployment playbook execution completes
- **THEN** the runbook MUST provide objective verification steps for process/runtime health
- **AND** expected success criteria MUST be clearly defined for first-level support

### Requirement: Runbook SHALL Include First-Level Troubleshooting Guidance

The operations runbook SHALL include troubleshooting guidance for common deployment and startup failures, including escalation boundaries.

#### Scenario: Operator encounters deployment failure

- **WHEN** a known failure condition occurs during bootstrap or deploy
- **THEN** the runbook MUST provide immediate corrective actions for first-level support
- **AND** the runbook MUST indicate when escalation to development is required
