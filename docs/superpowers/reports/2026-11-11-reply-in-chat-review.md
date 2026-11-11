# LAD-274 reply-in-chat: review report

Pull request #292 `hotfix/lad-274-reply-in-chat` → `main`. Scale: hotfix, the review widened to
`hooks.py`, `runtime.py` and `state.py`, as the diff changes every agent's instructions and the
check of replies to the human. Head reviewed: `14ee8c36`; `8cd84886` after it is an empty commit
that only restarted CI stuck in GitHub's queue. Every agent is told the human does not see its
terminal and how to answer; the human's line ends with a hint how to answer it; an answer left in
the terminal gets one reminder from `lado`, and the note "replied only in its terminal" waits for
the reminder's turn. Delta: `reply-check`, one requirement modified, four added.

## Rounds

1. Local, wide. The whole diff `02767b42..14ee8c36`: the spec against the code and tests, silent
   failures, comments, the architecture against AGENTS.md. Every task of `tasks.md` checked (11 of
   11), decisions D1–D8 kept. Findings L1, L2. The supervisor's three questions answered (below).
2. External 1, a stand-in: the Claude Code GitHub Action run 43097614084 stayed queued by
   GitHub, so a fresh agent got only the diff and the pull request's description. No blockers;
   S1, S2 (merged into S1) and S4 confirmed (minor), S3 and S5 refuted.

External rounds used: 1 of 1. Stand-ins: 1.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| L1 | minor | local: no committed test of a reminder queued next to another `lado` message (D4) | declined: the behaviour is right; a probe of three tests outside the tree passed (the verdict waits a turn and then comes; a reply in the delayed turn is `replied`; two human messages get two reminders and two verdicts) |
| L2 | minor | local: `docs/design/ui.md:875` says "when the supervisor ends a turn", while the check runs for any agent | declined: the wording is older than the change |
| S1 | minor | stand-in: `queue_message` raises `NotRunning` when the agent is stopped during the turn-end hook; the rest of `handle` is skipped and the message stays `reminded` without a reminder | declined: a rare race with a stop; after a resume one message gets the note without a reminder and one line goes to the error journal. A later fix: catch `state.NotRunning` around `queue_message` |
| S2 | minor | stand-in: the state and the reminder are written in two transactions | merged into S1 (the same path) |
| S3 | — | stand-in: any `lado` message delays the verdict, and any later message to the human counts as the answer | refuted: counting by `sent_at` predates the change; the delay is D4's, and the verdict still comes (L1's probe) |
| S4 | minor | stand-in: the comment of `reply_state` (`state.py:1267`) names `REPLIED \| MISSING` only | declined: cheap minors go only with other fixes |
| S5 | — | stand-in: a model rightly silent on "thanks" still gets a reminder and the note | refuted: the design's choice (proposal, Out of scope; design, Risks), the human's on #6042 |

## The supervisor's questions

1. D4 next to other `lado` messages: the verdict is delayed, not lost; a message stuck in `sent`
   goes `failed` by the redelivery sweep, so nothing stays `reminded` for ever.
2. Noise in the chat: the reminder goes from `lado` to the agent and shows only under "All";
   `test_an_answer_after_the_reminder_is_a_reply` checks the feed brought only `replied`. The API
   gives `reminded` as `null`.
3. The rule and "Do not relay worker or reviewer reports" do not contradict each other.

## Found on the way

None.

## Checks

On `14ee8c36`, every one with exit status 0:
- `make lint`; `make test` 6167 passed, 7 skipped; the changed integration files with
  `-m integration` 90 passed; `openspec validate reply-in-chat --strict`;
  `openspec validate --specs --strict`; the trial archive in a copy.
- CI run 43104314162 on `8cd84886`: success, 27 of 27 checks, `ci-ok` and the smoke included.

Not run: the live test `check_hello` (written, paid; `live.yml` by hand). Weak models are not in
CI; the experiment is their evidence (98% of answers in the chat).
