# Specification Delta

## ADDED Requirements

### Requirement: Bot Matrix Runtime SHALL Auto-Accept Invites For Configured Rooms Only

The system SHALL inspect Matrix `/sync` invite payloads and automatically join a room only when the invited `room_id` matches one of `ROOM1_ID`, `ROOM2_ID`, `ROOM3_ID`, or `ROOM4_ID`.

#### Scenario: Invite received for configured room id

- **WHEN** the bot receives an invite for a room whose id matches one configured runtime room id
- **THEN** it MUST call Matrix join for that room automatically
- **AND** it MUST emit an `INFO` log including the `room_id`

#### Scenario: Invite received for non-configured room id

- **WHEN** the bot receives an invite for a room id outside the configured runtime room ids
- **THEN** it MUST NOT call Matrix join for that room
- **AND** it MUST continue runtime processing without mutating case workflow state

### Requirement: Invite Auto-Accept Failures SHALL Be Visible And Retried On Future Polls

The system SHALL not fail silently when auto-join fails for an allowed room invite.

#### Scenario: Join request fails for allowed invite

- **WHEN** join execution for an allowed invited room fails due to transport or HTTP error
- **THEN** the bot MUST emit a `WARNING` log including the `room_id` and failure reason
- **AND** it MUST continue polling subsequent sync cycles

#### Scenario: Allowed invite remains pending after prior failure

- **WHEN** a subsequent `/sync` still contains the pending invite for the same allowed room
- **THEN** the bot MUST attempt join again automatically

### Requirement: Bot SHALL Rejoin Allowed Room On New Invite After Leave Or Kick

The auto-accept behavior SHALL remain valid for new invites to allowed rooms even if the bot had previously left or been removed.

#### Scenario: Bot removed and invited again to configured room

- **WHEN** the bot receives a new invite for an allowed room after previously not being joined to that room
- **THEN** it MUST attempt automatic join again using the same allowlist rule
