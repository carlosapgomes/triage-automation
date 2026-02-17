## ADDED Requirements

### Requirement: Bot API SHALL Serve Room-2 Widget Runtime Surface
The runtime API process SHALL serve widget assets/endpoints required for Room-2 decision execution while preserving current webhook/login contracts.

#### Scenario: Bot API starts with widget enabled
- **WHEN** `bot-api` runtime starts with valid settings
- **THEN** existing `/callbacks/triage-decision` and `/auth/login` routes MUST remain behaviorally unchanged
- **AND** widget routes/assets MUST be available for doctor interaction

### Requirement: Widget Runtime SHALL Fail Fast on Missing Required Config
The runtime SHALL fail fast when required public widget URL/runtime settings are missing or invalid.

#### Scenario: Widget URL setting absent
- **WHEN** runtime configuration lacks required widget public URL data
- **THEN** process startup MUST fail with explicit configuration error
- **AND** no partially running widget surface MUST be exposed
