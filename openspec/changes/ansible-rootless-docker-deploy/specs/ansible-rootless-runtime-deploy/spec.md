# Specification Delta

## ADDED Requirements

### Requirement: Ansible SHALL Provision Rootless Runtime Host Baseline

The deployment automation SHALL provision a compatible host baseline for runtime execution, including required system packages, dedicated service user, and rootless Docker prerequisites.

#### Scenario: Bootstrap host for first deployment

- **WHEN** operators run the bootstrap playbook against a new target host
- **THEN** the system MUST install required dependencies and configure the dedicated service user
- **AND** rootless Docker prerequisites MUST be configured successfully for that user context

### Requirement: Deploy Automation SHALL Run Application Services As Dedicated User

The deploy automation SHALL start and manage `bot-api`, `bot-matrix`, and `worker` under the dedicated service user context using rootless Docker runtime.

#### Scenario: Runtime services start after deploy

- **WHEN** operators execute the deploy playbook with valid configuration
- **THEN** all application services MUST start under the dedicated non-root service user
- **AND** runtime execution MUST NOT require root privileges for application process lifecycle

### Requirement: Deploy Playbooks SHALL Be Idempotent

The deploy automation SHALL be idempotent so repeated runs with unchanged inputs do not produce unintended configuration drift or duplicate resources.

#### Scenario: Re-run deploy with same version and variables

- **WHEN** operators execute the same deploy playbook twice with identical inputs
- **THEN** the second run MUST complete without destructive side effects
- **AND** resulting runtime state MUST remain equivalent to the first successful run

### Requirement: Deploy Automation SHALL Support Versioned Upgrade And Rollback

The deploy automation SHALL support explicit target version deployment and deterministic rollback to a previously known stable version.

#### Scenario: Rollback after failed upgrade validation

- **WHEN** an upgrade deployment fails post-deploy validation checks
- **THEN** operators MUST be able to run the rollback playbook targeting a previous version tag
- **AND** services MUST return to the prior stable runtime version
