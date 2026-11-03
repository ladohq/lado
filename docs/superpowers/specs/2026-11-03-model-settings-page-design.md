# Settings → Models: sources and ticked models — design

Task LAD-187. The change: `openspec/changes/model-settings-page/` (proposal, delta specs
`model-settings-page` and `model-servers`, design.md D1-D14). The approved shape: option B
of the epic's artifact `ux-models-cases` (17 cases) and the human's answers #2875 and
#2890. The mock-up: the run's artifact `mockup-models-sources.html`.

## What the human sees

```
Models
┌ Your models ──────────────────────────────────────────────────────────┐
│ Name                    CLI          Model       Source               │
│ Claude Sonnet ✎         Claude Code  sonnet      Claude Code  [Remove]│
│ qwen3-8b · LiteLLM ✎    OpenCode     qwen3-8b    LiteLLM      [Remove]│
│ mistral-7b · LiteLLM ✎  OpenCode     mistral-7b  LiteLLM ⚠ not in LiteLLM's list │
└───────────────────────────────────────────────────────────────────────┘
┌ Sources ──────────────────────────────────────────────────────────────┐
│ ▸ Claude Code  CLI  logged in                                          │
│ ▸ Codex CLI    CLI  logged in                                          │
│ ▸ Kilo CLI     CLI  not installed           (greyed)                   │
│ ▾ LiteLLM  OpenAI-compatible  http://10.0.0.5:4000  [↻ Refresh][Change][Remove] │
│   [Search 6 models]                                                    │
│   Model                     OpenCode  Codex CLI  Claude Code           │
│   mistral-7b ⚠ not in the server's list   [x]   [ ]   [ ]             │
│   qwen3-8b                               [x]   [ ]   [ ]               │
│   text-embedding-… (embeddings)          (greyed, no tick)             │
│   Other model… [__________] CLI [OpenCode] [Add]                        │
│ [+ Add server]                                                         │
└───────────────────────────────────────────────────────────────────────┘
```

