# Specification Delta

## ADDED Requirements

### Requirement: Room-2 Message II SHALL Include Recent Denial Context When Available

The system SHALL enrich Room-2 message II with an optional recent-denial context block when a denial for the same occurrence exists in the last 7 days.

#### Scenario: Recent denial exists for same occurrence

- **WHEN** a case is ready for Room-2 message II rendering and recent denial context is available for the same `agency_record_number`
- **THEN** message II MUST include a dedicated recent-denial block
- **AND** the block MUST include denial date/time, denial class, and denial reason
- **AND** the block MUST keep compatibility with the existing three-message Room-2 flow

#### Scenario: No recent denial exists in lookback window

- **WHEN** a case is ready for Room-2 message II rendering and no recent denial context is available
- **THEN** message II MUST omit the recent-denial block
- **AND** the message MUST preserve all currently required Room-2 decision content and sequencing
