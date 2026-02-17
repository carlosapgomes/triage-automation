## 1. Contracts and Guard Foundations

- [x] 1.1 Add failing tests for widget request/response DTO validation, including `accept|deny` + `support_flag` rules parity (`tasks/01-contracts-and-guards.md`)
- [x] 1.2 Add failing tests for auth token extraction + `admin` role enforcement on widget submit (`tasks/01-contracts-and-guards.md`)
- [x] 1.3 Implement DTOs and guard utility with docstrings/types, then make tests pass (`tasks/01-contracts-and-guards.md`)

## 2. Bot API Widget Endpoints

- [x] 2.1 Add failing API tests for widget bootstrap endpoint (authenticated read of Room-2 decision context) (`tasks/02-bot-api-widget-routes.md`)
- [x] 2.2 Add failing API tests for widget submit endpoint (calls existing decision service path, enqueues same jobs) (`tasks/02-bot-api-widget-routes.md`)
- [x] 2.3 Implement endpoints/routes in `bot-api` preserving existing callback/login behavior (`tasks/02-bot-api-widget-routes.md`)

## 3. Room-2 Launch Payload Integration

- [ ] 3.1 Add failing service tests for Room-2 post including widget launch URL/context while preserving ack + audit behavior (`tasks/03-room2-launch-payload.md`)
- [ ] 3.2 Update Room-2 message template/service composition to include widget launch metadata (`tasks/03-room2-launch-payload.md`)
- [ ] 3.3 Verify no state-machine change (`LLM_SUGGEST -> R2_POST_WIDGET -> WAIT_DOCTOR` remains intact) (`tasks/03-room2-launch-payload.md`)

## 4. Widget Static UI (Minimal)

- [ ] 4.1 Add failing tests for widget static page contract (required fields, submit payload shape, pt-BR text) (`tasks/04-widget-static-ui.md`)
- [ ] 4.2 Implement minimal static widget page + JS client for login, context load, submit accept/deny (`tasks/04-widget-static-ui.md`)
- [ ] 4.3 Add explicit error states (auth failure, wrong state, duplicate/race) and deterministic retry UX (`tasks/04-widget-static-ui.md`)

## 5. End-to-End Integration Coverage

- [ ] 5.1 Add integration test: authenticated widget accept path reaches existing doctor decision outcomes/jobs (`tasks/05-integration-e2e-widget.md`)
- [ ] 5.2 Add integration test: authenticated widget deny path preserves `support_flag=none` rule (`tasks/05-integration-e2e-widget.md`)
- [ ] 5.3 Add integration tests for unauthorized/non-admin submit rejection with no case mutation (`tasks/05-integration-e2e-widget.md`)

## 6. Runtime Configuration and Operational Docs

- [ ] 6.1 Add settings/tests for widget public URL and route registration fail-fast behavior (`tasks/06-config-and-runbook.md`)
- [ ] 6.2 Update `.env.example` and runtime docs with widget-specific configuration (`tasks/06-config-and-runbook.md`)
- [ ] 6.3 Update manual E2E runbook with positive/negative widget test checklist (`tasks/06-config-and-runbook.md`)

## 7. Quality Gates and Slice Closeout

- [ ] 7.1 Run `uv run pytest -q` and targeted widget integration tests (`tasks/07-closeout-and-quality-gates.md`)
- [ ] 7.2 Run `uv run ruff check .` and `uv run mypy src apps` (`tasks/07-closeout-and-quality-gates.md`)
- [ ] 7.3 Final review for docstrings/public types in touched files and prepare incremental slice commits (`tasks/07-closeout-and-quality-gates.md`)
