## Why

The current Room-2 decision implementation depends on widget/client capabilities that are inconsistent across Matrix clients, especially mobile, creating operational risk and fragmented user behavior. We need a single deterministic decision path that works in all clients now and is easy to audit end-to-end.

## What Changes

- Establish one canonical Room-2 decision path based on structured Matrix replies (no optional parallel decision UX).
- Bot posts a deterministic three-message Room-2 combo per case:
  - Message I: original PDF report
  - Message II: extracted data + summary + recommendation
  - Message III: strict reply template + instructions to reply to Message I
- Doctor decision is accepted only when it is a valid structured reply to Message I.
- Parse structured content only (no NLP/free-text interpretation).
- Resolve `doctor_user_id` from Matrix event sender, never from typed payload fields.
- Enforce deterministic message grouping by binding bot messages II and III as replies to message I (flat relation, no deep nested reply chain).
- Reuse existing decision business path (`HandleDoctorDecisionService`) so transitions/jobs/idempotency remain unchanged.
- Use Room-2 membership as authorization boundary for who can decide.
- Keep `/callbacks/triage-decision` available only as emergency compatibility path and mark it for near-term deprecation.
- **BREAKING**: widget-based Room-2 decision UX and app-login-based decision auth are removed from the standard flow.

## Capabilities

### New Capabilities
- `room2-structured-reply-decision`: deterministic Room-2 doctor decision workflow driven by strict Matrix reply templates and sender-derived identity.

### Modified Capabilities
- `matrix-live-adapters`: add/modify requirements for parsing and validating Room-2 structured reply decisions as first-class runtime events.
- `runtime-orchestration`: change runtime decision surface to a single Matrix-reply path and constrain callback endpoint to emergency compatibility usage.
- `manual-e2e-readiness`: redefine manual validation steps around structured Matrix replies across diverse clients, including mobile-first behavior.

## Impact

- Affected code/systems:
  - `apps/bot_matrix/main.py`
  - Matrix event parsing/routing adapters in `src/triage_automation/infrastructure/matrix/*`
  - Room-2 message templates and posting services
  - decision submit transport path in HTTP/widget adapters (removal/deprecation scope)
  - manual/runtime docs and runbooks
- API/runtime surface:
  - canonical decision path moves to Matrix reply events
  - callback endpoint remains only as emergency compatibility path and marked for deprecation
- Operational impact:
  - no requirement for additional human operator in normal flow
  - improved actor traceability by binding decisions to Matrix sender identity in Room-2
  - improved case context continuity by grouping each case in a single Room-2 message cluster
