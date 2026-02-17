## Why

The current Room-2 decision widget is implemented as a plain HTTP page with a separate email/password login, which breaks the expected Element widget experience and duplicates identity/auth concerns outside Matrix. We need to align the implementation with Matrix-native widgets so doctor identity comes from the Matrix client/session context, not a secondary application credential store.

## What Changes

- Replace the current link-opened external Room-2 decision page flow with a Matrix-native widget flow rendered in Element (iframe/widget framework path).
- Remove widget decision dependency on `/auth/login` email/password for doctor operation.
- Use Matrix-native widget identity context to resolve the acting user for decision submit, and propagate that identity into existing audit/event payloads.
- Keep current business decision behavior and state-machine semantics unchanged (`WAIT_DOCTOR` gating, idempotency, enqueue side effects).
- Preserve existing callback endpoint compatibility (`/callbacks/triage-decision`) as fallback/operational compatibility.
- Keep `users` table usage out of widget decision auth scope for this change; it remains reserved for future admin/monitoring capabilities.
- **BREAKING**: manual widget login UX and external-page assumptions used in the previous implementation are removed/replaced by Matrix-native widget interaction requirements.

## Capabilities

### New Capabilities
- `matrix-native-room2-widget`: Room-2 decision widget execution through Matrix-native widget framework, including in-client rendering and Matrix-derived actor identity.

### Modified Capabilities
- `runtime-orchestration`: runtime requirements for widget serving/auth change from standalone app-login model to Matrix-native widget identity model.
- `manual-e2e-readiness`: manual runbook requirements change to validate in-client widget behavior and Matrix-context identity, not email/password widget login.
- `matrix-live-adapters`: adapter requirements expand to support Matrix widget identity/context handling used by Room-2 decision submit.

## Impact

- Affected code/systems:
  - `apps/bot_api/main.py`
  - `src/triage_automation/infrastructure/http/widget_router.py`
  - `apps/bot_api/static/widget/room2/*`
  - auth guard and token logic currently tied to `/auth/login` for widget path
  - Room-2 message/widget launch metadata and manual E2E docs
- API/runtime surface:
  - Room-2 widget auth contract changes from app token login to Matrix-native context validation.
  - Existing callback HMAC endpoint remains available for compatibility.
- Dependencies:
  - Matrix/Element widget framework contracts become first-class dependency for decision UX and actor resolution.
  - No new dependency on `users` table for doctor widget access in this change.
