## Context

The current Room-2 decision UX ships as an external HTTP page with a dedicated app login (`/auth/login`) and opaque token checks. This diverges from expected Matrix/Element widget behavior and creates a second identity/authentication path that is unrelated to Matrix session identity.

The change goal is to align the Room-2 decision experience with Matrix-native widgets rendered inside Element, where actor identity is derived from Matrix widget context and validated server-side. Existing triage decision semantics must remain unchanged (same state machine transitions, idempotency, and downstream job enqueue behavior).

Constraints:
- Keep decision business logic in application services unchanged.
- Keep callback fallback endpoint (`/callbacks/triage-decision`) operational.
- Do not repurpose `users` table for doctor widget access; that table remains reserved for a future admin/monitoring feature.

## Goals / Non-Goals

**Goals:**
- Deliver Room-2 decision UX as Matrix-native widget flow (in-client iframe/widget framework path).
- Remove widget dependency on app email/password login for doctor actions.
- Resolve and validate acting doctor identity from Matrix widget/client context.
- Preserve existing decision behavior/audit semantics and callback compatibility.

**Non-Goals:**
- Redesigning triage decision rules, statuses, or queue transitions.
- Building the future admin/monitoring panel or changing its auth model.
- Removing existing callback route or existing DB auth schema used by other features.

## Decisions

### Decision 1: Use Matrix-native widget identity as the only widget actor source
- Choice: widget submit actor identity is resolved from Matrix widget authentication context (e.g., Matrix-provided identity/OpenID/session claims) and not from free-form client form input or separate app login.
- Rationale: the trusted identity must come from the same platform where the decision action occurs (Element/Matrix).
- Alternative considered: keep `/auth/login` + app tokens for widget submit.
  - Rejected because it duplicates identity systems and conflicts with native widget expectations.

### Decision 2: Keep backend decision service unchanged; adapt only transport/auth boundary
- Choice: keep `HandleDoctorDecisionService` as the single business path and update only adapter-layer submit contract to populate `doctor_user_id` from validated Matrix context.
- Rationale: preserves business parity and minimizes regression risk.
- Alternative considered: create widget-specific decision service.
  - Rejected because it duplicates rule enforcement and idempotency logic.

### Decision 3: Transition submit contract away from user-entered actor fields
- Choice: deprecate/ignore client-supplied `doctor_user_id` in widget-native path and rely on server-derived actor identity.
- Rationale: prevents spoofing by form payload tampering.
- Alternative considered: keep user-provided `doctor_user_id` with best-effort checks.
  - Rejected because it keeps an avoidable trust flaw.

### Decision 4: Keep callback endpoint and compatibility fallback active
- Choice: `/callbacks/triage-decision` remains available for operational fallback and integration continuity.
- Rationale: reduces migration risk and supports phased adoption.
- Alternative considered: remove callback once widget-native path is introduced.
  - Rejected because it increases operational risk and rollback cost.

### Decision 5: Keep `users` table out of doctor widget authorization scope
- Choice: widget doctor authorization does not depend on local app users/roles for this path.
- Rationale: aligns with planned separation where local users support future admin/monitoring functionality.
- Alternative considered: map Matrix users into local users before submit.
  - Rejected because it introduces coupling and onboarding burden unrelated to this objective.

## Risks / Trade-offs

- [Matrix client/widget API variance across Element versions] -> Mitigation: define minimal supported client/runtime matrix and provide graceful fallback behavior.
- [Server-side validation complexity for Matrix-issued identity artifacts] -> Mitigation: isolate validation adapter with deterministic contract tests and strict failure semantics.
- [Potential confusion during migration from external login flow] -> Mitigation: update runbooks and Room-2 instructions to explicitly describe in-client widget flow.
- [Replay/forgery risk if identity assertions are not audience-bound] -> Mitigation: enforce issuer/audience/expiry checks and reject unsigned or mismatched assertions.

## Migration Plan

1. Introduce Matrix-native widget auth adapter contract and tests (identity extraction + validation).
2. Update widget bootstrap/submit routes to require Matrix-native identity context and remove app-login dependency for widget path.
3. Update static widget UX for in-client operation (no email/password form) and server-trusted actor handling.
4. Keep callback endpoint unchanged as fallback; verify parity with existing integration tests.
5. Update runtime/manual runbooks and negative tests for unauthorized/invalid widget identity contexts.
6. Rollout in test environment first; validate audit actor parity and state transition parity.

Rollback strategy:
- Disable Matrix-native widget path and continue operating through existing callback fallback while preserving state/data compatibility.

## Open Questions

- Which exact Matrix-native identity primitive will be canonical in this project (widget API event context, OpenID token exchange, or deployment-specific equivalent)? 
- What minimum Element/Web client versions will be officially supported for widget-native auth? 
- Should Room-2 messages include explicit fallback instructions for clients that cannot render widgets in-iframe?
