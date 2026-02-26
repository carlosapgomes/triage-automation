# Specification Delta

## ADDED Requirements

### Requirement: Room Messages SHALL Prioritize Human-Readable Case Identification

The system SHALL render human-readable case identification at the top of bot-driven messages in Room-1, Room-2, and Room-3 using the lines `no. ocorrência` and `paciente`.

#### Scenario: Bot publishes operational message in monitored rooms

- **WHEN** the bot sends a case-related message intended for operational reading in Room-1, Room-2, or Room-3
- **THEN** the message MUST include, near the top, `no. ocorrência: <valor>` and `paciente: <valor>`

### Requirement: Missing Human Identification Data SHALL Use Deterministic Fallback

The system SHALL use `não detectado` whenever `agency_record_number` or `patient_name` is unavailable for message rendering.

#### Scenario: Occurrence and/or patient data are missing

- **WHEN** the bot renders a message and at least one of `agency_record_number` or `patient_name` is absent, empty, or unresolved
- **THEN** the corresponding identification line MUST render with value `não detectado`

### Requirement: UUID Visibility SHALL Follow Message Contract Criticality

The system SHALL replace UUID as primary visible identifier in non-structural messages and SHALL preserve UUID in structural templates where parser validation depends on the case line.

#### Scenario: Non-structural informational message

- **WHEN** the bot renders a message that does not require user copy/paste contract parsing
- **THEN** the message MUST prioritize `no. ocorrência` and `paciente` as case identification
- **AND** the message MUST NOT require UUID as the only visible case identifier

#### Scenario: Structural template or strict re-prompt message

- **WHEN** the bot renders a strict template or correction prompt whose parser contract depends on case binding
- **THEN** the message MUST keep the UUID case line used by parser validation
- **AND** the message MUST also include `no. ocorrência` and `paciente`

### Requirement: Room-2 PDF Attachment Filename SHALL Include Occurrence and UUID

The system SHALL generate Room-2 original report attachment filename using occurrence-aware naming while preserving UUID.

#### Scenario: Occurrence number is available

- **WHEN** the bot prepares Room-2 original report attachment filename and `agency_record_number` is present
- **THEN** filename MUST follow `ocorrencia-<agency_record_number>-caso-<uuid>-relatorio-original.pdf`

#### Scenario: Occurrence number is unavailable

- **WHEN** the bot prepares Room-2 original report attachment filename and `agency_record_number` is unavailable
- **THEN** filename MUST follow `ocorrencia-indisponivel-caso-<uuid>-relatorio-original.pdf`
