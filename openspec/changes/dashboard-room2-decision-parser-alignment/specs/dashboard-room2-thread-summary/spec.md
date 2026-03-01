# Specification Delta

## MODIFIED Requirements

### Requirement: Dashboard Room-2 Thread Summary SHALL Use Canonical Decision Parsing

The system SHALL derive the Room-2 decision label shown in dashboard thread summary from the same strict parser used in Room-2 reply processing.

#### Scenario: Reply message with quoted previous template and final deny decision

- **GIVEN** a `room2_doctor_reply` message body containing a quoted previous block with `decisao: aceitar`
- **AND** a final unquoted block with `decisao: negar`
- **WHEN** the dashboard renders case detail thread summary
- **THEN** the Room-2 summary MUST display `Resposta médica: DECISÃO = NEGAR`

#### Scenario: Non-parseable legacy reply content

- **GIVEN** a `room2_doctor_reply` message body that cannot be parsed by the strict decision parser
- **WHEN** the dashboard renders case detail thread summary
- **THEN** the Room-2 summary MUST display `Resposta médica: DECISÃO = INDEFINIDA`
