## 1. Matrix Widget Identity Contract and Adapter Foundation

- [ ] 1.1 Add failing unit tests for Matrix-native widget identity assertion validation (issuer/audience/expiry/signature failure paths)
- [ ] 1.2 Define adapter-layer identity validation contract and DTOs for resolved Matrix actor context
- [ ] 1.3 Implement infrastructure adapter wiring for widget identity validation with deterministic rejection on invalid artifacts

## 2. Room-2 Widget Route Auth Migration

- [ ] 2.1 Add failing integration tests showing widget bootstrap/submit succeed with valid Matrix widget identity context and fail without it
- [ ] 2.2 Replace widget route auth dependency on `/auth/login` app token flow with Matrix-native identity context guard
- [ ] 2.3 Ensure widget submit derives actor identity server-side and ignores/rejects conflicting client-provided `doctor_user_id`

## 3. Matrix-Native Widget UI and Launch Surface

- [ ] 3.1 Add failing static contract tests for in-client widget flow without email/password login form
- [ ] 3.2 Update Room-2 widget static assets to remove app-login UX and operate with Matrix-native context bootstrap/submit calls
- [ ] 3.3 Update Room-2 launch metadata/message contract to target Matrix-native widget rendering semantics in Element clients

## 4. Decision Parity and Safety Guarantees

- [ ] 4.1 Add integration tests proving ACCEPT/DENY outcomes, state transitions, and downstream jobs remain identical to current decision path
- [ ] 4.2 Add integration tests proving invalid/missing Matrix identity context causes rejection with no case/job mutation
- [ ] 4.3 Verify callback fallback (`/callbacks/triage-decision`) remains behaviorally unchanged

## 5. Runtime and Manual E2E Documentation Updates

- [ ] 5.1 Update runtime docs to describe Matrix-native widget prerequisites and supported client/runtime constraints
- [ ] 5.2 Update manual E2E runbook to validate in-client widget usage without secondary app login
- [ ] 5.3 Add deterministic negative runbook checks for invalid Matrix identity assertions and no-mutation guarantees

## 6. Quality Gates and Closeout

- [ ] 6.1 Run full verification suite: `uv run pytest -q`, plus targeted widget-native integration tests
- [ ] 6.2 Run static checks: `uv run ruff check .` and `uv run mypy src apps`
- [ ] 6.3 Final review for architecture boundaries/docstrings/types and confirm all checklist items are complete
