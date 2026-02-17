## 1. Room-2 Message Combo Emission

- [x] 1.1 Add/adjust Room-2 bot message builders for message I (original PDF), message II (extracted data/summary/recommendation), and message III (strict reply template + instructions).
- [x] 1.2 Update Room-2 publishing flow so messages II and III are sent as replies to message I (flat relation model).
- [x] 1.3 Persist/link the Room-2 root context event (message I) in case context so later decision replies can be validated against it.

## 2. Structured Reply Parsing And Validation

- [x] 2.1 Implement strict Room-2 decision template parsing (no free-text inference) for `decision`, `support_flag`, and `reason`.
- [x] 2.2 Enforce existing decision contract rules (`accept|deny`, `support_flag` constraints, `reason` semantics) during parsed payload validation.
- [x] 2.3 Enforce `m.in_reply_to` binding to the active Room-2 root context event (message I) and reject missing/mismatched parent relations.

## 3. Decision Routing And Actor Attribution

- [x] 3.1 Wire Room-2 structured reply events from Matrix runtime listener to the existing doctor-decision application path without adding business logic in adapters.
- [x] 3.2 Derive `doctor_user_id` from Matrix event sender and ignore/reject any typed identity field in reply content.
- [x] 3.3 Keep Room-2 membership as authorization boundary and ensure unauthorized decision-like events are rejected without state mutation.

## 4. Decision Feedback And Runtime Path Consolidation

- [x] 4.1 Emit deterministic Room-2 success feedback when a structured decision is accepted and applied.
- [ ] 4.2 Emit actionable Room-2 error feedback for parse/validation/state/authorization failures.
- [ ] 4.3 Remove widget-style decision as a standard runtime path, keeping `/callbacks/triage-decision` as emergency-only compatibility behavior.
- [x] 4.4 Persist Room-2 decision confirmation message as a dedicated reaction acknowledgment target posted after accepted decision handling.
- [x] 4.5 Accept only supported positive Room-2 acknowledgment reactions on the confirmation target as optional audit signal and keep workflow progression non-blocking.

## 5. Automated Test Coverage

- [ ] 5.1 Add/adjust unit tests for strict Room-2 template parsing and validation (valid accept/deny, malformed template, invalid rule combinations).
- [ ] 5.2 Add/adjust adapter/runtime tests for reply-parent enforcement, sender-based actor attribution, and safe ignore/reject behavior for unsupported events.
- [ ] 5.3 Add/adjust application/integration tests for idempotency/state-race behavior and downstream job parity on structured Room-2 decisions.
- [ ] 5.4 Add/adjust compatibility tests for emergency callback endpoint parity while marked for deprecation.
- [x] 5.5 Add/adjust reaction tests to verify Room-2 positive-only acknowledgment targeting and non-blocking behavior for missing/non-positive reactions.

## 6. Operational Documentation And Manual E2E

- [ ] 6.1 Update manual runbook to validate the three-message Room-2 combo and doctor structured reply to message I in desktop/mobile-capable clients.
- [ ] 6.2 Document negative manual checks for malformed template replies and wrong reply-parent targeting.
- [ ] 6.3 Update runtime docs to mark callback decision endpoint as emergency-only and near-term deprecated.
