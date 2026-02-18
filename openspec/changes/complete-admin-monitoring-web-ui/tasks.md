# Tasks

## 1. Web session foundation

- [ ] 1.1 Implement `GET /` redirect behavior based on authenticated session state.
- [ ] 1.2 Implement `GET /login` HTML page and `POST /login` form flow using existing `AuthService`.
- [ ] 1.3 Implement `POST /logout` to clear session cookie and redirect to login.
- [ ] 1.4 Add integration tests for success, invalid credentials, and logout behavior.

## 2. Session and guard integration

- [ ] 2.1 Add cookie-based token resolution in auth guard while preserving Bearer support.
- [ ] 2.2 Define deterministic precedence between Authorization header and session cookie.
- [ ] 2.3 Add tests covering cookie-only, Bearer-only, and mixed request authentication cases.

## 3. Shared operations shell

- [ ] 3.1 Create shared base template for authenticated pages (header, nav, logout).
- [ ] 3.2 Migrate dashboard list/detail pages to shared shell without regressions.
- [ ] 3.3 Implement role-aware navigation: `admin` sees prompts nav, `reader` does not.
- [ ] 3.4 Add integration tests asserting layout reuse and role-conditioned menu rendering.

## 4. Prompt admin HTML pages

- [ ] 4.1 Add server-rendered admin prompts list page (name, versions, active state).
- [ ] 4.2 Add server-rendered activation flow for admin prompt version change.
- [ ] 4.3 Keep existing `/admin/prompts/*` APIs as source of behavior and authorization.
- [ ] 4.4 Add integration tests for admin happy path and reader forbidden access.

## 5. Authorization matrix hardening

- [ ] 5.1 Enforce rule: `admin` can access dashboard and prompt-admin pages.
- [ ] 5.2 Enforce rule: `reader` can access dashboard pages only.
- [ ] 5.3 Ensure unauthorized prompt-admin attempts never mutate prompt state.
- [ ] 5.4 Add audit assertions for admin prompt activation actions.

## 6. Documentation and runbooks

- [ ] 6.1 Update `README.md` with landing/login and role matrix navigation summary.
- [ ] 6.2 Update `docs/setup.md` with browser-first login flow and logout notes.
- [ ] 6.3 Update `docs/manual_e2e_runbook.md` with end-to-end checks for web login and role-based menu visibility.

## 7. Verification gates

- [ ] 7.1 Run targeted tests for login/session, dashboard pages, and prompt admin pages.
- [ ] 7.2 Run `uv run ruff check` and `uv run mypy` on changed paths.
- [ ] 7.3 Run `markdownlint-cli2` on changed OpenSpec/docs markdown files.
