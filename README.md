# Triage Automation

Monorepo for triage automation services:
- `bot-api`
- `bot-matrix`
- `worker`

This repository is under slice-based implementation with strict TDD.

## Local Quality Gates

Run the same checks enforced in CI before pushing:

```bash
uv run ruff check .
uv run mypy src apps
uv run pytest -q
```

## CI

GitHub Actions workflow: `.github/workflows/quality-gates.yml`
