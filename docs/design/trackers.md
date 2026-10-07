# Task trackers

Plan for LADO's work with task trackers (ROADMAP.md, stage 9), not started. It comes after
the artifacts stage; when the work starts, this file is the starting point of its design.

## Goal

Any kit can work with any task tracker, and LADO's core knows nothing about trackers: no
tracker client, no tracker settings, no tracker-specific fields or dependencies.

## Decisions

1. **One convention, no contract.** A tracker kit provides a skill named `tracker`. Its
   SKILL.md says, in its own words, how to do the usual things in that tracker: find a
   task, read it, create one, change its status, comment, link a branch or commit. There
   is no separate contract document, pack or version: models map "file a bug" or "move the
   task to review" onto whatever the skill describes, and do without what it lacks.
2. **A session combines kits:** `lado start <repo> --kit <process-kit> --kit tracker-jira`.
   A process kit's roles talk about the tracker in plain words ("file it with the tracker
   skill").
3. **Checks LADO already does, no core change:** a role that lists `skills: [tracker]`
   cannot start without a tracker kit in the session (`skill "tracker" is not visible to
   agent ...`), and two tracker kits in one session fail as `skill "tracker" is defined by
   two kits`, with the `--without` ways out. A role without `skills:` gets every skill,
   so the tracker is optional for it. Whether a process kit requires a tracker is the
   kit's choice.
4. **How the kit uses the tracker is the kit's choice:** which roles touch it (the
   supervisor only or every role), when statuses move, what agents may and may not do.
   LADO sets no limits here.
5. **Credentials:** the user's own account, from environment variables of the user's
   login shell (agents get that environment; LADO never writes it to disk). A password
   comes from the OS keychain in the shell profile, not as plain text.
6. **Project settings** (project key, issue types, the mapping of the process's statuses
   to the board's, labels, custom fields) differ per project: they go in the project's
   repo, `.lado/tracker.yaml`, read only by the tracker skill, never by LADO. Its format
   is the tracker kit's, decided with the first real project.
7. **No MCP in the first kit.** The skill reaches the tracker with a script in its own
   folder (Python standard library). See Later for MCP.
8. **LADO's own backlog stays in BACKLOG.md.** LADO will probably move to another tracker
   later; the lado-dev kit is not changed by this work and does not require a tracker.

## For kit authors

A tracker kit is a kit without agents whose skill `tracker` describes one tracker: each
usual action, the markup the tracker expects, where the project's settings are and what to
do on each error. A process kit does not depend on a tracker kit: its roles name the
tracker skill in plain words, and a role that cannot work without it lists
`skills: [tracker]`, so a session without a tracker kit refuses to start it. Project
specifics (domain, project key, fields) go in the project's `.lado/tracker.yaml`, never in
the skill's text.

## First tracker kit: tracker-jira

- A new official kit (in the official marketplace), although the first Jira it serves is
  internal. A kit without agents; its own git repository; developed in its own LADO session.
- `skills/tracker/SKILL.md`: how to do each action, how to write Jira wiki markup (not
  Markdown), where the project's settings are, what to do on each error.
- `skills/tracker/jira.py` (standard library only): get, search (JQL), create, transition,
  comment, remote link. Reads `JIRA_URL`, `JIRA_USER`, `JIRA_PASSWORD` and the project's
  `.lado/tracker.yaml`.
- Errors are said plainly and never guessed over: task not found, no access, tracker not
  reachable (VPN), credentials missing or refused.
- On a 401 the script never retries: after a few failed logins Jira asks for a CAPTCHA and
  refuses REST logins (`X-Authentication-Denied-Reason`) until the user logs in in a
  browser.
- Checked with `lado kits check`, then a trial on a test task in the real Jira, only with
  the human's yes.

### The first target Jira (checked 2026-10-08)

- Jira Server 8.13.0 (`deploymentType: Server`), on an internal address reachable from
  the company network.
- No personal access tokens (they came with 8.14); the vendor's MCP server and CLI work
  only with Jira Cloud. So: REST API v2 with Basic auth.
- Basic auth is on: a wrong login gets `401` with `X-Seraph-LoginReason:
  AUTHENTICATED_FAILED`; `login.jsp` loads directly, no SSO redirect. Still to confirm
  with a real login: `curl -u <login> <JIRA_URL>/rest/api/2/myself`.

## Steps

1. **Docs in the LADO repo:** this file, and ROADMAP stage 9 says what is decided instead
   of an open question.
2. **Optional core change:** an agent's skill that no kit of the session has says where it
   may come from (a generic hint for any skill, nothing about trackers).
3. **The tracker-jira kit** in its own repository and session: skill, script,
   `.lado/tracker.yaml` format, `lado kits check`, the trial. Then into the official
   marketplace.
4. **The first project** that uses it: its `.lado/tracker.yaml` and its process kit's roles
   saying when to use the tracker.

## Open questions (decided when the work starts)

- The Jira project of the first project: key, issue types, board statuses, custom fields.
- The format of `.lado/tracker.yaml` (shaped by that project).
- Limits for agents in the tracker (deletes, closing tasks, other people's tasks): none for
  now; the kit may add them.
- Who in a process kit touches the tracker (the supervisor only is the likely start).
- A sandbox project or test task for the trial.
- Marking what agents write in the user's name (e.g. a comment prefix `[LADO: <agent>]`).

## Later: generic LADO features, only when a tracker kit needs them

- **A skill brings its MCP servers:** today an MCP server is declared on a role (`mcp:` in
  the agent's file), so a kit without agents cannot give one to other kits' roles. A
  skill could declare the servers it needs, and each role that gets the skill gets them.
- **Remote MCP servers by URL** (`url:` beside `command:`), which all three CLIs support:
  needed for a tracker's hosted MCP with OAuth (e.g. Jira Cloud). A stdio bridge to a URL
  is the stop-gap.
- **Choosing the tracker in the UI:** a Tracker field in New session, kept with the
  session or, later, the project.
- **A `tracker-backlog` kit** on BACKLOG.md, if a public process kit wants a tracker that
  needs nothing external.

## What other orchestrators taught

- One built a tracker client, OAuth, token store and board API into its core (thousands of
  lines), while its agents reached the tracker through the vendor's own tools anyway: the
  core's part went unused, and a second tracker got only a thinner path on the side. Do
  not put trackers in the core.
- Another copied its tracker skills into each kit: the copies drifted (one had a bug's
  workaround, another still described the fixed bug), the organisation's domain, project
  key and fields were written into the skill text, and three variable names meant the
  same login. Do not copy tracker skills; keep project specifics out of the skill.
- Worth keeping: a clear behaviour for each failure (not found, no access, not reachable,
  tool missing); a task's context handed to a session as an artifact the agent reads, not
  pasted into its prompt.
