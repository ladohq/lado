Task: LAD-187

## Why

The human saves model servers and configured models only from the terminal (`lado
model-server add|list|remove`, `lado model add|list|remove`). The epic's concept sets them
once in Settings, under names the rest of LADO refers to; the next work (a session on a
configured model) picks them by name in the launch window, so they must be made where the
launch window is: in the UI.

Root cause: the store and its rules (`model_settings.py`) have no API, by "only what is
used", and the UI has no place for the human's model settings.

Options weighed for where the page's rules live:

- A (taken): the page calls a thin API over `model_settings.py`, the commands' own
  functions; each refusal is the core's line, with the field it concerns added by the core.
  Long-term cost: one more attribute on two exception types; one source of truth for every
  rule and text, so a fix of a check reaches the CLI and the page at once.
- B: the API re-implements the checks for the page with UI words (no CLI commands in the
  texts). Long-term cost: two sets of rules and texts that drift; every later check
  (sessions on a configured model, doctor) has to be written twice.
- C: the page probes and checks in the browser (fetch to the server's address). Breaks the
  key rule (the key in the browser's requests and the server's CORS), cannot reach a
  server only LADO's machine sees, and doubles the probe in TypeScript. Rejected.

Held against ROADMAP and the coming steps (a session on a configured model, effort, power
tables): A gives the launch window and the power tables one API to list the entries;
neutral core: the page names no provider; the ready-made models come from a provider's own
declaration, which only Claude Code fills today (said on the page by their absence for the
others, see design.md D7).

## What Changes

- Settings gets a section **Models** after Providers and environment, before Usage
  statistics, at `/settings#models`: a block **Your models** (a table, + Add model, the
  ready-made models of the installed CLIs) and a block **Model servers** (a row per server,
  + Add server, Check, Change, Remove).
- Adding a server probes it as `lado model-server add` does and shows what the probe found:
  type, models (embeddings marked), the CLIs that can use it and those that cannot, the
  neutral `same address as model server "<name>"` line and the plain-http warning. Change
  replaces its address and/or key as `--replace` does (an empty key keeps the kept one).
  Removing a server a model uses is refused with the command's line naming the models.
- Adding a model: name, CLI, optional server, the model with suggestions (the CLI's aliases
  and list, or the server's list without its embeddings models) and a live check under the
  field, as the launch window's Model field has; Add saves it as `lado model add` does.
  Models are removed one at a time.
- Ready-made models: one click adds Claude Haiku · haiku, Claude Sonnet · sonnet or Claude
  Opus · opus when Claude Code is installed (Add all three adds the ones shown); a chip
  goes once a model of that CLI with that model is saved.
- Every refusal is the command's line, shown under the field it concerns, the form kept.
- A new API under `/api/model-settings`, `/api/model-servers` and `/api/models`. A server's
  key enters it only in the body of a POST and leaves it never: no answer, log, error
  journal or change feed holds it (a canary test).
- The probe gives why a server has no list only when it has none (a list read with
  `anthropic-version` used to keep the plain list's failure as its why).
- The key field is the dots field of a project's secrets, not a password field (browsers
  offer to save a password field's value).

## Out of scope

- Choosing a configured model in the launch window and `lado start --model <name>`, agents
  on a server, a check before the start: the next work, which uses these entries.
- Effort, power tables, kits' and roles' weights: later work of the same epic.
- Editing a model in place, renaming a server or a model, removing a key without removing
  its server: the commands have none either; remove and add again.
- Removing several models at once, or a server with its models: one at a time keeps every
  removal confirmed in its own row and the server's refusal names what to remove.
- Ready-made models for Codex CLI, OpenCode and Kilo CLI: they have no alias that follows
  the latest model, and their lists depend on the account and servers, so a fixed entry
  would go stale.
- Probing every server when the page opens: a server that does not answer would hold the
  page up to 10 s, and the page would ask every server each visit; Check asks one on demand.
- UI texts of their own for the refusals: they would be a second set of texts drifting from
  the commands'; the page shows the commands' lines as a project's secrets do.

## Capabilities

### New Capabilities

- `model-settings-page`: Settings → Models, the page of the saved model servers and the
  configured models, and the API it uses.

### Modified Capabilities

- `model-servers`: the why of a server's missing list is given only when it has no list.

## Impact

- Code: `src/lado/model_settings.py` (refusals with their field, a check without saving),
  `src/lado/model_servers.py` (`ProbeError.field`, the list's why),
  `src/lado/providers/base.py` and `claude.py` (`ready_models`), `src/lado/server/app.py`,
  `src/lado/server/models.py`, new `src/lado/server/model_entries.py`; `web/src/Settings.tsx`,
  new `web/src/ModelSettings.tsx`, `web/src/api.ts`, `web/src/paths.ts`,
  `web/src/styles.css`; `web/openapi.json` and `web/src/api.gen.ts` regenerated.
- Docs: `docs/design/ui.md` (Settings' list of sections, a section Models),
  `docs/design/modules.md` (`server/model_entries.py`), AGENTS.md's line of `server/`,
  CHANGELOG.md (0.45.0, New). `docs/cli.md` unchanged: no command changes.
- Tests: unit (`tests/test_model_settings.py`, `tests/test_model_servers.py`, new
  `tests/test_server_model_settings.py`), vitest (`web/src/ModelSettings.test.tsx`),
  integration (new `tests/integration/test_model_settings_canary.py`), UI e2e (new
  `tests/ui/test_models_section.py`, `tests/fake_model_server.py`).
- No schema change, no provider behaviour change, no CLI change. Minor release (a feature):
  0.45.0.
