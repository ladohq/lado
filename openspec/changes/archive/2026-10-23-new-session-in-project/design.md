## Context

Steps S3–S6a built a session in a project in the core and the CLI: `runtime.start_session(
None, name, …, project=<id>, repo_name=<name>)` takes the project's repository
(`projects.repository`, refusing an unknown project `NoSuchProject`, an unknown repository
`NoSuchRepository`, a link as a link), names the session `<id>-<name>` by default, keeps
the project in `sessions.project` and gives the agents the project's variables and secrets.
`lado start --project <id> --repo <name>` calls it. A new session without a project inside
LADO's `projects/` is refused (`projects.refusal`, kind `in_project`) with a CLI hint.

The server's start, `POST /api/sessions` (`server/app.py`, model `Launch` with `where:
Where{kind, path}`), knows the kinds `folder` and `scratch` and refuses any other with 400
`where of kind "…" is not supported yet`. The New session window (`web/src/Launch.tsx`,
1586 lines) has the switch From scratch | Folder | Clone from URL; its Folder check (`GET
/api/folders`, `launch.folder_info`) shows the `in_project` refusal with the hint's command
and Copy. Kits and mode of a new session come from the folder's last session, found in
`GET /api/folders/recent`, which leaves out `projects/`. The Projects section (S6a) shows a
project's page with a not-built line naming the CLI.

Model and decisions: `docs/design/projects.md`, the concept `projects-concept` ("The
session"), the brief of gate #105 (S6b), the human's answers #1282 (the window only chooses
a repository; repositories are managed on the project's page) and #1283 (adding on the page
stays in S7; the recommendations 1–7 accepted), the mockup `mockup-project-way.html`
(version 2).

## Goals / Non-Goals

Goals: a session in a project started from the browser by choosing a project and one of its
repositories, through the same core function as the CLI; Folder's refusal inside a project
leading there; the project's page opening the window on it; the canary over that start.

Non-goals: adding a repository from the window (dropped, #1282); the project's page with its
repositories, sessions, rename and delete (S7, #1283); sessions over several repositories.

## Options

The root cause: the start's request cannot name a project and its repository, and the
window cannot choose them.

1. **A `project` kind of `where` on the existing start, and one read route that tells the
   window what a start in a project takes (the choice, the default name, its state, the
   provider, the last session)** (chosen). Long-term cost: one route and three optional
   fields of `Where`; every rule (the default name, the choice of project and repository,
   the name's state) stays in the server next to the core, so S7's per-repository "Start
   session" reuses it with `?project=&repo=`.
2. The window composes from what exists: `GET /api/projects` for the select, `GET
   /api/projects/{id}` for the repositories, the feed's sessions for the last one, and the
   name `${id}-${repo}` made in TypeScript. No new route, but the default name's slug rule
   and the name's state would get a second copy in the web, and the feed has no start
   order (`state.sessions_by_start`), so "the last used" could not be told: against "one
   source of truth".
3. A route of its own, `POST /api/projects/{id}/sessions`. Clear in the URL, but a second
   start route beside `POST /api/sessions` with its own refusal mapping and models
   (`Launch`, `Taken`, `Refused` repeated): the brief's threshold "a second implementation
   of the start" leans against it, and the window would branch on two routes.

## Decisions

**D1. The window only chooses (#1282, #1283).** Project chooses a project and one of its
repositories; nothing is cloned or made from the window. An empty project points at its page
(which until S7 names `lado project repo add`), no project at the Projects section. The
refusals of Clone into and Create in inside a project keep the core's command: a button
there would lead back to adding from the window.

**D2. `Where` stays one model.** `Where{kind: str, path: str | None = None, project: str |
None = None, repo: str | None = None}`; the route checks the combination (kind `project`:
`project` and `repo`, no `path`; kinds `folder` and `scratch`: `path`, no `project` or
`repo`; any other kind: 400 as today). A discriminated union would make an unknown kind a
422 instead of today's 400 and change the generated types of every caller for one more
kind. `path` becomes optional in OpenAPI; the existing callers send it as before.

**D3. The start in a project is the CLI's call.** For kind `project` the route calls
`runtime.start_session(None, given.name, given.permission_mode, given.provider, given.kits,
given.without, resume=False, prompt=given.prompt, title=given.title, project=given.project,
repo_name=given.repo)`. Refusals: `projects.NoSuchProject` and `projects.NoSuchRepository`
404 (caught before `LadoError`), `runtime.SessionExists` 409 `Taken`, `kits.KitError` as
today, any other `LadoError` 400 with its text. `resume=False` as for every new session of
the API, so a taken name is 409 (never a silent resume), and the core's "a session's project
never changes" cannot arise from the API.

**D4. `GET /api/project-launch?project=&repo=`.** A read-only route (`guard`, `database`:
without `lado.db` the answer has no projects and makes nothing), not under `/api/projects/`
because any word there may be a project's id (S6a's `GET /api/project-id`). Answer
`ProjectLaunch{projects: list[ProjectSummary], project: str | None, repos:
list[ProjectRepo], repo: str | None, default_name: str | None, name_state: NameState |
None, provider: ProviderSuggestion | None, last: SessionInfo | None}`, built by
`launch.project_launch(project, repo, has_db)`:
- `projects`: `launch.project_summaries()` sorted by `(title or id).casefold()`; the window's
  select shows them in this order, so the order has one source.
- `project`: the asked id when it is in `projects`; else the project of the first session of
  `state.sessions_by_start()` whose project is in `projects` with its folder found; else the
  first of `projects` with its folder found; else the first of `projects`.
- `repos`: `projects.repositories(project)` as `ProjectRepo`s (none when its folder is not
  found).
- `repo`: the asked name when it is in `repos`; else the repository (the folder's name) of
  the first session of `sessions_by_start()` in that project whose folder is still one of
  `repos`; else the first of `repos`.
- `default_name`: `runtime.slug(f"{project}-{repo}")`, the core's rule (the developer moves
  the expression `slug(name or f"{project}-{repo_name}")` of `start_session` into a small
  `runtime.project_session_name(project, repo)` both call, so the rule is written once).
- `name_state`: `launch.name_state(default_name, path, has_db, project=project)`; the new
  `project` argument makes a session of that name in another project or in none
  `taken_elsewhere` (D5).
- `provider`: `launch.provider_suggestion(path)`.
- `last`: the first session of `sessions_by_start()` with `repo == path` and `project ==
  project`, as `SessionInfo`.

**D5. The name's state in a project.** `launch.name_state(name, root, has_db, project=None)`:
with `project` given, a session of the name whose `project` differs (another project, or a
session from before schema 33 with none) is `taken_elsewhere`, so the window never offers
"Resume it" for a session the start would not resume as this project's. Without `project` it
answers as today.

**D6. Which project a path is in: `projects.place(path)`.** A new `Place(id, repo: str |
None)` for a path whose real path is inside a project's folder in LADO's `projects/`, else
None (outside, the human's own `projects/`, a foreign folder). `refusal` and its `_hint`
use it for the project and the repository, so the hint's `lado start --project <id> --repo
<name>` and the UI's button come from one place. `launch.folder_info` sets
`FolderInfo.project = ProjectPlace{id, title, repo}` from it (title from `projects.get`)
only when the check refused with kind `in_project`; else null.

**D7. The Project way's code.** A new file `web/src/LaunchProject.tsx` holds the field
(`ProjectField`: the select, the facts line, the repository list `.repo-pick` with
`role="radiogroup"`, the two empty states); `Launch.tsx` gains the source `"project"`, the
state `{project, repo}` asked from `GET /api/project-launch` (`useAsked`, keyed by the two),
`projectReady`, the `where` of kind `project` in `startIn`, and the Folder refusal's
buttons in `WhereField`. The other three ways keep their code (the brief's threshold); a
change to them beyond the switch and the refusal's button is a stop and a question.
`LaunchMode` becomes `{kind: "new"; project?: string} | {kind: "resume"; …}`: with
`project` the window opens in Project with that project (the page's link), otherwise as
today (#1283, 3). The Folder refusal's `Start in the project` sets the source to Project
and asks `project-launch` with the place's `project` and `repo`; `Open the project`
closes the window and navigates to `/projects/<id>`, as the empty states' links do.

**D8. Defaults from the repository's last session.** In Project the effect that sets Kits
and Permission mode from Folder's `last` takes `ProjectLaunch.last` instead, keyed by its
name and the source, honouring `touched` as today; Provider follows `ProjectLaunch.provider`
by the existing suggestion effect (`suggesting` gets the Project case). The notes read as in
Folder ("from the last session of this folder").

**D9. A project whose folder is not found** is an `<option disabled>` marked `folder not
found`; `project-launch` chooses it only when asked or when no project's folder is found (then `repos` is empty and the empty state shows, the link going to its page, which says
`folder not found`).

**D10. The phone.** `@media (max-width: 760px) { .where-head .segments { display: grid;
grid-template-columns: 1fr 1fr; width: 100%; } }` with the buttons centred; the rest of the
window as today (one column below 760 px).

**D11. The project's page.** `Projects.tsx`'s not-built line begins with a `link-button`
`New session in this project…` calling `useLaunch()({kind: "new", project: id})`, and its
text names what S7 brings (the spec's MODIFIED requirement).

**D12. The canary.** `test_a_project_secret_is_found_nowhere_else` starts `shop-frontend`
through `api.call("POST", "/api/sessions", {where: {kind: "project", project: "shop",
repo: "frontend"}, kits: ["default", "itcanary"], provider: "fake"})` in place of the direct
`runtime.start_session` call, asserts 200 and `session.project == "shop"`, and adds the
answer to `said`; the rest (environments, processes, files, feed, logs) stays and now
covers a start through the server's process.

**D13. Tests by layer.** Unit: `tests/test_server_project_launch.py` (new) for the start's
kind `project` (the core call with `project` and `repo_name`, asserted with a recorder of
`runtime.start_session`; 404, 409, 400 combinations; the token), `GET /api/project-launch`
(the choice rules, sorting, `name_state` across projects, `last`, no `lado.db`), `GET
/api/folders`'s `project`; `tests/test_projects_core.py` for `projects.place` and the
refusal's hint unchanged; `tests/test_runtime*.py` for `project_session_name`. Vitest:
`web/src/LaunchProject.test.tsx` (new) and `Launch.test.tsx` (the switch, the choice, the
empty states, the request's body, the refusal's buttons), `Projects.test.tsx` (the link).
Integration: the canary (D12) — the one start through the server's process with real tmux
and the fake agent. UI e2e: `tests/ui/test_launch_project.py` (new): Project → project →
repository → start, the head's `project Shop`; the Folder refusal into Project; the taken
name's refusal text; the page's link; 390 px with the switch's grid. All waits are on
states, never times (LAD-127).

**D14. Docs and version.** `docs/design/ui.md` (Launch: the fourth way, `where` of kind
`project`, `GET /api/project-launch`, the refusal's buttons; Projects: the page's line),
`docs/design/projects.md` (The session: the window only chooses, "+ new repository" moved to
the page's S7; The UI: what is built; the step table's S6b row), CHANGELOG under `## 0.43.0
(unreleased)` (Added). Minor: an API change, already 0.43.0.

**D15. The epic's files.** The concept and `docs/epics/lad-116/plan.md` belong to the epic
and are not changed here; the analyst tells the supervisor that the concept's "+ new
repository" in the window was dropped (#1282) for the epic to record.

## Risks / Trade-offs

- `Launch.tsx` grows again; the field in a file of its own keeps the growth to the wiring.
- A repository removed by hand between the window's read and Start is refused by the core
  (404 with its text), shown as any refusal.
- The choice of "the last used" reads `sessions_by_start()` (one query over sessions and
  events) per request; the window asks once per project change.
