# Specification Delta

## ADDED Requirements

### Requirement: Recent Denial Block SHALL Be Concise And Deterministic In Room-2 Summary

When rendered, the recent-denial context in message II SHALL preserve concise physician reading by using a short, deterministic structure.

#### Scenario: Recent denial block is rendered

- **WHEN** recent denial context is available during Room-2 summary rendering
- **THEN** the summary MUST render one concise block for recent denial context without full historical dumps
- **AND** the block MUST include at least: denial date/time, denial class, and reason
- **AND** the reason field MUST use deterministic fallback text when not available

#### Scenario: Multiple denials exist but summary remains concise

- **WHEN** more than one denial exists in the 7-day window
- **THEN** the summary MUST display details only for the most recent denial
- **AND** it MAY include only the total count of denials in the same window as additional context
