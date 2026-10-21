Task: LAD-122

## Why

Symptom: in the window's Resume mode (Resume session) a provider refusal shows under
Provider as a red panel ("unknown provider <name>", or "<detail>; <install hint>" for a
CLI that is not installed, or the providers list's load error), yet the Resume session
button stays on. The human presses it and the resume is refused only after the press.
The New session window keeps Start off in the same case (LAD-120, capability
`launch-notes`, requirement "Start is off while a refusal shows under the fields"), so
the two modes of one window disagree. Found in the review of LAD-120 (finding F1).

Root cause (main, a4762ec): `ready` in `web/src/Launch.tsx` (the condition of the
submit button) is

```ts
(resuming !== null || ((current?.ok ?? false) && providerInfo?.installed === true)) &&
kits.length > 0 && !promptOver
```

In Resume mode the first term is true at once, so the provider's state is never asked.
`ProviderNote` shows a refusal exactly when `providerInfo?.installed === true` fails
(the list failed, the chosen name is not in the list, or its CLI is not installed), so
the provider part of the condition belongs to both modes; only the folder part
(`current?.ok`) is New-session-only, as Resume does not check its folder.

## What Changes

- **Resume session is off while the provider refuses**: in Resume mode the button needs
  the chosen provider to be listed and installed, as Start does in a new session. Picking
  an installed provider turns it on again; nothing else of the window changes.
- `docs/design/ui.md`: the three-levels paragraph names Resume session among the buttons
  that are off while a refusal shows.
- CHANGELOG.md, `## 0.42.1 (unreleased)`, Fixed: one line.

A patch: a fix of the web UI only.

## Scope

`web/src/Launch.tsx` (the `ready` condition), its unit test `web/src/Launch.test.tsx`, a
UI e2e test in `tests/ui/test_launch.py`, `docs/design/ui.md`, CHANGELOG.md, the delta of
`launch-notes`.

## Out of scope

- The server's resume (`POST /api/sessions/{name}/resume`): it already refuses a provider
  that cannot run, and that refusal still shows if the provider breaks between the
  window's check and the press.
- A look change: the refusal panel stays as LAD-120 made it; no mockup is needed.
- One window-wide "a refusal shows" flag derived from the rendered notes: it would cover
  future refusals by construction, but needs every note's condition lifted out of its
  component, a refactor larger than this defect; the next step of the epic LAD-116 (S3)
  adds its refusal to the same `ready` and the delta's rule names the duty.
- The folder check in Resume mode: Resume does not check its folder (Where is fixed), so
  no folder refusal can show there.

## Impact

- `web/src/Launch.tsx`, `web/src/Launch.test.tsx`, `tests/ui/test_launch.py`.
- `docs/design/ui.md`, CHANGELOG.md.
- Modified capability spec `launch-notes`.
- No change to the API, the MCP tools, the CLI or the schema.
