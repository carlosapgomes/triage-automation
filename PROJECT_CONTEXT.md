# Triage Automation Project Context

## Purpose
This file is the implementation pre-read for every slice. It summarizes the authoritative handoff contract, architecture boundaries, and non-negotiable constraints so execution remains deterministic when context is reset.

## Authoritative Sources
- Primary contract: `prompts/first-prompt.md` (embedded `<handoff>` specification).
- Planning artifacts: `openspec/changes/implement-triage-automation/tasks.md` and `openspec/changes/implement-triage-automation/tasks/*.md`.

If this file conflicts with the handoff spec, follow the handoff spec.

## Project Goal
Implement an event-driven triage automation across 3 unencrypted Matrix rooms with full auditability and cleanup-by-reaction semantics:
- Room-1 intake of human PDF messages.
- PDF extraction, watermark record-number handling, LLM structured outputs and suggestion.
- Room-2 doctor decision via webhook callback.
- Room-3 scheduling request/reply parsing with strict template handling.
- Room-1 final reply always as reply-to original intake.
- Cleanup triggered exactly once by first 👍 on Room-1 final reply.

## Extended Goal (Admin Foundation, No UI)
Add foundational backend infrastructure for a future admin interface without changing triage business behavior:
- Prompt template storage with versioning and single active version per prompt name.
- User + role model (`admin`, `reader`) stored in DB.
- Authentication foundation with secure password hashing and role guard utilities.
- Minimal backend login capability only (no UI).

## Architecture and Service Boundaries
- `bot-api` (FastAPI): webhook callback ingress + auth + persistence/enqueue.
- `bot-matrix` (matrix-nio): Matrix event ingestion and reaction routing.
- `worker`: async job execution for extraction/LLM/posting/cleanup.
- `postgres`: source of truth (cases, audit, message map, queue).

Dependency direction:
- adapters -> application/services -> domain -> infrastructure details isolated behind ports.

## Technical Constraints
- Python 3.12
- SQLAlchemy 2.x async + `asyncpg`
- Alembic migrations
- Pydantic for settings/contracts (webhook + LLM schemas)
- `uv` for dependency lock/install
- TDD strictly with pytest
- Deterministic behavior; no hidden side effects

## Non-Negotiable Domain Rules
- Do not redesign state machine or transitions.
- Do not change cleanup semantics: first Room-1 👍 on final reply wins.
- Do not change idempotency contract: unique Room-1 origin event id prevents duplicate case creation.
- Do not change strict Room-3 reply templates.
- Do not change webhook payload contract except confirmed clarifications below.
- Do not change LLM schema intent and validation strictness.
- Room-2 and Room-3 👍 on ack messages are audit-only and never trigger cleanup.
- Do not implement admin UI in this phase.
- Do not change triage workflow behavior while introducing admin foundations.

## Clarifications Locked In (2026-02-15)
- `support_flag` enum: `none | anesthesist | anesthesist_icu`
- Final reply jobs transition directly to `WAIT_R1_CLEANUP_THUMBS` after posting.
- Invalid Room-3 scheduler reply always gets strict re-prompt and remains in `WAIT_APPT`.
- Webhook auth mode for now: HMAC only.
- On startup reconciliation, stale `jobs.status='running'` must be reset to `queued` with unchanged `attempts`.
- Auth foundation token strategy: opaque tokens (not JWT).
- Prompt bootstrap strategy: seed default active prompt templates in migration.

## Core Data Model (Authoritative)
- `cases`: case lifecycle, decisions, appointment fields, final-reply and cleanup timestamps, artifacts.
- `case_events`: append-only audit log.
- `case_messages`: room/event mapping for cleanup targeting.
- `jobs`: Postgres queue with `queued|running|done|failed|dead`, `run_after`, retries.

## State Machine (Status Set)
`NEW`, `R1_ACK_PROCESSING`, `EXTRACTING`, `LLM_STRUCT`, `LLM_SUGGEST`, `R2_POST_WIDGET`, `WAIT_DOCTOR`, `DOCTOR_DENIED`, `DOCTOR_ACCEPTED`, `R3_POST_REQUEST`, `WAIT_APPT`, `APPT_CONFIRMED`, `APPT_DENIED`, `FAILED`, `R1_FINAL_REPLY_POSTED`, `WAIT_R1_CLEANUP_THUMBS`, `CLEANUP_RUNNING`, `CLEANED`.

Implementation note: although the enum includes `R1_FINAL_REPLY_POSTED`, current execution transitions directly to `WAIT_R1_CLEANUP_THUMBS` after final post.

## Execution Quality Bar Per Slice
- Write failing tests first (RED).
- Implement minimal behavior (GREEN).
- Refactor only after passing tests (CLEAN).
- Run verification for each slice:
  - `uv run pytest ...`
  - `uv run ruff check .`
  - `uv run mypy src apps`
- Commit after each completed slice with a meaningful message before moving to the next slice.
- Stop after the slice completes. Do not pre-implement future slices.

## Pre-Slice Read Sequence
1. `PROJECT_CONTEXT.md`
2. `openspec/changes/implement-triage-automation/tasks.md`
3. current slice file under `openspec/changes/implement-triage-automation/tasks/`
4. only then implement
