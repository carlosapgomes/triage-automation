# Implementation Tasks: enable-live-runtime-e2e

Tracking rule: complete slices strictly in order. Each slice is independently testable and resumable.

## 1. Runtime Orchestration Baseline

- [x] 1.1 Serve `bot-api` as a real ASGI process and align compose command (`tasks/01-bot-api-asgi-runtime.md`)
- [x] 1.2 Expand runtime settings for live execution (Matrix bot auth, polling/runtime flags, LLM mode toggles) (`tasks/02-runtime-settings-expansion.md`)

## 2. Worker Live Handler Wiring

- [x] 2.1 Build worker dependency composition and non-empty handler map for existing job types (`tasks/03-worker-handler-map.md`)
- [x] 2.2 Wire runtime handlers to existing services without changing job semantics (`tasks/04-worker-runtime-service-wiring.md`)
- [x] 2.3 Add worker runtime integration coverage for handler dispatch, retry/dead-letter, and recovery startup sequence (`tasks/05-worker-runtime-integration-tests.md`)

## 3. Matrix Live Adapters and Event Routing

- [x] 3.1 Implement concrete Matrix adapter ports (`send_text`, `reply_text`, `redact_event`, `download_mxc`) (`tasks/06-matrix-adapter-ports.md`)
- [x] 3.2 Implement Room-1 PDF intake listener routing in `bot-matrix` runtime (`tasks/07-room1-intake-listener.md`)
- [x] 3.3 Implement reaction listener routing (Room-1 cleanup trigger, Room-2/3 audit thumbs) (`tasks/08-reaction-listener-routing.md`)
- [x] 3.4 Implement Room-3 reply listener routing with strict parser/re-prompt behavior (`tasks/09-room3-reply-listener.md`)

## 4. LLM Runtime Readiness

- [x] 4.1 Add runtime LLM adapter wiring with provider-configured execution path (`tasks/10-llm-runtime-adapter.md`)
- [x] 4.2 Add deterministic manual-test LLM mode and runtime smoke coverage (`tasks/11-llm-deterministic-mode.md`)

## 5. Manual E2E Readiness and Closeout

- [x] 5.1 Document and validate local + Cloudflare tunnel smoke workflow (`tasks/12-manual-e2e-runbook.md`)
- [x] 5.2 Run full verification and close out runtime-readiness implementation (`tasks/13-runtime-e2e-closeout.md`)

## Resume Protocol

1. Read `PROJECT_CONTEXT.md`.
2. Open `openspec/changes/enable-live-runtime-e2e/tasks.md` and pick the first unchecked slice.
3. Execute only that slice file under `openspec/changes/enable-live-runtime-e2e/tasks/`.
4. Run required verification (`pytest`, `ruff`, `mypy`) for that slice.
5. Commit the slice with a meaningful message.
6. Mark the slice complete in `tasks.md`.
7. Stop before starting the next slice.

## Commit Rule

- Commit after every slice completion.
- Commit scope must be only the current slice.
- Commit message format:
  - `slice-XX: <short meaningful summary>`
  - Example: `slice-03: wire worker handler map for live runtime`
