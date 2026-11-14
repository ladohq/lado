# LAD-285 live-passive-role-answers-human: review report

Pull request #312 `fix/lad-285-live-hello-role` → `main`. Scale: tweak, depth precision.
Head reviewed: `05e8ac8d`. The live cell of Codex failed at random in `check_hello`
(`missing` instead of `replied`): the live kit's passive supervisor was told never to use any
tool, `send_message` included, while `check_hello` (LAD-274) expects it to answer the human.
Not a regression of LAD-234: LADO's hint and its one reminder worked as specified. The role now
allows `send_message` to the human and nothing else; `docs/testing.md` says so.

## Rounds

1. Local, precision, over `7e77aa5a..05e8ac8d`, checked against the change: AC-1…AC-4 met.
   On the supervisor's request, every use of the passive supervisor under `tests/live/` was
   checked (`supervisor_quiet`, `check_hello`, `check_human`, the `messages(...)` filters,
   `check_supervisor_tools`, `check_supervisor_kept_still`, `check_resume`, `check_clear`, the
   flow, image and tmpdir tests): none relies on it sending the human nothing. Nothing found.
2. External 1, Claude Code GitHub Action (request 21:00:49Z, "Claude finished" 21:01:50Z). It
   read `tests/live/test_live.py` and `docs/testing.md`; not the openspec files (not risky).

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | external: `check_hello`'s last assertion, `len(messages("supervisor","human")) > before`, is weaker now: a late ACK to an earlier message could satisfy it | declined: the assertion before it, `reply_state == REPLIED`, holds the point; changing the assertions is out of scope (AC-2). A later option: check for a supervisor→human message created no earlier than the hello |

## Checks

- `make lint`: exit 0.
- `uv run pytest -m live --collect-only -q tests/live/test_live.py`: 16 collected.
- `openspec validate live-passive-role-answers-human --strict`: valid.
- CI of #312 on `05e8ac8d`: 27/27, `ci-ok` green (run 43640380166), the smoke on Linux and
  macOS included. `make test` not run locally (the diff touches no unit test; CI ran it; the
  build report: 6199 passed, 7 skipped).

## Metrics

Rounds 1 (local 1, external 1, stand-ins 0). Local: confirmed 0, refuted 0. External:
confirmed 1 (minor), refuted 0. Findings in code rewritten by the developer's cleanup: 0.

## Not checked (residual risk)

The live cells are written, not run: the environment `live` is open only to main and tags.
Watch the codex cell in the first `live.yml` run on main after the merge. Haiku through Codex
may still answer only in its terminal now and then; `check_hello` would then show `missing`,
a signal about the model, not a defect of the test.

Found on the way: none.
