## Context

Steps S2–S5b built projects in the core, the CLI and the server: `lado.projects` (create,
get, rename, `listed`, repositories from the disk, plain variables in `lado.db`, the rules
of names), `lado.project_secrets` (one file per secret under
`<LADO_HOME>/projects/<id>/secrets/`, `names`, `read` → `Outside(values, unused)`), and the
routes `GET /api/projects/{id}`, `PUT`/`DELETE /api/projects/{id}/variables/{name}` and
`…/secrets/{name}` (answering `{project, running}`), `POST /api/projects/{id}/repos`,
`POST /api/clones` with a project. `lado doctor` alone says which names a project overrides
of `LADO_ENV_DIR` (`check_project_variables`) and which secret files its agents do not get
(`check_project_secrets`). The web UI shows a placeholder for Projects (`web/src/pages.tsx`)
and the session head's `project <title>` as text (`Sessions.tsx`, `SessionDetails.tsx`).

The change feed (`server/feed.py`) replays journaled rows of sessions, agents, messages and
the rest; `projects` and `project_variables` are not journaled, and secrets are files.

Model and decisions: `docs/design/projects.md`, the concept `projects-concept`, the brief of
gate #96 (S6), the human's answers #1151 (split S6a/S6b), #1153 (recommendations 1–10 of
the mockup `mockup-projects.html`) and #1158 (adding repositories).

## Goals / Non-Goals

Goals: the Projects section with its list, making a project, and a project's page with its
variables and secrets, the outside overrides, unusable secret files, the security warning
and the running sessions; the API it needs; a secret's value only in one request's body;
the canary over the new endpoints with E6–E9 closed.

Non-goals: the Project way of New session and a start in a project from the UI (S6b); the
page's repositories, sessions, rename and delete (S7); a feed of projects; isolation.

## Options

