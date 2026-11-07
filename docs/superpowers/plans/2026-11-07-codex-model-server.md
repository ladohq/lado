# Codex on a model server: Implementation Plan

**Goal:** a Codex agent runs on a server with the Responses API and LADO's tools, a refusal reads in
LADO's words, and the probe, `lado model add`, Settings and a start say the same thing.

**Architecture:** the rule of who can use a server in `providers/base.py` and `model_servers.suiting`;
the launch and the journal in `providers/codex.py`; the pass in `runtime.py` and `loop.py`, through
`hooks.handle`; the note in `server/` and `web/src/ModelSources.tsx`.

**Tech Stack:** Python 3.10+, pytest (`-n auto`, `-m integration`, `-m smoke`), vitest,
`tests/fake_model_server.py`, the fake agent.

**Spec:** `openspec/changes/codex-model-server/` and
`docs/superpowers/specs/2026-11-07-codex-model-server-design.md`.

## Global Constraints

- No new dependency. Past ~15 code files (tests aside): stop and ask. The estimate is 12.
- No schema change, no MCP tool, no CLI option, no new screen. One API field, `ProbeInfo.cli_notes`.
- Codex on a built-in model or on the user's own provider starts as today, and has no journal read: a
  test holds each. Claude Code, OpenCode and Kilo on a server work as today.
- The user's Codex config is read, never written.
- No key in a config, `models.json`, `lado.db`, output, log or error text.
- Tests never reach a real provider. A real request costs the human's money: only with their yes.
- Live tests of Claude Code only with the human's yes.
- Nothing in code, docs, specs or the UI names the epic's steps; `docs/epics/` is not touched.
- The pull request carries the manual check from the start: branch, folder, commands, expected;
  `env | grep LADO_` and `unset`; own `LADO_HOME` and `LADO_TMUX_SOCKET`; `make web`.

## Review Focus

1. A key that survives in a line, a body, an event or a log, the loop having no variable of it.
   Test: tasks 3, 4.
2. A built-in Codex agent changed by accident: its config, its login, a journal read. Test: tasks 2, 3.
3. An error told twice, or a busy agent made idle by an old error. Test: task 3.
4. A place that still promises Codex on LM Studio, or refuses it elsewhere. Test: task 1.
5. A Codex update that changes the journal or the catalogue. Test: task 4.

## Task 1: Who can use a server

Layer: unit; the form by vitest.

- `refuses_server`, `suiting(apis, kind)`: LM Studio with the Responses API has Codex under `not:` with
  why; an OpenAI-compatible server has it among the CLIs; the three other CLIs are not touched.
- `lado model add --cli codex` on LM Studio: exit 1, nothing saved, the `does not suit` line.
- `check_launch`, `blocked`, `spawn_worker`: the same words, the server not asked.
- `runs_on_server` gone: `grep -r runs_on_server src tests` is empty; `test_providers.py:2053` moves.
- `probe_info` has `cli_notes`; `Found` shows a line for it, none for an empty list.

## Task 2: The launch

Layer: unit in `tests/test_codex.py`; integration for what crosses processes.

Unit: the entry over carried `model_providers`; a carried profile; a key-less server; the key in
`Launch.env` and not in the file; `launched_on`; `needs_login`; no `auth.json` link; `web_search`; no
carried effort; `models.json` from a stubbed `codex debug models`, each overridden field; no such entry
and a failing command warn; `model_context_window` and the compact limit, none unknown; a built-in
agent's config byte for byte as before.

Integration, `tests/integration/test_codex_model_server.py`, fake agent: a session and a worker on a
fake server's model, the key in the agent's environment and in no file of `LADO_HOME` (the canary of
LAD-116), a resume on a built-in model drops everything of the server.

## Task 3: A failed turn

Layer: unit for the reading; integration for the path to the chat.

Unit: each row of D9's table, `, url: ` and `cf-ray` cut, a key in the text out before the cut; a
journal with no error, with an error, with a later `task_started`, a line in writing; the offset kept,
a new file from 0; a built-in agent reads nothing (no file opened); `check_turns` on an agent not busy.

Integration: the fake agent writes a journal line and stays busy; within the loop's passes the agent
is idle, the chat's line is LADO's, no resume for a 401, a resume for a 500, the key echoed is `***` in
`lado log` and `lado.db`, a restarted loop tells nothing again, a queued message is delivered after it.

## Task 4: Smoke

Layer: smoke, real Codex, a fake Responses server. The only layer that catches a Codex update, so it
holds the journal's format and the catalogue.

`tests/fake_model_server.py` gets a Responses stream: a shell call, an MCP call to LADO's `list_agents`,
a reply, usage. Then: the session reaches idle; the tools have LADO's in a `namespace` and no
`web_search` or `custom`; no `Model metadata` warning; usage past the limit brings a compaction request;
401 and 429 end the turn in LADO's words, with a count of requests that stops, the key echoed and in no
text. The existing smoke's Codex branch keeps its built-in checks.

## Task 5: Documents

The text is in the design doc. Then grep: `does not run on a model server`, `no session of theirs
starts`, `runs no hook for a turn` in `docs/` and `BACKLOG.md`.

## Task 6: The end

`make lint`, `make test`, `make web`, the changed integration and smoke tests with their markers (run
each layer alone), the openspec checks and a trial archive. Then the report names what is left: the
human's manual check (their key, a worker, a wrong key, a long session up to a compaction, the
catalogue on a real server), and what Codex cannot do.

## Regression run

`make test` whole; `uv run pytest -m integration -n auto tests/integration/test_model_server_probe.py
tests/integration/test_provider_refusals.py tests/integration/test_codex_model_server.py`; CI's smoke
for all four CLIs.
