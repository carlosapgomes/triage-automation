# Context

Room-2 doctor decision currently depends on widget/client features that vary by Matrix client and platform, creating inconsistent execution risk for production usage, especially on mobile. The required direction is a single deterministic path with no optional branching in normal operation.

The new canonical flow is message-driven in Matrix itself:

1. Bot posts message I with the original PDF report.
2. Bot posts message II with extracted data + summary + recommendation, as a reply to message I.
3. Bot posts message III with strict instructions + required reply template, as a reply to message I.
4. Doctor replies to message I using the template from message III.
5. System parses structured fields only.
6. Doctor identity comes from Matrix sender (`event.sender`).
7. Existing decision service is called with unchanged business semantics.
8. Bot posts a decision confirmation message in Room-2 as a reply to the doctor decision reply when possible.
9. Doctor may react positively to the bot confirmation message as an audit-only acknowledgment that the process ended.

Message relation strategy is intentionally flat:
- message I is the root case context event
- bot messages II and III are replies to message I
- doctor decision reply is also a reply to message I

This avoids deep nested reply chains that can degrade UX across clients while preserving deterministic parent binding for parsing.

Constraints:

- Keep business/state-machine logic unchanged.
- No free-text NLP decision parsing.
- No optional parallel decision UX in standard flow.
- Room-2 membership is the authorization boundary.
- Callback endpoint remains emergency-only and marked for deprecation.
- Decision state transition is never gated by reaction acknowledgment.

## Goals / Non-Goals

**Goals:**

- Enforce one canonical Room-2 decision path across all clients.
- Ensure deterministic parsing/validation of doctor decisions.
- Improve actor traceability by binding decision actor to Matrix sender identity.
- Preserve existing decision outcomes, idempotency, and downstream job behavior.

**Non-Goals:**

- Supporting widget as a standard decision path.
- Introducing additional operator-mediated decision submission.
- Redesigning triage business rules or case-state transitions.
- Building admin/monitoring features tied to users table.

## Decisions

### Decision 1: Single standard decision channel is structured Matrix reply

- Choice: only structured replies to Room-2 message I are accepted in normal flow.
- Rationale: uniform behavior across diverse clients and easiest operational reliability.
- Alternative considered: keep widget + reply dual-path.
  - Rejected because it increases moving parts and state divergence risk.

### Decision 2: Three-message combo protocol in Room-2 is mandatory

- Choice: bot always emits message I (original report), message II (extracted summary/recommendation), and message III (template/instructions).
- Rationale: deterministic UX and explicit machine-parseable contract for doctors.
- Alternative considered: one free-form message with implicit rules.
  - Rejected because parsing reliability and user consistency degrade.

### Decision 2a: Use flat reply grouping to root message I

- Choice: bot messages II/III and doctor decision are all replies to message I (no reply-of-reply nesting).
- Rationale: keeps per-case context grouped while reducing client UX variance and confusion from deep chains.
- Alternative considered: nested reply chain (III replying to II, doctor replying to III).
  - Rejected because deep chains can be harder to follow across client implementations.

### Decision 3: Author identity is always Matrix event sender

- Choice: `doctor_user_id` is sourced from reply event sender; typed identity fields are ignored.
- Rationale: prevents spoofing and ensures audit chain aligns with Matrix identity.
- Alternative considered: accept user-provided doctor identity in payload.
  - Rejected due to trust and audit integrity issues.

### Decision 4: Room-2 membership is authorization boundary

- Choice: decision eligibility is derived from ability to post in Room-2; no extra local role table for this flow.
- Rationale: matches operational policy controlled by Matrix room administration.
- Alternative considered: add local authorization allowlist for decisions.
  - Rejected for now to avoid duplicate policy systems and synchronization burden.

### Decision 5: Callback endpoint is emergency-only compatibility path

- Choice: keep `/callbacks/triage-decision` operational but non-primary and flagged for deprecation.
- Rationale: preserves emergency fallback while transitioning to single standard flow.
- Alternative considered: immediate callback removal.
  - Rejected to reduce rollout risk.

### Decision 6: Room-2 final acknowledgment is positive-only and audit-only

- Choice: only positive reaction keys on the bot decision confirmation message are treated as doctor acknowledgment; reaction does not gate workflow progression.
- Rationale: keeps automation deterministic and non-blocking while still recording explicit doctor acknowledgment when provided.
- Alternative considered: wait for acknowledgment before applying decision transition.
  - Rejected because missed reactions would stall cases and break 24/7 automation reliability.

## Risks / Trade-offs

- [Template misuse by doctors (format errors)] -> Mitigation: strict validation with immediate Room-2 feedback and copy-ready template examples.
- [Reply not attached to message I] -> Mitigation: enforce `m.in_reply_to` linkage to active Room-2 root case event and reject otherwise.
- [Authorization ambiguity in atypical room setups] -> Mitigation: document Room-2 governance prerequisite and add startup/runbook checks.
- [Emergency callback path drift over time] -> Mitigation: keep parity regression tests until callback is fully deprecated.
- [Doctor does not react to confirmation] -> Mitigation: acknowledgment remains optional audit signal and never blocks decision progression.

## Migration Plan

1. Introduce/extend Matrix reply parser for Room-2 strict template decisions with robust validation errors.
2. Update Room-2 posting service to emit three-message combo (I PDF + II extracted summary/recommendation + III template/instructions) with II/III replying to I.
3. Route validated reply events to existing decision service using sender-derived `doctor_user_id`.
4. Remove widget-driven decision path from standard runtime/docs and keep callback marked emergency-only.
5. Post Room-2 decision confirmation message after accepted decision handling and store it as reaction target metadata.
6. Add integration coverage for accept/deny, malformed template, wrong reply target, duplicate/race, sender audit parity, and optional positive acknowledgment reaction.
7. Update runbooks for single-path operations and deprecation notice for callback.

Rollback strategy:

- Temporarily rely on emergency callback path while preserving same decision service semantics and data model compatibility.

## Open Questions

- None for architecture direction; implementation may still choose exact reply template syntax details as long as strict parseability and validation guarantees are preserved.
