## 1. The workflow

- [ ] 1.1 `tests/test_workflow_security.py`: the checks of D3 (AC-1, AC-2, AC-3), each
  failing on today's `claude.yml`. `make test`.
- [ ] 1.2 `.github/workflows/claude.yml`: `fetch-depth: 0`; `claude_args` by D1 with the
  instruction of D2; the boilerplate comments of `prompt` / `claude_args` replaced by one
  comment on why there is no `prompt`. SHA, `permissions`, `additional_permissions`, the
  `if:` and the secret unchanged. The tests of 1.1 pass; `actionlint` by D4 (AC-4).

## 2. Documents

- [ ] 2.1 `.lado/sdlc.md`, **External reviewer**: the coverage line of D5.
- [ ] 2.2 `docs/testing.md`, the paragraph on `claude.yml`: the full history, the three
  reading commands, the standing instruction and its two lists, and that the setup runs
  from the default branch.
- [ ] 2.3 BACKLOG.md, in a commit of its own (template: tier, `Size:`, `Why here:`,
  Found: 2026-10-23, this branch): the Action's comment mode grants Claude file edits
  and git commit/push by itself (proposal, Out of scope).

## 3. Checks

- [ ] 3.1 `make lint`, `make test`, `openspec validate review-reads-risky-code --strict`;
  CI green on the last commit (AC-4).
- [ ] 3.2 `build-report` names AC-5 as checked only after the merge, on the next pull
  request.
