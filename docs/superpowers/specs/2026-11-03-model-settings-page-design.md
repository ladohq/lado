# Settings → Models: the page of model servers and models — design

Task LAD-187. The change: `openspec/changes/model-settings-page/` (proposal, delta specs
`model-settings-page` and `model-servers`, design.md D1-D11). The approved mock-up:
the run's artifact `mockup-models-page.html`.

## What the human sees

Settings gets a section **Models** after Providers and environment and before Usage
statistics, at `/settings#models`:

```
Models
Models set once under names; sessions will refer to them by name. No session uses them yet.

┌ Your models ───────────────────────────────────────────────────────────┐
│ Name            CLI           Model      Server                         │
│ Claude Opus     Claude Code   opus       —                    [Remove]  │
│ Локальная Qwen  OpenCode      qwen3-8b   LM Studio дома       [Remove]  │
│ Ready-made for Claude Code: [+ Claude Haiku · haiku] [+ Claude Sonnet · sonnet]  Add both │
│ [+ Add model]                                                           │
└─────────────────────────────────────────────────────────────────────────┘
┌ Model servers ─────────────────────────────────────────────────────────┐
│ LM Studio дома  [LM Studio]  http://localhost:1234   [Check][Change][Remove] │
│ For: Kilo CLI, OpenCode · key: no                                        │
│ [+ Add server]                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

(The drawing is a map of the parts; the look is the mock-up's.)

- **Add server**: Name, Address, Key (optional, the dots field of a project's secrets). Add
  probes as `lado model-server add` does (`checking the server…`, up to ~10 s), then the row
  shows the probe's findings: type, address, models with `(embeddings)` marks or `no list
  (<why>)`, the CLIs that can use it and those that cannot, the key; `Saved model server
  "<name>".`; `same address as model server "<other>"` under it; the plain-http warning
  under Key.
- **A server's row** shows what was saved, asking nothing. **Check** probes with the kept
  key and shows models and CLIs, or the probe's line as a warning. **Change** opens Address
  (filled) and New key (empty keeps the kept key), as `--replace`. **Remove** asks in the
  row; a server models use is refused with the command's line naming them.
- **Add model**: Name, CLI (all LADO's CLIs, `(not installed)` marked), Server (`—` or a
  saved server), Model with suggestions (the CLI's aliases and list, or the server's models
  without its embeddings ones) and a live check under it (`✓` / `⚠` / refusal), as the
  launch window's Model field. Add saves as `lado model add`.
- **Ready-made models**: when Claude Code is installed, chips `+ Claude Haiku · haiku`,
  `+ Claude Sonnet · sonnet`, `+ Claude Opus · opus`, one click each, and `Add all three`
  (`Add both` for two); a chip goes once a Claude Code model with that alias is saved. Why
  aliases: Claude Code itself takes them and maps each to the latest model of its family,
  so the entry never goes stale and its check is always ✓; the other CLIs have no such
  names, so they get no chips.
- **Refusals** are the commands' lines, under the field they concern (Name, Address, Key,
  CLI, Server, Model), in the launch window's note look; a refusal of no field under the
  buttons. The form and its values stay; the key's field is emptied.
- At phone width the forms stack in one column and the page does not scroll sideways.

## Root cause and options

The store and its rules (`model_settings.py`) have no API, and the UI has no place for the
human's model settings: by "only what is used", the previous change left both to this one.

- **A (taken):** a thin API over `model_settings.py`, the commands' own functions; the core
  marks each refusal with its field. Long-term cost: an attribute on two exception types.
  One source of truth for rules and texts.
- **B:** the API re-implements the checks with UI words. Two rule sets that drift.
- **C:** the browser probes the server itself. The key would leave LADO's server, CORS and
  networks LADO's machine alone sees would break it, and the probe would exist twice.

## Held against the roadmap and the design principles

- **Coming work.** The next change chooses a configured model in the launch window and
  `lado start --model <name>`: it reads `GET /api/model-settings`'s list; effort and the
  power tables add fields to the same entries and the same page.
- **Neutral core.** No route or component names a provider; ready-made models are
  `Provider.ready_models`, declared by Claude Code alone today and shown for any provider
  that declares some. The page works for all four CLIs; only the chips are Claude Code's,
  said in the proposal's Out of scope.
- **One source of truth.** Every check and text is `model_settings.py`'s; the live check is
  `check_model`, the same function `add_model` runs (D3); the field of a refusal is set
  where it is raised (D2); the embeddings filter of the suggestions reads the probe's own
  `embeddings` (D10).
- **No silent drops.** Every refusal shows under a field or the buttons; warnings
  (plain-http, no list to check) show where the human looks; a chip's refusal shows under
  the chips; nothing is saved on a failed probe.
- **Only what is used.** One route per thing the page does; no rename, no edit of a model,
  no bulk removal, no change-feed event.
- **The key.** In through the body of one POST, out never (D5): the canary of LAD-116 and
  the previous change, extended to the API.

## Decisions (design.md)

D1 the API routes and models · D2 a refusal's field set by the core · D3 `check_model`, the
checks without the save · D4 a server's probe kept a minute for the Model field · D5 the
key's way in, `SECRET_ROUTE`, the empty key · D6 warnings and notes of add · D7
`Provider.ready_models` · D8 the probe's why only with no list · D9 the page's components
and reuse · D10 embeddings left out of the suggestions · D11 the tests.

## Test layers per requirement

| Requirement | Layer | Why that layer |
|---|---|---|
| Settings has a section Models; the anchor | vitest + UI e2e | the order of sections and the scroll need the DOM; e2e proves the real page |
| Opening the section asks no server | unit (`tests/test_server_model_settings.py`, the fake server's request record) | the route alone decides it |
| The page adds a server as the command does; what the probe found; same address and plain http | unit (routes against `tests/fake_model_server.py`) + UI e2e (one add) | the route's answer is unit; the rendered row needs a browser |
| A refusal is the command's line; under its field (server and model) | unit (`tests/test_model_settings.py`: each raise's `field`; the routes' `EntryRefused`) + vitest (placement) + UI e2e (one under Address, one under Server) | field set in the core, placed by the page |
| The notes look as the launch window's | vitest (classes) + UI e2e screenshot | look |
| A server's row shows what was saved; Check | unit + vitest | |
| Change replaces address or key | unit (route with `replace`, key kept on `null`) + vitest (empty New key sends `null`) | |
| Removing a server asks in its row; refused naming models | unit + UI e2e | |
| The page adds a model; the table | unit + vitest + UI e2e | |
| The Model field suggests; checks as typed | unit (`check_model`, the kept probe) + vitest (debounce, embeddings filtered) + UI e2e (suggestion from the fake server) | |
| Removing a model | unit + vitest | |
| Ready-made models; several at once; each CLI's | unit (`ready_models` are aliases; listing hides saved; installed only) + vitest + UI e2e (fake `claude` on PATH) | |
| The key enters the API and never leaves it | integration (`tests/integration/test_model_settings_canary.py`, a real `lado server`) + unit (422 on the secret route) | crosses processes: server log, journal, files |
| The page keeps the key only in its field | vitest | DOM and state |
| The section fits a phone | UI e2e at 390 px | layout |
| Without the page everything is as before | the regression run (`make test`, integration `test_session_model.py` in CI) | behaviour unchanged |
| model-servers: why only with no list | unit (`tests/test_model_servers.py`) | pure probe |

The plan with each task's tests: `docs/superpowers/plans/2026-11-03-model-settings-page.md`.
