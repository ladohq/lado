# Settings as pages, default models with the CLIs, Help on the rail (LAD-238)

Change: `openspec/changes/settings-pages/` (proposal with AC-1..AC-9, new capabilities
`settings-pages` and `rail-help`, deltas of ten others, `design.md` with D1-D14). This document
is the human's view. Sources of the look, in this order (a later one wins): run artifacts
`r3-models-spec` and `r3-models-brief`, `r4-concise-spec` and `r4-concise-brief`, the r5 spec
and brief attached to LAD-238 (`settings-spec.md`, `settings-brief.md`), `r5-design-system`,
`r5-mockup.html` (frames 1-15; 16 is later), and `mockup-help.html` (frames 1-7) for the rail.
Decided with the human: question #4821 (all six answers as recommended).

## What a user gets

    LADO rail          | Settings                                            ● live
      Home             |
      …                |  ⚙ General          Agent CLIs  ↻
                       |  ▣ Agent CLIs       Changes apply to agents started afterwards.
      ─────────        |  ☰ Model servers    ─────────────────────────────────────────
      (?) Help         |  ⛨ Statistics       Claude Code 2.1.40                [Log in…]
      ⚙ Settings       |                     ◆ Not logged in
                       |                     developer of checkout-redesign waits; it starts once you log in.
                       |                     Default model  [Claude Code's settings     ▾]
                       |                     ─────────────────────────────────────────

- Settings is four short pages beside a list of their names and icons. A phone shows the list,
  then a page with `‹ Settings`.
- A CLI's row says whether it can start (its login, one button) and what it runs (Default
  model). Needs you and New session send the human straight to that row, the login button
  focused.
- Model servers holds the servers and one table of the human's models, the default of a CLI
  marked.
- The rail's Settings is a cogwheel; Help opens Documentation, GitHub and Report a bug.

## Pages

| Address | Heading | Content |
|---|---|---|
| `/settings` | — | computer, tablet: General; phone: the list alone |
| `/settings/general` | General | rows Theme (System, Light, Dark) and Browser notifications (switch), `#notifications` its row |
| `/settings/agent-clis` | Agent CLIs ↻ | lede, a row per CLI with login and Default model, the login-shell line; `#<cli>` arrival |
| `/settings/model-servers` | Model servers | Servers `<n>` with Add server; Your models `<n>` |
| `/settings/statistics` | Statistics | one row, Send / Don't send |

Old addresses (replaced, Back does not loop): `#providers-and-environment`,
`/settings/agent-clis-and-environment` → Agent CLIs; `#models`, `/settings/models` → Model
servers; `#statistics`, `/settings/usage-statistics` → Statistics; `#notifications` →
`/settings/general#notifications`; `#appearance` → General; `/settings/<unknown>` → `/settings`.

## Words, exactly

New or changed, all others as today:

| Where | Text |
|---|---|
| List | `General`, `Agent CLIs`, `Model servers`, `Statistics`; no state line |
| Phone back link | `‹ Settings` |
| General · notifications | `Browser notifications` / `When something waits for you and this tab is hidden.` |
| Refusals (General and Needs you) | `Blocked by the browser: allow them in the site settings (icon left of the address), then switch on again.` · `Needs a secure page: open LADO at 127.0.0.1 or localhost.` · `Not supported by this browser.` · `Not allowed: switch on again and allow them.` · `The browser asks again: switch on and allow them.` |
| Agent CLIs · lede | `Changes apply to agents started afterwards.` |
| … untested | `LADO tested 0.58.0` (`--warn`) |
| … waiting | `<agent> of <session> waits; it starts once you log in.` / `… wait; they start once you log in.` |
| … none installed | `No agent CLI installed. Install one to start a session.` |
| … login shell | `Couldn't read your login shell: <why>. Details: lado doctor` |
| … server unreachable | `Could not reach the LADO server: <why>` then `Not checked yet. Press ↻ to try again.` |
| … label | `Default model` (visible, `aria-hidden`; picker `aria-label="Default model of <CLI>"`) |
| … not installed with a default | `Default model: <name> — cannot run: not installed` + `Use <CLI>'s settings` |
| … no servers | `Models of your own come from a model server: Model servers` (link) |
| Model servers · Servers lead | `Any OpenAI-compatible server: LM Studio, Ollama, vLLM, LiteLLM.` |
| … Your models lead | `Pick one as a default in Agent CLIs.` (link) |
| … none ticked | `None yet: open a server and tick the agent CLIs that run a model.` |
| … a default | Agent CLI cell `<CLI> · default` |
| … default in trouble | `⚠ <server> does not answer (<why>). Start it or pick another model.` |
| … source down | `⚠ Does not answer (<why>)` + `Its models stay saved; agents on them stop at their first turn until it answers.` |
| … ticks | `Agent CLIs that run <model>:` |
| … key | `Only LADO reads it; never shown again.` |
| Statistics · row | `Send anonymous statistics and errors to LADO's maintainers` |
| … states | `Nothing is sent until you choose.` · `Last sent <when>.` / `Not sent yet.` · `Nothing is sent.` each + `What LADO collects ↗`; `Off: <VAR> is set in the server's environment.`; `No statistics endpoint: nothing is sent.` |
| New session · picker foot | `The default comes from Settings → Agent CLIs.` → `/settings/agent-clis`, new tab |
| … model note | `<CLI>'s default model, from Settings → Agent CLIs.` |
| … lost model | `… which is no longer in Settings → Model servers. Pick a model or use <CLI>'s settings.` |
| Server refusals, `lado doctor` | `Settings → Agent CLIs` in place of `Settings → Agent CLIs and environment` |
| `lado model default` | `… rename the saved one: Settings → Model servers` |
| Rail | `Help` (menu `Documentation ↗`, `GitHub ↗`, line, `Report a bug`), `Settings` |

## Width by width

| | Phone 390 | Tablet 768 | Computer 1440 |
|---|---|---|---|
| List | the page itself; rows 52 px, icon 22, chevron | 196 px beside the page | 232 px, sticky |
| Agent CLIs row | text, button (44 px), `Default model`, picker full width (44 px), notes | text left, button right; label 104 px + picker up to 360 px | as tablet |
| Your models | name + × 44 px, then `id · server · CLI` | name + × 32 px, line under | five columns |
| Help | in the drawer, its menu above it across the drawer, items 44 px | menu right of the rail | as tablet |

No sideways scroll at any width; no picked model's name cut (its id gives way first).

## Rail

Help replaces Report a bug above Settings; Settings stays last. The menu opens beside the rail,
its bottom on Help's; the first item focused, ↑/↓ move, Esc closes and gives the focus back to
Help, a press outside closes. On `/report` Help has the current stripe. The folded rail shows
Help's icon with the tooltip `Help`. The system panel keeps its GitHub icon.

## Not now

Groups (from six sections) and Find a setting (from eight), Documentation in the Settings list,
a tab title per section, the note after a server's removal that a default went with it.

## Version

A feature: under `## 0.45.0 (unreleased)`, which already bumps the minor. No API, schema, MCP or
CLI option change.
