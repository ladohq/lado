# LAD-240 short-model-names: review report

Pull request #260 `fix/lad-240-short-model-names` → `main`. Scale: tweak, depth precision. Head
reviewed: `2ed5d01b`. A server's model is named by its id by default, and where a model is named by
its id the UI shows the id once: in the model picker, in Your models and in the agent's Model. Models
saved under the old long names stay as they are. Delta: changes to `agent-model` and
`model-settings-page`.

## Rounds

1. Local, precision, `origin/main..ddae16ed`: the whole diff against the spec, a trial archive.
   The naming rule read whole, every branch. Found F1 and F2; CI found F3.
2. External 1, Claude Code GitHub Action: no blockers, the observation E1. It read
   `model_settings.py`, `Agents.tsx`, `ModelPicker.tsx`, `ModelSettings.tsx`, `modelFakes.ts` and
   `styles.css`, not the docs, specs or tests.
3. Local, precision, `ddae16ed..2ed5d01b`: one commit, the test and the docs' line breaks; no new
   finding.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F3 | important | CI: the canary integration test expected the old default name `m1 · work · OpenCode` and sent its PATCH to it | fixed in `2ed5d01b`: it expects `m1`; green locally and in CI |
| F2 | minor | two new lines of `docs/design/ui.md` wider than the rest of the file | fixed in `2ed5d01b` |
| F1 | minor | shortening the agent-model requirement to 500 characters dropped the clause on the saved name in the head line | declined: the scenario "An external model on the page" still holds it; `Agents.tsx` unchanged there |
| E1 | minor | external: the CSS `.mx-model-named + .mx-from::before` relies on `.mx-from` following `.mx-model` | declined: true today, and the UI e2e checks the whole line at 768 and 390 px |

## Found on the way

- CI flake `tests/integration/test_human_messages.py::test_a_stop_as_the_message_is_typed_refuses_it_on_a_tmux_server_left_empty`
  (run 42515645273, `integration (3.13, 3)`, `DID NOT RAISE LadoError`): passed on a rerun of the
  failed job; unrelated to the change; tracked as LAD-236.

## Checks

- `make lint` green; model unit tests 309 passed; Vitest of four files 137 passed; UI e2e
  `tests/ui/test_models_section.py` 25 passed; the canary integration test 1 passed; trial archive and
  `openspec validate --specs --strict` 80/80.
- The developer ran the full `make test` (5984 passed) and `make web` (1792 Vitest).
- CI on `2ed5d01b`: all green, `ci-ok` SUCCESS, smoke on Linux and macOS and container included.

## Not checked

- Live tests: not run; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
  `tests/live/` did not change.
- The external reviewer did not read the tests or the docs; the local rounds did.
