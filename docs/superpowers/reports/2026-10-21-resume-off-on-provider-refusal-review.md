# LAD-122 resume-off-on-provider-refusal: review report

Pull request #135 `hotfix/lad-122-resume-off-on-provider-refusal` → `main`. Scale: hotfix,
reviewed by precision: the diff changes one condition of the UI and one option of a
select, no business logic or user data, so no breadth pass; the code rewritten in round 1
(seven lines of JSX) was covered whole by the precision pass. Head reviewed: `e30a962`
(= the remote head). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change, so no live tests were needed.

## Rounds

- **Round 1, local** (precision, `origin/main...e4147c9`): lenses spec, tests,
  comments and descriptions, architecture against AGENTS.md. F1. No external round was
  asked for.
- **Round 2, local** (precision, the delta `e4147c9..e30a962`, commits `135b4f4` and
  `e30a962`): F1 checked in the code: the conditions of the `unknown` and `choose…`
  options exclude each other, the select shows the chosen name, and any pick from the
  list is a change. No new findings.
- **Round 1, external** (Claude Code GitHub Action; request comment 6326526124 at
  21:04:50Z, "Claude finished" at 21:05:07Z, newer than the request): no blockers, one
  minor (F2). It is of the same model family, so its "nothing more" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec, reading) | a session provider absent from the list (`unknown provider gone`) made the Provider select show the first installed provider; picking it sent no `change`, so Resume session never turned on (AC-3) | confirmed | important | fixed in `135b4f4`: a disabled option `<name> · unknown` while `chosenProvider !== null && providerInfo === null`, inside the `providers !== null` branch; vitest "not among the providers" (red before the fix) and the e2e test check it; `docs/design/ui.md` in `e30a962` |
| F2 | ext 1 | external | the line added to `docs/design/ui.md:1387` is longer than its neighbours | confirmed | minor | declined: cosmetic, no effect on meaning or rendering; the loop had converged |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 1 (important,
fixed), external confirmed 1 (minor, declined), refuted 0. Findings in code changed by
the developer's cleanup: 0.

## Checks

- `make lint`: exit 0.
- `make web`: exit 0; 53 files, 979 vitest tests passed.
- `uv run pytest -m ui tests/ui/test_launch.py`: 26 passed (the first run errored for a
  missing Playwright Chromium in the reviewer's environment; green after `make browser`).
- `openspec validate resume-off-on-provider-refusal --strict` valid; `openspec validate
  --specs --strict` 43 of 43 after the archive.
- CI run 39670429986 on `e30a962`: `ci-ok` green after one `gh run rerun --failed`. The
  first try failed only `container (amd64)`,
  `tests/container/test_image.py::test_lado_doctor_is_clean_in_the_container` (Codex CLI
  printed a node error instead of its version); the diff touches no Python or Docker, and
  the test was green on `e4147c9` and on arm64: a flake.

## Not checked

- `make test`, the integration and container tests were not run locally by the reviewer:
  no Python changed (the developer's run: 3615 passed); CI ran them green. The smoke was
  skipped by CI's skip list; live tests were not run.

## Found on the way

- The container test's flake on amd64 (doctor and the Codex CLI), handed to the
  supervisor for a tracker search.
