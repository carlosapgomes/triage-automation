## 1. Baseline Policy and Guardrail Setup

- [x] 1.1 Define docstring/type enforcement baseline and scope in config comments and project context notes (`tasks/01-baseline-policy.md`)
- [x] 1.2 Add initial non-breaking `ruff`/`mypy` ratchet configuration that targets first package group only (`tasks/02-initial-tooling-ratchet.md`)

## 2. Progressive Package Ratchet Slices

- [x] 2.1 Ratchet `src/triage_automation/application` for public docstrings and typed public signatures (`tasks/03-ratchet-application.md`)
- [x] 2.2 Ratchet `src/triage_automation/domain` with same policy and remediation (`tasks/04-ratchet-domain.md`)
- [x] 2.3 Ratchet `src/triage_automation/infrastructure` with same policy and remediation (`tasks/05-ratchet-infrastructure.md`)
- [ ] 2.4 Ratchet `apps/` entrypoints and shared wiring modules (`tasks/06-ratchet-apps.md`)

## 3. Test and CI Enforcement

- [ ] 3.1 Apply agreed docstring/type policy to tests (or codify scoped exclusions) with deterministic rationale (`tasks/07-tests-policy.md`)
- [ ] 3.2 Enforce ratchet gates in CI and local verification workflow (`tasks/08-ci-gates.md`)

## 4. Final Hardening Verification

- [ ] 4.1 Run full repo validation (`pytest`, `ruff`, `mypy`) and fix remaining violations within defined policy scope (`tasks/09-final-verification.md`)
- [ ] 4.2 Document completion status, residual exceptions, and maintenance rules for future slices (`tasks/10-closeout.md`)
