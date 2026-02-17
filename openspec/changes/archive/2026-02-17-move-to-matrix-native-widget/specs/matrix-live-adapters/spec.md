## MODIFIED Requirements

### Requirement: Matrix Adapter Port Implementation
The system SHALL provide concrete Matrix runtime adapters implementing required posting, replying, redaction, MXC download, and Matrix-native widget identity validation used by existing services.

#### Scenario: Service port call uses concrete adapter
- **WHEN** application services invoke Matrix send/reply/redact/download operations in runtime mode
- **THEN** calls MUST be executed through concrete infrastructure adapters rather than placeholders

#### Scenario: Widget identity validation uses concrete adapter boundary
- **WHEN** widget bootstrap or submit requires Matrix identity verification
- **THEN** identity assertions MUST be validated through concrete Matrix integration adapters at infrastructure boundary

## ADDED Requirements

### Requirement: Matrix Widget Identity Assertions SHALL Be Strictly Validated
Runtime adapter flow SHALL reject Matrix widget identity artifacts that fail issuer, audience, expiry, or signature expectations defined for deployment.

#### Scenario: Identity artifact validation fails
- **WHEN** Matrix widget identity artifact is expired, malformed, or audience-mismatched
- **THEN** widget request MUST be rejected deterministically
- **AND** no decision mutation MUST occur
