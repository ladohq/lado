## Context

`web/src/Launch.tsx` holds the session's name as `name` (null: the place's), shows it as
`shownName = name ?? named.free_name ?? named.default_name` and passes it to `LaunchTeam.tsx`,
which shows it in Team's summary (`Name <name>`) and as the field **Session name** in the opened
Team. `named` is the place's check: `FolderInfo` (`GET /api/folders`), `ProjectLaunch` (`GET
/api/project-launch`) or `CloneTarget`; each carries `default_name`, `free_name` and
`name_state` from the core (`runtime.free_name`, `server/launch.py`). A project's
`default_name` is `runtime.project_session_name(project, repo) = slug(f"{project}-{repo}")`,
which `runtime.start_session` also uses for `lado start --project` without `--name`. The start
posts `name` (and, for a new empty folder, `title`) to `POST /api/sessions`; `models.Launch`
already takes `title` for every way (`runtime.check_title`), and a name taken in the meantime is
a 409 `Taken`. `Limits.max_title` (80) is already served by `GET /api/limits`, which the window
reads for `max_message`. The live store (`useLive().sessions`) holds every session with its
`name`, `status` and `repo`, kept current by the feed.

Where's closed box (`LaunchWhere.tsx`) shows the place's name, then `.place-path` or the
`Badge` `Project <title>`; on a narrow window the badge wraps to a second line.

The approved look: session artifacts `ui-design/new-session-dialog-2/spec` (§1–§9) and
`mockup.html` (states 1–12), with the human's answers on this run: F8 option B
(`mockup-task-name-phone.html`), no `Resume it`.

## Goals / Non-Goals

Goals: the name visible and editable on Task's label row; an automatic name that says what the
session is for; a typed name kept as the title; a project's place named without repeats; Where
on one line; "Kits" for the kits. Non-goals: see the proposal's Out of scope.

## Decisions

- **D1. The automatic name is computed in the browser, in a pure module `web/src/sessionName.ts`.**
  It needs the task as it is typed, the place's `default_name` and the sessions' names, all of
  which the window has; recomputing 300 ms after a keystroke needs no request. The server stays
  the authority: it slugs the name it gets and refuses a taken one (409). Rejected: an endpoint
  `GET /api/session-name?task=…&place=…` (one source in the core, but a request per pause, a new
  API and its types, and a stale answer racing the typing); a core rule for `lado start` with a
  prompt (no real user asked; "only what is used").
  Exports: `autoBase(task, placeBase)`, `freeName(base, taken)` (`base`, `base-2`, … as
  `runtime.free_name`), `slug(text)` (the core's `runtime.slug` without its `lado` fallback:
  empty for nothing left), `sessionName({mode, typed, task, placeBase, taken})` →
  `{id, title, base, numbered, taken}`. The key is the first match anywhere in the task of two
  or more capital Latin letters, `-` and digits, as a word of its own (`xLAD-263`, `LAD-263a`,
  `lad-263` are none); else the place's name. False keys (`UTF-8`, `HTTP-2`) are accepted: the
  name shows and can be changed before the start. The human set this rule during review
  (finding F2), in place of a key that starts the first line, else up to three of its words
  without filler: `LAD-263 Fix the login` gave `lad-263-fix`, and a name from words said little
  more than the place's.
- **D2. `slug` cannot drift from the core's.** The browser's `slug` and `runtime.slug` are checked
  against one case file, `web/src/sessionSlug.cases.json` (input → slug), by vitest and by a
  pytest, as `closedRefusals.cases.json` is shared today. Cases: `Review Kao` → `review-kao`,
  `Front.End` → `front-end`, `lad_263` → `lad_263`, `--a--` → `a`, `Вход` → `` (the core then
  says `lado`, the browser takes the automatic name), `Ünïcode` → `n-code` (the core does not
  fold accents; the browser's `slug` must not either).
- **D3. Taken names come from the live store**, `useLive().sessions`: every session's `name`,
  `status`, `repo`, already loaded and kept current by the feed, so a session started elsewhere
  numbers the name at once. Rejected: a `getSessions()` of its own on open and after a 409 (a
  second copy that goes stale). While the store has no list (loading or its error) the
  automatic name is not numbered; the 409 still guards the start.
- **D4. The window's state.** `nameMode: "auto" | "custom"` and `typed: string` replace `name`.
  An input event that leaves text sets `custom` and `typed`; one that leaves the field empty
  sets `auto`, the value stays empty while focused (the placeholder shows the automatic id) and
  becomes the automatic id on blur. The task feeds the rule through a 300 ms debounce, flushed
  on Task's blur and computed synchronously at the start. The draft keeps `name` as the typed
  name (null in auto), so an existing draft's `name` restores `custom` as before.
- **D5. id and title.** Custom: `id = slug(typed)`; fewer than 2 characters → the automatic
  id; `title = typed.trim()` when it differs from `id`, else none. The start sends `name: id`
  and `title` when there is one. Over `Limits.max_title` (the served value, not a copy of 80)
  the field is invalid with `Name: at most <n> characters.` and the start is off. A title the
  core refuses for a hidden character comes back as today's general refusal (rare; no second
  check in the browser).
- **D6. Notes under Task, one at a time**, `id` = the field's `aria-describedby`: taken (custom,
  `.bad`, `role="alert"`, `Name: a session named <id> exists (<status>, in <folder's last
  part>).` with `Use <next>`), too long, custom with title ≠ id (`Name shown as “<title>” · in
  links and branches: <id>`), auto numbered (`Name: <base> exists already, so this one is
  <id>.`). A 409 after the press keeps today's handling, its text and `Use <next>` in the same
  place, the focus on Name (`TeamRefs.name` moves to the new input), and no longer opens Team.
- **D7. The line under Where and the button keep the server's fields.** `Session <name> stopped
  here <when>` still comes from `name_state: "stopped_here"` of the place's `default_name`, and
  the button then reads `Start new session <id>` (the session's name, now possibly `lad-263`);
  Team's info drops `"<name>" is taken by another session.` (the numbered note says it).
- **D8. `runtime.project_session_name`** joins the slugs without repeats: `r` when `r == p` or
  `r` starts with `p-`; `p` when `p` ends with `-r`; else `p-r`. One function for the window's
  place and `lado start --project` (the human's answer to question 3).
- **D9. Where on one line.** `.place-text` nowrap; `.place-name` `flex: 0 1 auto`, no max width;
  `.place-sub` (was `.place-path`, now also a project's `in project <title>`) `flex: 0 1000 auto;
  min-width: min(12ch, 45%)`, so the secondary is cut first. `Badge` and `.place-badge` go. The
  box gets `title="<name> — <secondary>"`; Where's info button keeps the full sentence for a
  project and gains the full path for a folder. Recent rows the same, with the time last.
- **D10. Kits.** `LaunchTeam.tsx`: summary `Kits`, section **Kits** with an info button always
  (`Kits add roles, skills and ways of working to the team. Install more on the Kits page.`,
  then each chosen kit's `name: description`), `+ Add kit` (`aria-label="Add kit"`). `Launch.tsx`:
  footer `choose a kit`, Team's info `Kits and permissions are LADO's defaults.` and `Agent as
  in your last session; kits and permissions are LADO's defaults.` One word for one thing, as
  the Kits page and `--kit` say.
