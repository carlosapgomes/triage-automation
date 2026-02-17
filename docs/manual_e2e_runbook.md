# Manual E2E Runbook

This runbook validates the Room-2 widget path end-to-end in a deterministic local environment.
Run `docs/runtime-smoke.md` first to confirm process startup and callback reachability.

## Prerequisites

1. Start runtime processes with the same commands used in `docs/runtime-smoke.md`:

```bash
uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000
uv run python -m apps.bot_matrix.main
uv run python -m apps.worker.main
```

2. Confirm `.env` has a public widget URL base:

- `WIDGET_PUBLIC_URL` (or fallback `WEBHOOK_PUBLIC_URL`)

3. Use a test case already moved to `WAIT_DOCTOR` with a valid Room-2 widget post.

## Room-2 Widget Positive Path

1. Open the launch URL published in Room-2:

- `/widget/room2?case_id=<case-id>`

2. Authenticate in the widget UI (or API-level equivalent):

- `POST /auth/login`

3. Fetch Room-2 decision context:

- `POST /widget/room2/bootstrap`

4. Submit an accept decision:

- `POST /widget/room2/submit`
- Payload: `decision=accept`, `support_flag=none`, optional `reason`

5. Validate expected progression:

- Case status moves to `DOCTOR_ACCEPTED`
- A next job `post_room3_request` is enqueued
- Audit includes the widget submit actor and outcome

## Widget Negative Auth Checks

1. Submit without Authorization header (without Authorization):

- `POST /widget/room2/submit`
- Expected: `401`

2. Submit with reader role token (reader role token):

- `POST /widget/room2/submit`
- Expected: `403`

3. Validate no unexpected state/job mutation (state/job mutation):

- Case status does not change
- No additional decision job is enqueued
- Only expected auth/audit records are present
