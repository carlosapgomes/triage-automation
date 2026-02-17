Use the `openspec-apply-change` skill.

  Context:
  - Change ID: implement-room2-decision-widget
  - Task file: 01-contracts-and-guards.md
  - We are implementing one task at a time.

  Execution rules:
  1. Read `AGENTS.md`, then read the selected OpenSpec task file.
  2. Implement ONLY that single task (respect scope boundaries and STOP RULE).
  3. Follow TDD: write/fail tests first, then implement, then refactor.
  4. Enforce docstrings and type hints on new/changed code.
  5. Keep architecture boundaries intact (adapters -> application -> domain -> infrastructure).
  6. Do not change triage workflow/state machine/LLM schemas unless task explicitly requires it.
  7. After completion, mark the task checklist item(s) as done in the task file.
  8. Run the task’s verification commands and report results.
  9. Commit with a meaningful message and push.
  10. Stop and wait for my “go ahead” before starting the next task.

  Output format:
  - What was implemented
  - Files changed
  - Tests added/updated
  - Verification commands + results
  - Commit hash
  - Next suggested task
