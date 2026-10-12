## 1. README

- [ ] 1.1 Replace README.md's `## Update` section with the text in proposal.md. Check: the
  section reads as in the proposal; every command it names exists (`lado update --help`,
  `lado ls`, `lado doctor`); the UI labels match `web/src/SystemPanel.tsx` (`live`,
  `↑ X.Y.Z`, `Update…`, `Restart and update`) and the CLI line matches
  `update.available_line`'s text (`LADO X.Y.Z is available: lado update`).

## 2. docs/install.md

- [ ] 2.1 Add `## Update` between "Your first session" and "Common problems" with the
  points listed in proposal.md, in English. Check each claim against the code it
  describes: `self_update.run` (order of steps, backup path, rollback conditions,
  update.log), `self_update.refusal` and `Plan.by_hand` (the commands by hand),
  `update.check` (`CHECK_EVERY`, `LADO_NO_UPDATE_CHECK`), `cli.cmd_update` (`--yes`
  without a terminal).
- [ ] 2.2 Link the "later updates: `lado update`" mentions in docs/install.md (Windows
  step 3, Your first session, Without uv) to `#update`. Check: README's link
  `docs/install.md#update` and these anchors resolve on GitHub (the heading is exactly
  `## Update`, the only one of that name in the file).

## 3. CHANGELOG

- [ ] 3.1 One line under `## 0.36.0 (unreleased)`: README's Update section rewritten for
  users, with updating from the web UI; the details moved to docs/install.md.

## 4. Checks

- [ ] 4.1 `make lint` and `openspec validate --specs --strict` pass (nothing else runs on
  a docs-only change; CI runs the rest).