How the screen learns what it shows (the root cause: the server has no list, no create, and
the project's answer lacks the facts only `doctor` has):
1. **REST: a list, a create, an id suggestion, and the project's answer extended with
   `running`, `overrides`, `unused`, each derived by one core function shared with
   `doctor`** (chosen). Long-term cost: three routes and three fields; one source of truth
   for each fact; the page reads anew instead of following a feed.
2. Projects in the change feed (journal triggers on `projects` and `project_variables`,
   secrets' names pushed on write). Live in every browser, but a schema migration for one
   screen, and the secrets' names, which are files, would need a second record that can
   drift from the folder: against "one source of truth".
3. The UI composes from what exists (sessions of the feed, `GET /api/projects/{id}` per
   project). No way to list projects or make one; rejected.

How much of S6 one pull request carries (#1151): **S6a here, S6b a task of its own**
(chosen) keeps each review on one risky area (the secret's way vs. the Launch window,
1585 lines); one pull request would be L+ with two mockup sets.

## Decisions

**D1. Split.** This change is S6a; S6b (the Project way of New session: project then
repository, "+ new repository" by clone or from scratch through the S4 routes, the S3
refusal in Folder leading into Project, the start equal to `lado start --project <id> --repo
<name>`, the canary of that start) is a new task derived from LAD-134 (#1151). The S6 row of
`docs/design/projects.md`'s step table splits into S6a and S6b.

**D2. Routes of the section.** `/projects` and `/projects/:id` under one `Projects`
component laid out as Sessions (`App.tsx`: `<Route path="projects" element={<Projects/>}>`
with an index child and `:id`): the list at the left, the page at the right; on a phone the
list or the page, as `phone.ts` already decides for Sessions. The new code lives in
`web/src/Projects.tsx` (list, page, dialog) and `web/src/ProjectVariables.tsx` (the two
blocks), not in `pages.tsx`, whose placeholder goes; `PLANS.projects` points at the plan of
S7 for the page's not-built line.

**D3. No feed for projects; read anew.** The list and the page fetch on open, take the
project from each change's answer (`{project, running}` already carries it), fetch again
when the sessions of the feed change (a session of the project appears, starts or stops) and
when the window gets focus. A change made in another browser shows on its next focus or
open. A journal for projects is option 2, rejected.

**D4. The API.**
- `GET /api/projects` → `list[ProjectSummary]` `{id, title, folder, found, repos: int,
  running: list[str]}`, from `projects.listed()`, `len(projects.repositories(id))` when the
  folder is there, and `projects.running(id)`. Without `lado.db` (`database` dependency
  false): `[]`, none made.
- `POST /api/projects` with `ProjectNew {id, title?}` and `guard.changes` → `ProjectInfo`;
  `projects.create`, `LadoError` → 400 with its text. It makes `lado.db` when missing, as
  `lado project create` does.
- `GET /api/project-id?title=` or `?id=` → `ProjectId {id: str | None, folder: str | None,
  problem: str | None}`: a path of its own, since `new` or any word under `/api/projects/`
  is a valid project id.
- `ProjectInfo` gains `running: list[str]`, `overrides: list[str]`, `unused:
  list[UnusedSecret {name: str | None, reason: str}]`; `launch.project_info` fills them, so
  every route that answers a project carries them.
All in OpenAPI; `make web-types` regenerates `web/openapi.json` and `web/src/api.gen.ts`.

**D5. One source per fact.**
- `projects.overrides(id) -> list[str]`: the project's variable and secret names that
  `agent_env.outside().values` holds, sorted; `doctor.check_project_variables` builds its
  line from it. No value leaves the function.
- `project_secrets.unused(id) -> list[tuple[str | None, str]]`: `read(id).unused`; the
  values `read` loads stay in the function. `doctor.check_project_secrets` uses it.
- `projects.suggest_id(title) -> str | None`: `scratch.names(title).name` with `_` → `-`,
  cut to `MAX_ID`, trimmed of `-`; a `ScratchError` gives None with its text as the problem.
- `projects.check_new(id)`: `create`'s checks before it makes anything (id, workspace,
  taken, folder, left data folder, the human's `projects/`), factored out of `create`, which
  calls it; the race of two creates stays caught by `creating_project`.

**D6. The secret's value in the browser.** The value field is an uncontrolled `<input
type="password" autocomplete="off" data-1p-ignore data-lpignore="true">`, not inside a
`<form>` that submits or navigates (the browser's "save password" and form history follow a
form's submission). The value is read from the field's ref when the human clicks Add,
Replace or presses Enter, sent as `{value}` in the body of `api.ts`'s `putSecret`, and the
field is emptied (`ref.current.value = ""`) on success, on Cancel and on unmount; it is never
put in React state, a context, a URL, a query, `localStorage`/`sessionStorage`, an error the
UI keeps, or the console. After a refusal the value stays in the open field so the human can
fix the name; Cancel or leaving the page empties it. The server's access log is off
(`server/run.py`, `access_log=False`); the 422 of the secrets' routes already answers
without the input (S5b). Rejected: a controlled input (the value would sit in React state
and its dev tools).

**D7. Refusals.** A 400's `detail` is shown verbatim in the S1b style (`field-note bad`)
under the row or field it concerns, the fields kept. The variable's refusal "looks like a
secret" is recognised by the `looks like a secret` text of the core (the 400 carries no
kind); its button moves the name only, the value field of the secret form empty.

**D8. A name LADO sets.** S5a's launch warning of a name LADO sets concerns the outside
folder; a project cannot hold such a name: `projects.check_name` refuses every reserved name
(`RESERVED_NAMES`: the shell's, `LADO_*`, each provider's CLI variables) for both kinds. The
page shows that refusal; it needs no warning of its own.

**D9. Unusable secret files.** A secret named in `secrets` and in `unused` shows `⚠ Agents do
not get it: <reason>` in its row with Replace and Remove (a Replace writes the file 600 and
mends a loose mode); an `unused` entry with no secret of its name (a link, a bad name) shows
as a line under the block, and the folder's (`name` null) as `⚠ The secrets folder is not
used: <reason>`, both without actions: the CLI and the human's shell mend them.

**D10. The running line.** `ProjectInfo.running` gives the names; the UI shows each session
by its title from the feed (`sessionLabel`), the name without one, as a link to
`/sessions/<name>`.

**D11. New project's id.** The dialog asks `GET /api/project-id?title=` as the title
changes, debounced as the fresh start's name is in `Launch.tsx`, until the human types in
Id; from then on it asks `GET /api/project-id?id=` for the typed id. The answer `{id,
folder, problem}` gives the note under Id (`folder`: `projects.folder(id)`, the workspace of
now) or the refusal, and enables Create. One request per pause in typing; nothing is made
before Create, whose `POST` checks again (another browser may have taken the id).

**D12. The head's link.** `session-project-title` in `Sessions.tsx` and the details' `dd` in
`SessionDetails.tsx` become a router `Link` to `/projects/<id>`, the tooltip kept.

**D13. The canary** (`tests/integration/test_project_secrets_canary.py`):
- the new endpoints in `said`: `GET /api/projects`, `GET /api/project-id?title=…`, `POST
  /api/projects` (made and refused), `GET /api/projects/shop` with `overrides` (an outside
  folder giving `CLI_NAME` with another unique value) and `unused` (a loose hand-made file);
- E6: `ps -ww -eo args` after each agent kind starts, not once;
- E7: `tmux show-environment -t <session>` for every session of LADO's socket (`tmux
  list-sessions -F '#{session_name}'`) besides `-g`;
- E8: `files_holding` reads a link's target too (a file link; folders are not followed, so
  no loop) and fails on a read error but a socket or a file gone meanwhile
  (`FileNotFoundError`);
- E9: neither secret's name is in `lado bug-report`'s output nor in `GET /api/bug-report`.

**D14. The browser's proof.** `tests/ui/test_projects_section.py` sets and replaces a secret with a
unique value in Chromium against a real `lado server`, records every request URL
(`page.on("request")`), then asserts the value is in no URL, not in
`JSON.stringify(localStorage)`/`sessionStorage`, not in the server's log and the files under
`LADO_HOME` but the secret's, and that the field is empty. It waits for states
(`expect(locator).to_have_…`), never for time (the LAD-127 flake).

**D15. Docs and version.** `docs/design/ui.md`: a section "Projects (decided 2026-10-23,
LAD-134)" with the list, the page, the dialog, the variables' blocks, D3 and D6; the head's
line "text, not a link, until the Projects section (S6)" becomes the link; the Launch
section's "fourth way (step S6…)" becomes S6b. `docs/design/projects.md`: what is built in
"Variables and secrets" and "The UI", the step table's S6a/S6b, and F3/E5 under the secrets'
store: a secret is read through links above `secrets/` (`LADO_HOME` itself may be one), while
writing and removing refuse a link at `projects/`, `<id>/`, `secrets/` or the file. CHANGELOG:
one line under `## 0.43.0 (unreleased)`; the minor is already raised.

**D16. Repositories meanwhile** (#1158): the page's not-built line names `lado project show
<id>` and `lado project repo add <id> <git-url>`; adding from the UI is S6b (with a start)
and S7 (on the page).
