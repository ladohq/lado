Task: LAD-241

## Why

On Settings → Model servers, a server's model opens a list of the agent CLIs that can run it,
a tick each. A CLI that cannot use the server is simply not there: on LM Studio, Codex CLI is
missing, with all four CLIs installed and logged in, and nothing says why. The human cannot
tell a defect from a limit.

Cause: the list under a model is `ProbeInfo.clis` filtered by the CLIs installed here. The
core knows why each other CLI is out (`model_servers.suiting` and `Provider.refuses_server`:
LM Studio's Responses API loses Codex CLI's MCP tools), but `ProbeInfo` carries only the type
refusals (`cli_notes`), and only the Add form's check (`Found`) shows them. A CLI out for want
of its API, or one not installed, has no line anywhere on the page.

Options weighed:

- A (taken): every agent CLI LADO knows stays in the list under a model, in LADO's order; one
  that cannot use the server has its tick off and disabled and, in place of `as <name>` /
  `would be <name>`, `cannot use this server: <why>` or `not installed`. The reason sits where
  the human looks for the tick. Long-term cost: one more field of `ProbeInfo`, one branch of
  the list.
- B: one line per CLI once per server, above its models. Fewer repeated lines, but far from
  the tick; the human who opens a model still sees the CLI missing. The human chose A.
- C: only the type refusals (`cli_notes` as they are). Cheapest, but leaves two silent drops
  (no API, not installed), against AGENTS.md's "No silent drops". The human chose all three.

## What Changes

- The core: `model_servers.Probe.cannot()` gives each agent CLI that cannot use the server,
  with why as the end of a sentence: the provider's own refusal of the type (Codex CLI on LM
  Studio), `it has no <API>`, or `its <API> did not answer in time`.
- The API: `ProbeInfo` gains `cannot`, a list of `{name, title, why}` in LADO's order of the
  CLIs; `clis` and `cli_notes` stay as they are.
- The UI: the list under a server's model shows every agent CLI in LADO's order. One the
  server suits and installed: a tick as today. One the server does not suit: the tick off and
  disabled, the title muted, under it `cannot use this server: <why>`. One the server suits
  but not installed here: the same, with `not installed`. A server no installed CLI can use
  still says `No installed CLI can use this server.`, and its models now open to show why.

## Scope

- The list under a server's model on Settings → Model servers (PR #256's page).
- The probe's API (`ProbeInfo.cannot`), the core's `Probe.cannot()`.
- `docs/design/ui.md`, CHANGELOG.md.

## Out of scope

- The CLI's `lado model-server add` / `probe` output (`not: <CLI> (<why>)`): it already says
  why for every CLI; its wording stays, so no command's output changes.
- The Add form's check (`Found`) and `cli_notes`: it already names the type refusals, and the
  CLIs the server lacks the API for are named there by `none can use it` and the list; not
  asked for.
- The Model id form under a server without a whole list: it offers only the CLIs that can
  save a model there, and a refusal there already says why (`<server> does not suit <CLI>`).
- Making Codex CLI work on LM Studio: a limit of LM Studio's Responses API, not of LADO.

## Acceptance

- AC-1: On LM Studio (chat completions and the Responses API), with all four CLIs installed,
  the list under a model shows Claude Code, Codex CLI, OpenCode, Kilo CLI in LADO's order;
  Codex CLI's tick is off and disabled, and under it `cannot use this server: its Responses
  API loses Codex CLI's MCP tools, so the agent could not talk to LADO`.
- AC-2: On a server without the Anthropic Messages API, Claude Code's tick is off and
  disabled with `cannot use this server: it has no Anthropic Messages API`; when that API did
  not answer in time, `cannot use this server: its Anthropic Messages API did not answer in
  time`.
- AC-3: A CLI the server suits but not installed here shows its tick off and disabled with
  `not installed`.
- AC-4: A server no installed CLI can use says `No installed CLI can use this server.`, and
  its models open to the list of CLIs with the reasons, none of them tickable.
- AC-5: Ticking and unticking the CLIs that can use the server work as before (names, Undo-less
  untick, the default's confirmation).
- AC-6: `lado model-server add` and `lado model-server probe` print what they print today.

## Impact

- `src/lado/model_servers.py`, `src/lado/server/models.py`, `src/lado/server/model_entries.py`
- `web/src/ModelSources.tsx`, `web/src/styles.css`, `web/src/modelFakes.ts`,
  `web/openapi.json`, `web/src/api.gen.ts`
- Tests: `tests/test_model_servers.py` (or the probe's unit tests), `tests/test_server_model_settings.py`,
  `web/src/ModelSources.test.tsx`, `tests/ui/test_models_section.py`
- `docs/design/ui.md`, CHANGELOG.md
- Version: patch (a fix of what the page says; no MCP tool, CLI or schema change). It lands
  under the unreleased heading PR #256 leaves.
- Depends on PR #256 (LAD-238, `feature/lad-238-settings-pages`): it builds on that branch's
  Model servers page, so the build starts after main has it.
