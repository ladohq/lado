# Providers section and agent start screens: design

Task: LAD-163. Change: `openspec/changes/providers-section-and-start-screens/` (proposal,
deltas of `provider-logins`, `claude-folder-trust` and the new `agent-start-screens`,
design.md D1-D11). Mockup: run artifact `mockup-providers.html`.

## What the human sees

**Settings → Providers and environment** (mockup, screens 1-3)

- Title "Providers and environment" with a small ↻ right after it; subtitle "Sign-ins your
  agents use. Changes apply to agents started afterwards."
- One row per agent CLI: name, version, dot and state ("Logged in · method · where",
  "Not logged in", "No login", "Couldn't check the sign-in" + why), the agents waiting for
  its login (only while it is missing), projects with their own login, the provider's note,
  one button.
- Only fixable problems: "not installed" greyed with the install hint; "LADO is tested
  with …" small by an untested version; one line over the list when no CLI is installed;
  one line under the rows when the agents' environment could not be read from the login
  shell. Nothing else of `lado doctor`: no `[ok]` lines, no "Check again".
- Opening the section shows the last result at once while ↻ turns; the rows change in
  place when the fresh check ends. The very first open after LADO started shows each row
  with "checking…" until its CLI answers. ↻, Save, Log out and a login window's end start a
  check.

**Resume window** (mockup, screen 4): as New session since LAD-161: a CLI without its login
is the disabled option "claude · not logged in" with the red note "Claude Code is not
logged in: its agents cannot start. Log in first"; Resume stays disabled until another
CLI with a login is chosen. `lado start` of a stopped session refuses with "… so the
session was not resumed: …". The resume LADO does by itself (container start, `lado
update`) still starts the supervisor, which waits for the login.

**Agents at their start** (mockup, screen 5)

- A Claude session in `bypassPermissions` no longer stops on "WARNING: Claude Code running
  in Bypass Permissions mode"; a repository's `.mcp.json` no longer stops agents on "New
  MCP server found in this project": its servers are enabled.
- Any agent that gives no sign 30 s after its CLI's launch goes to Needs you: "Waiting for
  an answer in its terminal: no sign from it 30 s after its start. Open its terminal."; once
  answered, it goes on.
- No "Warnings: LADO recorded Claude Code's trust …" box over a new session's chat; these
  lines are in loop.log only. A config LADO cannot read or write still warns.

## Facts the design rests on

The probe of Claude Code 2.1.295 on a clean config (design.md, Context): of the screens
before the first hook in all seven modes, LADO answers the first run, the API key and the
trust already; the bypass warning and the project MCP servers' screen remain, both
switched off by keys of the agent's own `--settings` file, checked by hand. Auto mode shows
an inline notice only.

"session loop not running" on the screenshot is not caused by the agent stuck on the
bypass screen: the loop starts right after the window and waits for no hook; nothing an
agent does before its first hook ends it, and the status is read anew every 3 s. It is a
separate fault on the human's Mac (its reason in `~/.lado/loop.log`), out of this change.

## How it is built

- `lado/server/provider_check.py` (D1): the last rows, one background check at a time, all
  CLIs at once, the login shell once; rows kept as each is read.
- API (D2): `POST /api/providers/check`, `GET /api/providers/logins` (`checking`,
  `environment`, per row `ready`), no `checks`.
- UI (D3, D4): `Providers.tsx` polls each second while a check runs; ↻; the rules of what a
  row shows come from the fields the server already gives (`installed`, `tested_version`,
  `warning`, the login's `problem`).
- The glitch (D5): `waiting` only while the login is not `yes`.
- Claude (D6): two keys in the agent's settings file, nothing in `.claude.json`.
- The safety net (D7): `runtime.check_starts` in the loop's pass, by `seen_at` and
  `window_at`, any provider.
- Notes (D8): logged by the core, returned to no one.
- Resume (D9): `start_session(wait_for_login=…)`, `logins.RESUME`, hidden `lado start
  --wait-for-login` for `lado update`, `Launch.tsx` without the resume exceptions.

## Questions settled

All in the human's decisions (`brief-lad-163`, questions #2053-#2069) and question #2078
of this run: the mockup, the repository's MCP servers enabled, the 30 s safety net, the
resume checked by the supervisor's CLI, the loop's fault kept out.
