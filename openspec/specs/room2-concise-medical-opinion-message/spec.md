# room2-concise-medical-opinion-message Specification

## Purpose

TBD - created by archiving change room2-concise-medical-opinion-message. Update Purpose after archive.

## Requirements

### Requirement: Room-2 Clinical Opinion Message SHALL Be Concise And Decision-Oriented

The system SHALL publish a concise medical-opinion summary in Room-2 focused on clinical context, decision support, and actionable conduct, without dumping full flattened structured payloads.

#### Scenario: Room-2 summary is generated for doctor review

- **WHEN** message II (`room2_case_summary`) is rendered for a case awaiting doctor decision
- **THEN** the message MUST prioritize concise, decision-oriented content
- **AND** the message MUST NOT include full flattened listings equivalent to complete LLM1/LLM2 structured payloads

### Requirement: Room-2 Summary SHALL Include Mandatory Seven-Block Layout

The system SHALL render the Room-2 summary with a fixed seven-block layout to standardize medical reading flow.

#### Scenario: Summary message is posted in Room-2

- **WHEN** the bot posts message II for a case in Room-2
- **THEN** the message MUST include the following blocks in order:
- **AND** `Resumo clínico`
- **AND** `Achados críticos`
- **AND** `Pendências críticas`
- **AND** `Decisão sugerida`
- **AND** `Suporte recomendado`
- **AND** `Motivo objetivo`
- **AND** `Conduta sugerida`

### Requirement: Room-2 Summary SHALL Preserve Fast Clinical Context

The summary SHALL preserve rapid context for doctors who did not read the full report by enforcing a short narrative clinical synopsis.

#### Scenario: Doctor reads Room-2 summary without opening full PDF

- **WHEN** a doctor relies on message II as first clinical contact with the case
- **THEN** `Resumo clínico` MUST be present with 2 to 4 lines
- **AND** the synopsis MUST capture the patient clinical situation and immediate triage context

### Requirement: Decision, Support, And Objective Reason SHALL Be Explicit And Coherent

The message SHALL explicitly show final reconciled suggestion fields and a short objective reason aligned with that final suggestion.

#### Scenario: Suggested action is reconciled before Room-2 post

- **WHEN** `suggested_action_json` is already policy-reconciled and consumed for summary rendering
- **THEN** `Decisão sugerida` MUST reflect the final reconciled suggestion value
- **AND** `Suporte recomendado` MUST reflect the final reconciled support value
- **AND** `Motivo objetivo` MUST be presented in 1 to 2 lines and stay coherent with displayed decision and support

### Requirement: Conduta Sugerida SHALL Be Bounded And Actionable

The system SHALL bound conduct guidance length and preserve operational actionability.

#### Scenario: Conduta block is rendered

- **WHEN** `Conduta sugerida` is generated for Room-2 summary
- **THEN** it MUST include at least 2 actionable bullets
- **AND** it MUST target 3 bullets by default when enough actionable items are available
- **AND** it MUST NOT exceed 4 bullets

### Requirement: Emergent Instability Cases SHALL Include Priority Phrase

The summary SHALL include explicit emergent-priority language for bleeding cases with documented hemodynamic instability.

#### Scenario: Bleeding plus hemodynamic instability is present

- **WHEN** case context indicates active bleeding with documented hemodynamic instability
- **THEN** `Motivo objetivo` or `Conduta sugerida` MUST include explicit emergent-priority phrasing
- **AND** this phrasing MUST indicate that stabilization and urgent pathway should not be delayed by non-critical missing fields
