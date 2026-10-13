# Usage statistics and LADO's own errors: design

Task: LAD-32. Change: `openspec/changes/usage-telemetry/`. Mockup: run artifact
`task/lad-32/mockup-consent.html` (screens 1A, 2, 3, 4 approved; 1B rejected). Research:
run artifact `task/lad-32/research.md`.

## Problem

The maintainer wants to know how many people use LADO, which versions run, and which
errors happen most, to prioritise tasks. Today LADO's unexpected exceptions go to four
unrelated logs, without a version, or nowhere (a CLI command's traceback, an MCP tool's
"Error executing tool"). Nothing reaches the maintainers.

## What the user sees after the change

**The question (once).** While no choice is made, the web UI shows a banner under the top
bar on every page:

> **Help improve LADO?**
> Send anonymous usage statistics and LADO's own errors to its maintainers: the LADO
> version, your OS, the agent CLIs and daily counts of sessions, agents and runs; for an
> error, its type and where in LADO it happened. Never paths, repository or session
> names, messages, prompts or keys.
> Nothing is sent until you choose. You can change it any time in Settings or with
> `lado telemetry off`.
> ▸ What is sent
> [Send statistics] [Don't send]  What LADO collects ↗

`lado start` and `lado ui` in a terminal ask the same on stderr before they start:

```
LADO can send anonymous usage statistics and its own errors to its maintainers,
so they see how many people use it, which versions run and which errors to fix first.
Never paths, repository or session names, messages, prompts or keys.
See what is sent: lado telemetry show · https://github.com/ladohq/lado/blob/main/docs/telemetry.md
Send them? [y/N]
```

`y` prints `statistics: on (lado telemetry off to stop)`, Enter or `n` prints
`statistics: off`. With no terminal, inside an agent, with `DO_NOT_TRACK=1` or
`LADO_TELEMETRY=0`, or in a LADO without a statistics endpoint, nothing is asked.

**Afterwards.** Settings → Usage statistics (last section) has Send / Don't send and one
line of state: `Last sent today at 09:12 · What the next report sends · What LADO
collects ↗`, `Not chosen yet: nothing is sent.`, or, disabled, `Off: DO_NOT_TRACK=1 is
set in the LADO server's environment.` The System panel has a row `Statistics` (`sending ·
last today 09:12`, `off`, `not chosen`, `off: DO_NOT_TRACK=1`) linking to Settings, and
"Copy system info" adds `- Statistics: on`.

`lado telemetry`:

```
$ lado telemetry status
statistics: on (chosen 2026-10-13)
last sent: 2026-10-13 09:12 · waiting: 0 reports, 1 error
$ DO_NOT_TRACK=1 lado telemetry status
statistics: off: DO_NOT_TRACK=1 is set (your choice: on)
$ lado telemetry show          # the exact JSON of the next send, the token left out
$ lado telemetry on|off        # refused inside an agent
```

When a later LADO adds a kind of data, the question comes again and names it.

**Locally, always**, whatever the choice: `LADO_HOME/errors.jsonl` keeps each unexpected
exception of any LADO process, with its version and traceback. It and `hooks.log`,
`loop.log` and `server.log` stay under 1 MiB plus one rotated `.1` file.

**When PostHog cannot be reached** (no network, DNS, proxy, TLS, a firewall or a block
by region, a timeout, an error answer), and the same for any other endpoint: the user
notices nothing. No command, hook, tool, loop pass or UI request waits for the network
or prints an error about it; only the detached sender tries, 2 s per network operation,
ended after 30 s whatever happens (DNS included), at most every 15 minutes. What waits
stays bounded (200 errors, then only counted; one report whose window grows). `lado
telemetry status` and the Settings line say `last try failed: <reason>`; once the
endpoint answers again, one report and the grouped errors go out.

**What LADO keeps on disk.** Statistics are not collected: the daily report is counted
from `lado.db` when it is sent and never stored, so nothing grows with use. What waits
to be sent: at most 200 errors (a few hundred bytes each), none older than 30 days, and a
report window of at most 30 days. Logs: `errors.jsonl`, `hooks.log`, `loop.log`,
`server.log` at most 1 MiB each plus one `.1` (`server.log` also while a server runs for
weeks). At worst about 9 MiB.

**The PostHog parameter.** LADO needs the **Project token** (`phc_…`, Project settings →
General), not the Project ID. It goes into `telemetry.PROJECT_TOKEN`; it is public by
design.

## What is sent, and where

PostHog Cloud EU (`https://eu.i.posthog.com/batch/`), with no person profiles and no
GeoIP. The project's "Discard client IP data" setting is on. Two events:

- `lado_daily`, at most once a day while LADO is used:

  ```json
  {"install": "6b0e1f2a-…", "lado": "0.37.0", "python": "3.13.1", "os": "darwin",
   "arch": "arm64", "installer": "uv tool",
   "providers": {"claude": "2.1.296", "codex": "0.162.0"},
   "kits": {"named": ["default", "sdlc"], "other": 1},
   "since": "2026-10-12T09:12:00Z", "sessions": 3, "agents": {"claude": 7},
   "runs": 2, "gates": 4, "turn_errors": 1, "lado_errors": 0, "errors_dropped": 0}
  ```

- `$exception`, one per kind of error since the last send:

  ```json
  {"type": "KeyError", "chain": [], "where": "hook:turn_end", "provider": "codex",
   "stack": ["lado/hooks.py:main:276", "lado/hooks.py:handle:212",
             "lado/runtime.py:hand_over:1840", "<external>"],
   "fingerprint": "9c1d…", "count": 3, "first_at": "…", "last_at": "…", "lado": "0.37.0"}
  ```

The list is `telemetry.FIELDS` (version 1), and `docs/telemetry.md` lists the same; a test
keeps them equal.

## How it works

See `openspec/changes/usage-telemetry/design.md` D1–D14. In short:

- `telemetry.record` writes the journal line and, when sending is on, a scrubbed event
  into `LADO_HOME/telemetry/outbox/`. It is called from the five capture points: the
  CLI, hooks, MCP tools, the loop and the server.
- `telemetry.kick` starts a detached `lado telemetry send` when something is due. It is
  called by the CLI after a human's command, by the loop every 10 minutes, and by the
  server at its start and every 10 minutes. A hook never sends.
- The sender runs under a flock. It builds the daily report from `lado.db` at send time,
  groups the outbox by fingerprint, and posts one batch (2 s per network operation, the process ended after 30 s). On failure
  it keeps everything and tries again after 15 minutes.

## Tests

| Requirement | Layer | Where |
|---|---|---|
| journal line per process, refusals excluded, bounds | unit | `tests/test_telemetry.py`, `test_cli.py`, `test_runtime.py` (the hook's tests), `test_mcp_server.py`, `test_loop.py`, `test_server_system.py` |
| a failing hook's line and queued event across processes | integration | `tests/integration/test_telemetry_processes.py` |
| consent, environment, endpoint, fields version | unit | `tests/test_telemetry.py` |
| the CLI question and `lado telemetry` | unit | `tests/test_cli_telemetry.py` |
| scrubbing (path, name, token never in an event) | unit | `tests/test_telemetry.py` |
| sender: lock, batch, grouping, failure keeps, retry gap, report window | unit, local HTTP server | `tests/test_telemetry.py` |
| unreachable endpoint: refused port, 403, a server that never answers, a hanging DNS (monkeypatched `getaddrinfo`), a TLS error; CLI command unaffected and silent | unit; integration for `lado start` with an unreachable `LADO_TELEMETRY_URL` | `tests/test_telemetry.py`, `tests/integration/test_telemetry_processes.py` |
| the loop's kick reaches a local endpoint | integration | `tests/integration/test_telemetry_processes.py` |
| API and SystemInfo/report line | unit (test client) | `tests/test_server_system.py`, `tests/test_doctor.py` |
| banner, Settings section, panel row | vitest | `web/src/Telemetry.test.tsx`, `SystemPanel.test.tsx` |
| banner → Send → Settings, screenshots | UI e2e | `tests/ui/test_statistics.py` |
| docs list = `FIELDS` | unit | `tests/test_telemetry.py` |

Regression run before review: `make lint`, `make test`, `uv run pytest -m integration -n
auto tests/integration/test_telemetry_processes.py` plus the integration files of hooks and the loop
touched, `uv run pytest -m ui tests/ui/test_statistics.py tests/ui/test_system_panel.py`,
`make web`, `openspec validate --specs --strict`. CI then runs the full `make check`.
