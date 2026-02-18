# Manual E2E Runbook

This runbook validates the Room-2 structured Matrix reply path end-to-end in a deterministic local environment.
Run `docs/runtime-smoke.md` first to confirm process startup and callback reachability.

## Prerequisites

1. Start runtime processes with the same commands used in `docs/runtime-smoke.md`:

```bash
uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000
uv run python -m apps.bot_matrix.main
uv run python -m apps.worker.main
```

1. Use a test case already moved to `WAIT_DOCTOR` with Room-2 case context posted by bot.

## Room-2 Structured Reply Positive Path

1. Validate the three-message Room-2 combo for the target case in desktop and mobile clients:

- message I: original PDF context
- message II: extracted data + summary + recommendation (reply to message I)
- message III: strict template instructions (reply to message I)
- verify in both desktop and mobile that messages remain grouped under message I

1. Open message III and copy the strict template.

2. Submit decision by sending a Matrix reply to message I (reply to message I):

- include template fields exactly:
  - `decision: accept|deny`
  - `support_flag: none|anesthesist|anesthesist_icu`
  - `reason: <texto livre ou vazio>`
  - `case_id: <case-id>`

1. For positive flow validation, send:

- `decision: accept`
- `support_flag: none`
- optional `reason`

1. Validate expected progression:

- Case status moves to `DOCTOR_ACCEPTED`
- A next job `post_room3_request` is enqueued
- Audit includes the Matrix sender as actor and outcome

## Widget Negative Auth Checks

1. Submit without Authorization header (without Authorization):

- `POST /widget/room2/submit`
- Expected: `401`

1. Submit with reader role token (reader role token):

- `POST /widget/room2/submit`
- Expected: `403`

1. Validate no unexpected state/job mutation (state/job mutation):

- Case status does not change
- No additional decision job is enqueued
- Only expected auth/audit records are present

## Room-2 Negative Reply Checks

1. Post malformed template reply (malformed template):

- reply to message I with missing/invalid required lines
- expected bot feedback includes `error_code: invalid_template`
- expected no decision mutation and no new downstream job enqueue

1. Post valid template on wrong reply-parent (wrong reply-parent):

- send template as reply to message II/III or unrelated event (not message I root)
- expected bot feedback includes `error_code: invalid_template`
- expected no decision mutation and no new downstream job enqueue

## Dashboard and Monitoring API Checks

1. Open server-rendered dashboard list in browser:

- `GET /dashboard/cases` with a valid bearer token
- expected HTML list renders with cases and filters

1. Validate monitoring list API:

- `GET /monitoring/cases`
- expected `200` and JSON with `items`, `page`, `page_size`, `total`

1. Validate per-case detail API and auditable events:

- `GET /monitoring/cases/{case_id}`
- expected `200` and a chronological timeline ordered by `timestamp`
- timeline must include `source`, `channel`, `actor`, `event_type`
- when applicable, validate both ACK and human reply events are present

1. Cross-check API vs dashboard detail:

- open `GET /dashboard/cases/{case_id}`
- verify chronological timeline visible in UI matches monitoring API for the same case

## Prompt Management Authorization Flow

1. Using reader token (reader token), verify read-only behavior:

- `GET /monitoring/cases` returns `200`
- `GET /admin/prompts/versions` returns `403`
- `GET /admin/prompts/{prompt_name}/active` returns `403`
- `POST /admin/prompts/{prompt_name}/activate` returns `403`

1. Using admin token (admin token), verify prompt mutation behavior:

- `GET /admin/prompts/versions` returns `200`
- `GET /admin/prompts/{prompt_name}/active` returns `200`
- `POST /admin/prompts/{prompt_name}/activate` returns `200`

1. Validate prompt activation side effects:

- exactly one active version remains for the prompt name
- auth audit includes `prompt_version_activated` with actor and target prompt/version
