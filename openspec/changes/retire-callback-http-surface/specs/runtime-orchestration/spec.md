# Specification Delta

## MODIFIED Requirements

### Requirement: Bot API Runtime Serving

The system SHALL run `bot-api` as a long-lived ASGI process that supports runtime HTTP needs outside medical decision submission, while standard Room-2 doctor decisions are executed through Matrix structured replies.

#### Scenario: Bot API process starts in runtime mode

- **WHEN** the `bot-api` runtime entrypoint is launched with valid settings
- **THEN** the process MUST remain running and serve non-decision runtime routes required by the current product scope
- **AND** medical decisions MUST remain driven by Matrix structured reply flow

## REMOVED Requirements

### Requirement: Callback Endpoint SHALL Be Marked For Deprecation

**Reason**: callback compatibility path is removed directly before production provisioning, so deprecation-only wording is no longer valid.

**Migration**: use the Room-2 structured Matrix reply path as the only decision execution route.
