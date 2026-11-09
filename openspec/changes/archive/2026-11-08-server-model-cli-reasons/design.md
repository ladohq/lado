## Context

Built on PR #256's Settings → Model servers (`web/src/ModelSources.tsx`, `SourceBody`). An open
server reads its models by a probe; the answer is `ProbeInfo` (`server/model_entries.probe_info`),
whose `clis` are the CLIs the server suits (`model_servers.suiting`), filtered in the page by
the CLIs installed here (`installed`, from `/api/providers`). The list under a model and the
Model id form both use those columns.

## Decisions

- **D1. The core says why, the page never makes a reason.** `model_servers.Probe.cannot()`
  returns `(provider, why)` for each CLI of `suiting(...)[1]`, in the registry's order: the
  provider's `refuses_server(kind)` when the server has its API and the provider refuses the
  type; else `its <API> did not answer in time` when the API is in `late`; else `it has no
  <API>`. Each why is the end of a sentence, as `refuses_server` already is. `Probe.refused()`
  stays for `cli_notes`. Why: one place decides suitability (`suiting`), the reasons sit next
  to it, and the CLI and the UI cannot drift on which CLI is out.
- **D2. A new field, the old ones unchanged.** `ProbeInfo.cannot: list[CliCannot]`, `CliCannot =
  {name, title, why}`. `clis` (what can be ticked, and the Model id form's columns) and
  `cli_notes` (the Add form's warnings) stay. Why: no consumer of the old fields changes, and
  the page needs the name to place the CLI and the title to show it.
- **D3. `not installed` is the page's, from `/api/providers`.** Installation is a fact of this
  machine the page already reads (`installed`); the probe knows only the server. A CLI out for
  both reasons shows the server's why, which installing would not cure.
- **D4. The order is LADO's order of the CLIs.** The page merges `clis` and `cannot` by the
  order of the rows of `/api/providers` (`props.logins`, the registry's order), a CLI it does
  not find there last. Why: the ticks keep the places the human knows from Agent CLIs, and the
  core's two lists are each in that order already.
- **D5. A CLI that cannot is a disabled tick, not a text line.** Same row as a tickable one
  (`mx-sub-item`), the checkbox `disabled`, the title muted, the reason in the place of `as` /
  `would be` (`mx-as`). `would be` is asked of the core only for the tickable CLIs, as today.
  Why: the human's eye finds the CLI where it looks for the tick; a disabled checkbox reads as
  "not possible here" without a new element (mock-up `mockup-cli-reasons.html`, variant 1).
- **D6. A server no installed CLI can use opens its models.** Today such rows are plain and do
  not open; now they open to the list, all disabled, so the reason can be read.
  `No installed CLI can use this server.` stays above the list.
- **D7. The CLI's text output stays.** `model_servers.lines` keeps `not: <CLI> (no <API>)`;
  the commands' output and its spec (model-servers) do not change.

## Tests by layer (AGENTS.md, Testing)

- Unit (pytest): `Probe.cannot()` for a type refusal, a missing API and a late API, in the
  registry's order; `probe_info` fills `cannot`; the server's probe endpoint answers it.
- Unit (vitest, `ModelSources.test.tsx`): the order of the list, the disabled ticks with their
  reasons, `not installed`, the server no installed CLI can use, and that `would be` is not
  asked for a disabled CLI.
- UI e2e (`tests/ui/test_models_section.py`, marker `ui`): an LM Studio server (fake endpoint)
  opens a model and shows Codex CLI disabled with its reason; screenshot.
- No integration test: nothing crosses processes beyond the server's HTTP answer, which the
  UI e2e covers.
