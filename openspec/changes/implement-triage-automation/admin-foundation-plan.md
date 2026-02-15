# Admin Foundation Plan Extension (No UI)

## 1) Spec Confirmation
- No workflow redesign: confirmed.
- No triage state-machine/schema behavior changes: confirmed.
- No UI implementation in this extension: confirmed.
- Scope is foundational infrastructure only: prompt versioning, roles, auth model, role guards, minimal login API.
- Login foundation uses opaque tokens (no JWT).

## 2) Data Model Additions

### Table: `users`
Purpose: identity + role assignment for future admin/audit access.

Columns:
- `id` UUID PK
- `email` text not null
- `password_hash` text not null
- `role` text not null (`admin`|`reader`)
- `is_active` boolean not null default true
- `created_at` timestamptz not null default now()
- `updated_at` timestamptz not null default now()
- `last_login_at` timestamptz null

Constraints:
- `UNIQUE(email)`
- `CHECK(role IN ('admin','reader'))`

Indexes:
- unique index on `email`
- index on `role`
- index on `is_active`

### Table: `prompt_templates`
Purpose: versioned prompt storage with one active version per prompt name.

Columns:
- `id` UUID PK
- `name` text not null
- `version` int not null
- `content` text not null
- `is_active` boolean not null default false
- `created_at` timestamptz not null default now()
- `updated_at` timestamptz not null default now()
- `updated_by_user_id` UUID null (FK to `users(id)` added in a later migration once `users` exists)

Constraints:
- `UNIQUE(name, version)`
- `CHECK(version > 0)`
- partial unique index: one active row per name (`UNIQUE(name) WHERE is_active = true`)

Indexes:
- index on `(name, version DESC)`
- index on `(name, is_active)`

Seed requirement:
- Migration seeds default active prompts for:
  - `llm1_system`
  - `llm1_user`
  - `llm2_system`
  - `llm2_user`
- Seeded rows use `version = 1` and `is_active = true`.

### Table: `auth_events`
Purpose: authentication audit trail (audit-ready foundation).

Columns:
- `id` bigserial PK
- `user_id` UUID null FK -> `users(id)`
- `email` text null
- `event_type` text not null (`login_success`|`login_failed`|`login_blocked_inactive`)
- `ip_address` text null
- `user_agent` text null
- `payload` jsonb not null default '{}'
- `ts` timestamptz not null default now()

Indexes:
- index on `(user_id, ts)`
- index on `(event_type, ts)`
- index on `(email, ts)`

Relationships:
- `prompt_templates.updated_by_user_id -> users.id` (nullable, established in Slice 22 migration)
- `auth_events.user_id -> users.id` (nullable)

### Table: `auth_tokens`
Purpose: opaque token persistence for login foundation.

Columns:
- `id` UUID PK
- `user_id` UUID not null FK -> `users(id)`
- `token_hash` text not null
- `issued_at` timestamptz not null default now()
- `expires_at` timestamptz not null
- `revoked_at` timestamptz null
- `created_at` timestamptz not null default now()

Constraints:
- `UNIQUE(token_hash)`

Indexes:
- index on `(user_id, issued_at DESC)`
- index on `(expires_at)`
- index on `(revoked_at)`

## 3) Architecture Changes

Where prompt loading logic lives:
- `application/services/prompt_template_service.py` exposes `get_active_prompt(name)`.
- `infrastructure/db/prompt_template_repository.py` handles DB queries.
- Worker LLM services depend on prompt service (not direct SQL).

Where role checking lives:
- `domain/auth/roles.py` defines `Role` enum (`admin`, `reader`).
- `application/services/access_guard_service.py` enforces role requirements.
- Adapters call service-level guard helpers; no adapter business logic.

Where auth service lives:
- `application/services/auth_service.py` for credential verify + login result.
- `infrastructure/security/password_hasher.py` for bcrypt hashing/verification.
- `infrastructure/security/token_service.py` for opaque token generation + hashing.
- `infrastructure/db/user_repository.py` + `auth_event_repository.py` for persistence.
- `infrastructure/db/auth_token_repository.py` for token persistence.

Dependency direction:
- adapters (`FastAPI route`) -> application services -> domain enums/guard rules -> infrastructure adapters.
- Worker prompt usage: application LLM service -> prompt template service -> repository port -> DB adapter.

## 4) Slice Plan

Order keeps triage behavior unchanged while adding isolated foundations.

1. Slice 19: Prompt templates schema and constraints.
2. Slice 20: Prompt template repository and active version retrieval.
3. Slice 21: Worker uses DB active prompt and audits prompt version used.
4. Slice 22: Users/roles/auth_events schema and repositories.
5. Slice 23: Password hashing and auth application service.
6. Slice 24: Role guard utilities.
7. Slice 25: Minimal login endpoint issuing/storing opaque token (no UI).
