# Specification Delta

## ADDED Requirements

### Requirement: Recent Denial Context SHALL Be Resolved Per Occurrence In A 7-Day Window

The system SHALL resolve recent denial context using `agency_record_number`, excluding the current case, and considering only denial outcomes whose denial timestamp is inside the last 7 days.

#### Scenario: Medical denial in lookback window

- **WHEN** at least one prior case for the same `agency_record_number` has `doctor_decision = deny` and `doctor_decided_at` within the last 7 days
- **THEN** the system MUST consider this case eligible as recent denial context
- **AND** the current case MUST be excluded from eligibility

#### Scenario: Scheduling denial in lookback window

- **WHEN** at least one prior case for the same `agency_record_number` has `appointment_status = denied` and `appointment_decided_at` within the last 7 days
- **THEN** the system MUST consider this case eligible as recent denial context
- **AND** it MUST classify this outcome as scheduling denial for context rendering

### Requirement: Recent Denial Selection SHALL Prefer The Latest Denial Event

When multiple denial outcomes exist in the 7-day window for the same occurrence, the system SHALL select the denial with the most recent denial timestamp for display.

#### Scenario: Multiple denials exist in the same window

- **WHEN** two or more eligible denials are found in the lookback period
- **THEN** the system MUST select the one with the greatest denial timestamp as the recent denial context
- **AND** the selected context MUST expose denial timestamp, denial class, and reason when available

### Requirement: Missing Denial Reason SHALL Use Deterministic Fallback

The system SHALL render deterministic fallback text when the selected recent denial has no stored justification.

#### Scenario: Selected denial has empty reason

- **WHEN** the selected recent denial has null, empty, or whitespace-only reason
- **THEN** the system MUST return fallback reason text `não informado`

### Requirement: Seven-Day Denial Counter SHALL Include Both Denial Classes

The system SHALL compute an optional denial counter for the 7-day window as the sum of medical denials and scheduling denials eligible for the same occurrence.

#### Scenario: Window contains mixed denial classes

- **WHEN** the lookback set includes both `doctor_decision = deny` and `appointment_status = denied`
- **THEN** the returned counter MUST include both classes in the same total
- **AND** this counter MUST be scoped to the same `agency_record_number` and 7-day window