- **D11. Task's label row.** `.task-head` flex, `justify-content: space-between`, `gap: 12px`,
  `flex-wrap: wrap` (below ~300 px Name drops under Task's label); `.name-inline` `flex: 0 1
  300px`; at 760 px or less `.name-inline` `flex: 0 1 auto` and the input at most 140 px, so the
  free room falls between `Task ⓘ` and `Name ⓘ` (F8, option B). Input 30 px high, focus ring as
  `.place-box`, invalid `--danger`; tokens only.
- **D12. Tests at the lowest layer.** The rule is pure: vitest of `sessionName.ts` (the spec's
  examples table). The window's behaviour (recompute, custom, clear, notes, footer, Kits, Where)
  in vitest of `Launch.test.tsx` / `LaunchTeam.test.tsx` / `LaunchWhere.test.tsx`. The core rule:
  pytest unit (`tests/test_runtime_projects.py`), the server's `default_name` in
  `tests/test_server_project_launch.py`. In a browser (UI e2e): a start with a task posts the
  automatic name and the session's page opens under it; a typed name starts with its title; the
  phone's label row (F8) and Where on one line at 390 px. No process crossing changes, so no
  new integration test.
- **D13. A minor.** A new behaviour of the window and a changed default of `lado start
  --project`: CHANGELOG's `## 0.45.1 (unreleased)` becomes `## 0.46.0 (unreleased)`
  (docs/release.md: a feature bumps the minor); no API model changes, so `web/openapi.json` and
  `api.gen.ts` stay.

## Risks / Trade-offs

- A browser rule and a core slug: guarded by D2's shared cases.
- The CLI's default for a project changes (D8): an older stopped `<project>-<repo>` session is
  no longer resumed by `lado start --project` without `--name`, and a default name held outside
  the project is refused with the core's hint to give `--name`. CHANGELOG says how to resume the
  older one by its name.
- The automatic name changes under the human's eyes while they type: only 300 ms after the last
  keystroke, never once they typed in Name.