(A map of the parts; the look is the mock-up's.)

- **First open** (case 1): Your models says `No models yet. Without them each agent runs on
  its CLI's default model. Tick models in Sources below.`; Sources lists every LADO CLI
  (not installed greyed, not logged in marked) and the saved servers, all closed. Nothing
  is asked.
- **A source opened** reads its list now (`reading the models…`), Refresh reads again: a
  CLI's aliases and own list; a server's by a probe with its kept key. A tick per model and
  CLI: one for a CLI; for a server a column per installed CLI whose API it proves. Ticking
  saves a model with its default name, unticking removes it (cases 2, 3, 5, 6, 13).
- **Default names**: `Claude Sonnet` (an alias: the CLI title's first word and the alias),
  `gpt-5-codex` (a CLI's own list), `qwen3-8b · LiteLLM` (a server); taken → `· Codex CLI`,
  then `(2)`. Renamed in place with ✎ (case 12).
- **Long lists, embeddings, gone models, silent servers**: search above more than ten
  models; embeddings greyed, not tickable; a saved model the read list lacks shows first,
  ticked, marked, and in Your models with a warning, never removed by itself; a server that
  does not answer says why (the container's hint too) and its models stay (cases 7, 8, 10).
- **Other model…** in each source: a model the list lacks, the launch window's live check
  under it, Add (case 11).
- **Servers**: + Add server (Name, Address, Key in the dots field), probed as `lado
  model-server add`; the new server shows open with `Saved model server "<name>".`, `same
  address as …`, the plain-http warning under Key (case 4). Change: Address and New key,
  empty keeps the key (case 9). Remove: `Remove LiteLLM and its 3 models: …?`, then the
  server goes with its models (case 14).
- **CLI not logged in / not installed** (cases 15, 16): the source is marked; a model of a
  CLI not installed shows `<CLI> is not installed` in Your models.
- **Refusals** are the commands' lines under the field they concern, in the launch window's
  note look. At phone width the forms stack; a wide list scrolls inside itself.

## After the human's UI remarks (#2949, #2950, #2969)

The built page met twelve remarks; the human asked for a clickable mock-up first (the
run's artifact `mockup-models-clickable.html`) and took 1A, 2A, 3A: a model keeps its CLI,
Model id only where a list is not whole, embeddings hidden. The page becomes:

```
Models
[Your models 5] [Add models]
 ┌ Claude Code 1 ─────────────────────────────────────────────┐
 │ Name (click)       Model        From                      × │
 │ Claude Sonnet      sonnet       the CLI itself            × │
 └────────────────────────────────────────────────────────────┘
 ┌ OpenCode 2 ────────────────────────────────────────────────┐
 │ Removed mistral-7b · LiteLLM · OpenCode. Undo   (10 s)      │
 │ qwen3-8b · LM Studio · OpenCode  qwen3-8b  LM Studio      × │
 └────────────────────────────────────────────────────────────┘
 ┌ Kilo CLI 0 ── No models: its agents run on Kilo CLI's default model. Add from Kilo CLI

[Add models]
 [▶] Claude Code  CLI  1 added · logged in
 [▼] Kilo CLI     CLI  logged in
     [Search 323 models]                                         ↻
     ┌ ☑ qwen/qwen3-8b                           added ┐  ≤ 9 rows, scrolls inside
     └ ☐ anthropic/claude-3.5-haiku …                  ┘
     323 models · the ones you added are at the top
 [▼] LM Studio  LM Studio  2 added · http://localhost:1234        ✎ 🗑
     [Search 12 models]                                          ↻
     qwen3-8b               in OpenCode, Kilo CLI   [CLIs ▾]
       ☑ OpenCode  ☑ Kilo CLI  ☐ Codex CLI  ☐ Claude Code   [Done]   (one under the other)
     qwen3-coder-30b…                               [+ Add ▾]
     1 embeddings model hidden: agents cannot run on it.
 [▶] LiteLLM  LiteLLM  https://litellm-gateway.platform.inte…    ✎ 🗑
 [+ Add server]  → Name · Address (checked as typed) · Key (sent on Check key / Add)
```

Each remark and its answer: D16 of design.md. At gate #244 the human took the tabs and
remarked on the rest (#2983); the second round (#2984) took a card per CLI and a server
model's list of CLIs under its row.

## Root cause and options

The store and its rules (`model_settings.py`) have no API, and the UI has no place for the
human's model settings: by "only what is used", the previous change left both to this one.

- **A:** explicit entries through forms, ready-made chips. The human picks every name; new
  models on a server stay unseen. The first design; replaced by the human's choice.
- **B (taken):** sources read when opened, ticks are entries. Cost: a probe per opening, a
  naming rule, ticks derived from entries.
- **C:** no entries. Loses the names the power tables and roles refer to.

Where the rules live: a thin API over the core, each refusal marked with its field (taken);
an API with its own checks and texts (drifts); the browser probing (the key leaves LADO).

## Held against the roadmap and the design principles

- **Coming work.** The launch window and `lado start --model <name>` pick configured models
  from `GET /api/model-settings`; they add `models.id` and refer by it (D8), so a rename
  never breaks a reference. Effort and power tables add to the same entries and page.
- **Neutral core.** No route or component names a provider; an alias's name comes from the
  CLI's title and its provider's own alias list; the columns of a server come from the
  APIs it proves and each provider's `server_api`.
- **One source of truth.** Rules and texts are `model_settings.py`'s; the live check is
  `check_model`, which `add_model` runs; a refusal's field is set where it is raised; a
  tick is derived from the entries; the default name is one function.
- **No silent drops.** A model gone from its server is marked, never removed by itself; a
  server that does not answer says why; doctor names a gone model; a refusal shows under a
  field or the tick's row.
- **Only what is used.** No id column until a reference needs it; no "new" mark; no chips;
  no rename in the CLI.
- **The key.** In through the body of one POST, out never (D9), the canary.

## Decisions (design.md)

D1 the API · D2 a refusal's field · D3 `check_model` · D4 the default name · D5 lists read
now, a probe kept a minute for the live check · D6 ticks derived from the entries · D7 a
server removed with its models, `--with-models` · D8 rename without an id now, the id with
the first reference · D9 the key's way in · D10 warnings and notes · D11 the probe's why ·
D12 doctor's gone model · D13 the page's components · D14 the tests.

## Test layers per requirement

| Requirement | Layer | Why that layer |
|---|---|---|
| Nothing moves under the pointer | UI e2e (`scrollY` and the element's top before and after) | layout, real scrolling |
| The form checks the server as the human types | unit (the check route, no key unless sent) + vitest (debounce, stale answers dropped, Add on/off) + UI e2e | |
| A source's list keeps its height; embeddings hidden | vitest + UI e2e (323 models) | |
| A server's model opens its CLIs; Your models by CLI; one panel at a time | vitest + UI e2e | |
| A model id only where the list is not whole | vitest (`models === null`) + unit (`ProbeInfo.kind`) | |
| Settings has a section Models; Your models without a model | vitest + UI e2e | DOM order, scroll |
| Opening the section reads no list | unit (routes: the fake server's request record; no CLI list read) + vitest (no read before opening) | |
| The sources | vitest (installed/login from `/api/providers*`) + UI e2e | |
| Opening a source reads its list now | unit (`fresh`, the probe route) + vitest + UI e2e (Refresh shows a model added to the fake) | |
| A tick is a configured model; a tick of several models | vitest (ticks from entries, POST/DELETE) + UI e2e | |
| A model's default name | unit (`default_name`) | pure rule |
| Search; embeddings; a model its source no longer lists; a server that does not answer | vitest + UI e2e (the fake's `lmstudio` profile, a closed port) | |
| Other model | unit (`check_model`, kept probe) + vitest (debounce, note) | |
| The table of Your models; renaming | unit (`rename_model`, routes) + vitest + UI e2e | |
| The page adds a server; same address and plain http; refusals under fields | unit (routes, fields) + vitest (placement) + UI e2e | |
| The notes look as the launch window's | vitest (classes) + UI e2e screenshots | |
| Change | unit (`replace`, key kept on `null`) + vitest (empty New key → `null`) | |
| Removing a server removes its models | unit (state transaction, routes) + vitest + UI e2e | |
| model-servers: `--with-models`, the hint | unit (`tests/test_cli_model_server.py`) + integration (`test_model_settings_process.py`) | the real command |
| model-servers: doctor's gone model | unit (`tests/test_doctor.py`) | fake server in-process |
| model-servers: why only with no list | unit (`tests/test_model_servers.py`) | |
| The key enters the API and never leaves it | integration canary + unit (422) | crosses processes |
| The page keeps the key only in its field | vitest | |
| The section fits a phone | UI e2e at 390 px | layout |
| Without the page everything is as before | regression run | unchanged behaviour |

The plan with each task's tests: `docs/superpowers/plans/2026-11-03-model-settings-page.md`.
