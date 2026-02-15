# Implementation Tasks: implement-triage-automation

Tracking rule: complete slices strictly in order. Each slice is independently testable and resumable.

## Progress

- [x] 01. Project Bootstrap and Quality Gates (`tasks/01-bootstrap-quality-gates.md`)
- [x] 02. Runtime Config and Docker Compose Baseline (`tasks/02-config-compose.md`)
- [x] 03. Initial Postgres Schema and Migrations (`tasks/03-db-schema-migrations.md`)
- [x] 04. Domain Status and Transition Guards (`tasks/04-state-transitions.md`)
- [x] 05. Case/Audit/Message Repositories (`tasks/05-case-audit-message-repos.md`)
- [x] 06. Postgres Job Queue (SKIP LOCKED) (`tasks/06-job-queue-skip-locked.md`)
- [x] 07. Worker Runtime and Boot Reconciliation (`tasks/07-worker-runtime-reconciliation.md`)
- [x] 08. Room-1 PDF Intake Flow (`tasks/08-room1-intake.md`)
- [x] 09. PDF Download and Text Extraction (`tasks/09-process-pdf-download-extract.md`)
- [x] 10. Record Number Extraction and Stripping (`tasks/10-record-number-strip.md`)
- [x] 11. LLM1 Integration and Validation (`tasks/11-llm1-validation.md`)
- [x] 12. LLM2 Integration and EDA Policy Cross-Check (`tasks/12-llm2-policy-crosscheck.md`)
- [x] 13. Room-2 Widget Posting with 7-day Prior Lookup (`tasks/13-room2-widget-priors.md`)
- [x] 14. HMAC Webhook and Doctor Decision Handling (`tasks/14-webhook-doctor-decision.md`)
- [x] 15. Room-3 Request Posting (`tasks/15-room3-request.md`)
- [x] 16. Room-3 Reply Parsing and Strict Re-prompt (`tasks/16-room3-parser-reprompt.md`)
- [x] 17. Room-1 Final Replies + Cleanup CAS Trigger (`tasks/17-final-reply-reaction-cas.md`)
- [x] 18. Cleanup Execution + Retry Exhaustion + Recovery E2E (`tasks/18-cleanup-retry-recovery-e2e.md`)
- [x] 19. Prompt Templates Schema and Constraints (`tasks/19-prompt-templates-schema.md`)
- [x] 20. Prompt Template Repository and Active Version Service (`tasks/20-prompt-template-repository.md`)
- [x] 21. Worker Dynamic Prompt Loading + Audit Prompt Version (`tasks/21-worker-dynamic-prompt-loading.md`)
- [x] 22. Users/Roles/Auth Audit Schema and Repositories (`tasks/22-users-roles-auth-audit-schema.md`)
- [x] 23. Password Hashing Service and Auth Application Logic (`tasks/23-password-hashing-auth-service.md`)
- [x] 24. Role Guard Utilities (Admin vs Reader) (`tasks/24-role-guard-utilities.md`)
- [x] 25. Minimal Login Endpoint (No UI) (`tasks/25-login-endpoint-no-ui.md`)

## Resume Protocol

1. Read `PROJECT_CONTEXT.md`.
2. Open `tasks.md` and pick the first unchecked slice.
3. Execute only that slice file.
4. Verify slice with `pytest`, `ruff`, and `mypy`.
5. Commit that slice with a meaningful message.
6. Mark it complete in this file.
7. Stop before starting the next slice.

## Commit Rule

- Commit after every slice completion.
- Commit scope must be only the current slice.
- Commit message format:
  - `slice-XX: <short meaningful summary>`
  - Example: `slice-08: implement Room-1 PDF intake idempotency and queue enqueue`
