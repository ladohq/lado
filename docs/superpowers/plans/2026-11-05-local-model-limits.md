# OpenCode and Kilo on local models: Implementation Plan

**Goal:** agents on a model server know its context, a too small model is said aloud, a first start with
no way out does not stall, and a failed turn is not called a reply.

**Architecture:** the read in `model_servers.py`; `model_settings.py` joins it to the config and the
warning; the providers write it; the plugin stops the loop; `hooks.py` skips the reply check.

**Tech Stack:** Python 3.10+, pytest, `tests/fake_model_server.py`, the fake agent, Node's test runner.

**Spec:** `openspec/changes/local-model-limits/` and
`docs/superpowers/specs/2026-11-05-local-model-limits-design.md`.

## Global Constraints

- No new dependency. Past about 20 code files, stop and ask; the estimate is 10.
- No schema, MCP, CLI or API model change. `web/` only for LAD-210.
- No agent CLI's global config is touched. The key only in headers and the agent's environment.
- Do not touch `docs/epics/`. Live tests of Claude Code only with the human's yes.

## Tasks and tests

Numbers are those of `tasks.md`.

| Task | Requirement | Layer | Tests |
|---|---|---|---|
| 1.1 | Overflows in a row stop the turn | by hand, real OpenCode | the fake of the design doc, context 8000 |
| 2.1 | LADO reads a model's context | unit | each shape; a loaded and a not-loaded model; a float; a bad value; a silent server within the ceiling; no redirect followed; the key in the headers |
| 2.2 | the same | unit | two silent servers cost one ceiling |
| 2.3 | A known context goes to the config | unit | 65536, 24000, a reported output, none; both CLIs |
| 2.4 | A start on too small a context | unit | below, at and above the need; unknown; another model; the window |
| 3.1 | Overflows in a row stop the turn | plugin (`make test-js`) | three stop it; the abort's error does not replace it; a step resets; a prompt resets; a compaction alone does not |
| 3.2 | A failed turn decides no reply | unit | error: no state; the next turn replied; the next turn did not |
| 4.1 | OpenCode does not wait for npm | unit | a server's model; built-in; Kilo; the user's value |
| 4.2 | TUI settings | unit | copied; kept at a resume; unreadable; none; the user's file unchanged |
| 5.1 | LAD-210 | vitest | 50 runs under CPU load |
| 6.1 | start's warning, failed turn | integration | the fake agent, `tests/fake_model_server.py` with a small context |
| 6.2 | the key stays off the disk | integration | the canary with a keyed server that reports a context |
| 6.3 | the real CLIs take `limit` | smoke, CI | a config with `limit` starts on OpenCode and Kilo |

Regression run: `make lint`, `make test`, the changed integration files with `-m integration`, `make
test-js`, `make web` for 5.1, `openspec validate --specs --strict`, a green CI.

## The human's check before the merge

One big model at a time on the host. `env | grep LADO_`, `unset` each; own `LADO_HOME` and
`LADO_TMUX_SOCKET`; `make web`.

1. LM Studio, a loaded model: the agent's `% used` is no longer 0; the context in its config is the
   loaded one.
2. LM Studio with a model loaded at 16K: the start warns, the first turn ends on the error in the chat
   on both CLIs, with no endless `busy`.
3. Ollama: is `/api/ps`'s `context_length` there? What does a long session do with no limit?
4. A real LiteLLM in front of a real model: a turn of an agent, and the limits of its config.
5. A weak real model: does it call `read_messages` and `send_message`?
6. A long session on a model of 32-64K up to a compaction, on both CLIs.
