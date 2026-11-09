# LAD-240 short-model-names: review report

Pull request #260 `fix/lad-240-short-model-names` → `main`. Scale: tweak, depth precision. Head
reviewed: `366122e4`. A server's model is named by its id by default, and where a model is named by
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
4. Local, precision, the return from `conflicts`, `2ed5d01b..366122e4`: the archive `3f743a45` and
   the merge of `main` with PR #258 (LAD-242). The resolution read with `git show --remerge-diff`: the
   living spec `model-settings-page` keeps the requirements of both LAD-240 and LAD-242, and
   `ModelSources.test.tsx` joins both sides. Found F4.
5. Local, the same head: the corrected pull request description checked; no new finding.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F4 | minor | the CI line of the pull request description named `8c81eed5` of PR #258 and skipped smoke | fixed in the description: "CI on 366122e4: `ci-ok` green, smoke included." |
| F3 | important | CI: the canary integration test expected the old default name `m1 · work · OpenCode` and sent its PATCH to it | fixed in `2ed5d01b`: it expects `m1`; green locally and in CI |
| F2 | minor | two new lines of `docs/design/ui.md` wider than the rest of the file | fixed in `2ed5d01b` |
| F1 | minor | shortening the agent-model requirement to 500 characters dropped the clause on the saved name in the head line | declined: the scenario "An external model on the page" still holds it; `Agents.tsx` unchanged there |
| E1 | minor | external: the CSS `.mx-model-named + .mx-from::before` relies on `.mx-from` following `.mx-model` | declined: true today, and the UI e2e checks the whole line at 768 and 390 px |

## Found on the way

- CI flake `tests/integration/test_human_messages.py::test_a_stop_as_the_message_is_typed_refuses_it_on_a_tmux_server_left_empty`
  (run 42515645273, `integration (3.13, 3)`, `DID NOT RAISE LadoError`): passed on a rerun of the
  failed job; unrelated to the change; tracked as LAD-236.

## Checks

On `366122e4`:
- `make lint` green; model unit tests 309 passed; Vitest (ModelSources, ModelPicker,
  ModelSettings, Agents) 140 passed; UI e2e `tests/ui/test_models_section.py` 31 passed;
  `openspec validate --specs --strict` 82/82.
- The developer ran the full `make test` (6040 passed), `make web` (1832 Vitest) and UI e2e (47).
- CI: all green, `ci-ok` SUCCESS, smoke on Linux and macOS and container included.
- Earlier, on `2ed5d01b`: the canary integration test 1 passed.

## Not checked

- Live tests: not run; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
  `tests/live/` did not change.
- The external reviewer did not read the tests, the docs or the merge of `main`; the local rounds did.
- Models saved under the old long names keep them, by design.
