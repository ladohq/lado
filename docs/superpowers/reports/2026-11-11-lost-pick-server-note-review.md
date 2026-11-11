# LAD-259 lost-pick-server-note: review report

Pull request #288 `hotfix/lad-259-lost-pick-server-note` → `main`. Scale: hotfix, depth
precision. Head reviewed: `dc8bf681`. In the New session window, after a change of Agent that
drops a pick, when the field then takes the new CLI's one saved model of a server by itself,
the note under Model names both facts (`<name> belongs to <CLI>. For this session only: <new
CLI> is not logged in, so it runs on your server's model.`) instead of `back to <CLI>'s
default`. Capability `session-model`: one requirement modified.

## Rounds

1. Local, precision, over the whole diff `origin/main...dc8bf681`. The code matches the spec
   and decisions D1-D3 (the lost pick kept as `{ name, from }`, the text made at render, one
   shared server-model sentence, no second note while a pick is lost); AC-3's existing test
   stays green. Both new vitest tests were seen red on main's `LaunchModel.tsx`. No findings.
2. External 1, Claude Code GitHub Action: E1 confirmed minor, E2 refuted. It did not read the
   openspec files; the local round and `openspec validate` did.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | minor | external: the second new test pins the side line `CloudClaude belongs to Claude Code, so the model is back to Kilo CLI's default.` and the fixture's title "Kilo CLI"; a later fix of that behaviour breaks the test for another reason | declined: the line is true for what the field held; the test is worth changing together with the fix of the item under Found on the way |
| E2 | — | external: "Check again" could reset `tookOne` while a pick is lost, bringing back "back to default" | refuted: `tookOne` is reset only on a change of CLI and in `changed`, which clears the lost pick too; `checkAgain` does not touch it |

## Found on the way

- A server model the field took by itself (`tookOne`) counts, at the next change of Agent, as
  the human's lost pick (`CloudClaude belongs to Claude Code, so the model is back to …`),
  though the human never picked it. Present before this change. Proposed P3, Size S, for
  BACKLOG.md.

## Checks

On `dc8bf681`:
- `npx vitest run src/Launch.test.tsx` 240 passed; `npx tsc --noEmit` exit 0; `make lint`
  green.
- `openspec validate lost-pick-server-note --strict` valid; a trial archive with `openspec
  validate --specs --strict` 82 passed.
- CI green, `ci-ok` pass (unit, integration, web, ui ×4, container ×4); smoke skipped by
  ci.yml's skip list; `mergeStateStatus` CLEAN.

## Residual risk

- The launch window's UI e2e tests were not run by the reviewer locally (the developer ran
  them; CI's four ui shards are green).
- No screenshot, by design decision D4 (vitest is the test layer).
- One edit of `LaunchModel.tsx` was made by a script; the whole diff was read, nothing extra.
