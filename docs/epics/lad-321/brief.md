# Brief: Session isolation, M1 — Agent API groundwork (LAD-321)

## The human's statement

The epic's tracker task LAD-321 («Эпик: изоляция сессий, M1 — подготовка Agent API»), whose
description is the statement, written in Russian; in short, in English:

> LADO goes towards isolating every session, then towards the cloud. Today the agent's
> helper programs (`lado hook`, `lado mcp`) open LADO's database and its tmux themselves,
> with no proof of who they are. M1 is the first, safe step: a personal token for every
> agent; the hooks and `lado mcp` split into a "client" and a "server" half, still in one
> process; the protocol between the halves written down; the idea tried once in a
> throwaway prototype. The user notices almost nothing but two fixes: an agent can no
> longer make an artifact from a file outside its folders (M1-4), and LADO's folder is
> closed to other users of the machine (M1-10).

Sources it names, the plan being the source of truth on what and in which order:
`docs/research/session-isolation-dev-plan.md` (sections 1, 2, 3.1 — tasks M1-1…M1-10 —,
5, 6), `docs/research/session-isolation-plan.md` (D1, D2, Q1–Q5, section 4, stage M1),
`docs/research/session-isolation/plan-plain.ru.md`. Line numbers there were checked
against main on 2026-11-27 and are checked again before each task.

The human's rules from the statement (2026-11-28): one session for the epic; one task, one
pull request that can be reviewed in one sitting; a review after every task, its findings
carried into the next tasks, a wrong plan fixed by a separate docs pull request; tracker
tasks created one at a time when their turn comes; the epic's records in
`docs/epics/lad-321/`, decisions on the protocol and the process model in a new
`docs/design/agent-api.md` (Q-10); no release plan up front, every task releasable, the
CHANGELOG line in the task that changes what users see; merges into main only by a pull
request with a green `ci-ok` and the human's explicit "merge". Q-1…Q-9 belong to their
stages: a M1 task that runs into one asks the human.

The human's words at the start (2026-11-28): besides the end goal, every new release, and
better every finished task, must not break the system and must bring it smoothly closer to
the end goal.

Intake added (decisions.md, rounds #8901 and #8915):
- steps strictly one after another, each merged and checked by hand before the next;
- first a safety net, before any code change: the smoke tests reviewed and fixed so they
  really catch breakage; live tests run often and cheaply (Claude Code on the human's
  subscription, the other CLIs on a cheap OpenRouter model, $10 for the epic for now), once
  per step that touches agents, before its merge;
- a detailed manual checklist for every step that changes code, run by the human on
  another machine with another agent, on a build of the pull request's branch, native and
  Docker installs where the step touches them;
- the prototype M1-6 runs on a separate Mac of the human (no Docker in LADO's container);
  its draft pull request stays on the public ladohq/lado.

## Goal and "done"

Goal: the base the next stages (M2a…) build on without rework — every agent launch carries
a verifiable token; `lado hook` and `lado mcp` are split into a client and a server half
behind one seam each, still in one process; the protocol between them specified and tried
end to end once; two security fixes shipped. Everything else behaves as today.

Done: the M1 exit gate (dev plan 3.1): the Agent API protocol spec merged in
`openspec/specs/agent-api/`; the decision record on the process model merged in
`docs/design/agent-api.md`; the prototype reviewed; the threat model (plan, section 4)
approved by the human with the M0 results (E9, E14, E15, E10) and the two review items in
(the narrow setuid "become the agent" helper of M3-5b, the M3 column of the threat table).
Every step merged into main with `ci-ok` green, its live run and its manual check passed.

## Readiness checklist

- **Goal and "done"**: covered by S1–S12 and the M1 exit gate, Check: the four gate items
  (S9 reviewed, S10, S11, S12 approved) and every step's check.
- **Users and how they use it**: covered by S3 and S4, Check: the human's manual check of
  the closed folder and of the artifact refusal; developers of M2a by S10 and S11.
- **Scope and what is out**: covered by plan.md (S1–S12, Later), Check: each step's brief
  names its frame; M2a and later, Q-1…Q-9 out.
- **Data and migrations**: covered by S5, Check: key files 600 under
  `LADO_HOME/agent-api/keys/`; a schema change, if the design needs one, names its way back
  (open question 2).
- **Secrets and credentials**: covered by S5 (token never in argv nor tmux's environment,
  a test), S4 (no artifact of `lado.db` or a token file), S3 (folder 700), S2 (no key or
  subscription token in logs, configs or evidence, a test).
- **Update and rollback**: covered by S5, S6, S7, Check: agents of the previous version keep
  working until restart (integration tests) and the human's manual `lado update` with a
  running session; every step's rollback is a revert.
- **Removal**: not relevant: everything new is under `LADO_HOME`, which `lado uninstall`
  removes; a step that adds something outside it names its removal.
- **Platforms**: covered by S1 and S2 (all four CLIs, Linux and macOS in CI, local live),
  S3 (native and Docker), S9 (the human's Mac), S10 (macOS socket path limit).
- **Observability**: covered by S5 (a refused token in `hooks.log` and the error journal),
  S4 (the refusal says where files may come from), S3 (doctor's check with the fix).
- **Tests and what only a human can check**: covered by S1 (smoke able to fail), S2 (live
  on demand), every code step's negative test seen red first and the human's manual
  checklist (S3–S7, S9).
- **Documentation**: covered by each step (docs and specs in the same pull request),
  CHANGELOG in S3 and S4 only, S10 the new `docs/design/agent-api.md`, S11 the spec.

## Branch strategy

Every step merges into main, each leaving LADO working and releasable (#8901 q2).

## Tracker

The epic is LAD-321. Step tasks are created one at a time, when their step comes, on the
human's "yes, create".

## Verdict

Ready to plan.
