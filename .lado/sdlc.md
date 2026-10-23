# sdlc settings

The project's settings for the LADO kit `sdlc`. The human keeps this file; agents read it
at the start of every step.

## Languages

- Chat with the human: Russian
- Pull request description and comments: English
- Tracker (Yougile): Russian, everything written there: task titles, descriptions and
  comments; the team has no English-speaking developers
- Commit messages: English, the repository's own style: a plain sentence that says what
  the change does (no `<type>:` prefix), the task key at its end in parentheses
  (`The artifact tab scrolls a long record (DEV-12)`); the body says why, not what
- openspec documents and design docs: English

## Git

- Remote: `origin` (github.com/ladohq/lado, public)
- Base branch: `main`
- Epic branches (when the tracker has epics): `epic/<key>-<slug>`
- `<key>` is the task key as a name (skill `sdlc-settings`): `DEV-12` → `dev-12`
- Pull request branch: full `feature/<key>-<slug>`, hotfix `hotfix/<key>-<slug>`,
  tweak `fix/<key>-<slug>`; no date in the name
- Code host: GitHub, command-line tool `gh`

## Tracker

- Component labels: the sticker `Component` says which part of the system a task
  changes, one of `component lado`, `component kit-sdlc`, `component kit-builder`,
  `component kit-tracker-yougile`, `component kit-tracker-jira-server` (mapped in
  `.lado/tracker.yaml`). A task created through LADO gets the label of the part it
  changes; a task of this repository is `component lado`.
- Skipped issue types: none

## After the merge

`<X.Y.Z>` below is the version of CHANGELOG.md's `## X.Y.Z (unreleased)` heading on the
target branch after the merge.

Into the base branch:
- Post a comment by this template (Markdown):

  ```markdown
  **Слит PR #<n>** — войдёт в релиз <X.Y.Z>.

  **Для проверки: что смотреть**
  - <2-4 пункта: видимые изменения, сценарии, крайние случаи, риски регрессии>

  **Для разработчиков: что сделано**
  - <по слоям: ключевые решения, новые поля API/MCP/CLI, миграция схемы да/нет, CHANGELOG>
  ```

  Without an `(unreleased)` heading, its first line ends «— войдёт в следующий релиз.»
- Move the task to the status `done`.
- Add the label `waiting for release` (the sticker `Status: Ready`, "ready for the
  release", mapped in `.lado/tracker.yaml`). It stays on the task until the release that
  ships it removes it (docs/release.md, The final).
- Set the field `release` to `<X.Y.Z>` (the text sticker `Release`, mapped in
  `.lado/tracker.yaml`); without an `(unreleased)` heading, leave the field as it is.

Into an epic branch:
- Post the comment above with the first line «**Слит PR #<n> в эпик-ветку `<branch>`** —
  войдёт в релиз вместе с эпиком.»; change nothing else: the task stays in review.

## Checks

| Command | Run from | Notes |
|---|---|---|
| `make lint` | root | ruff format --check + ruff check |
| `make test` | root | unit tests, `-n auto`; report tests as numbers |
| `uv run pytest -m integration -n auto <changed files>` | root | the changed or added files under `tests/integration/`; the marker is required |
| `uv run pytest -m ui <changed files>` | root | when `web/` or `tests/ui/` changed; screenshots in `<temp dir>/lado-ui-shots/` |
| `make test-js` | root | when `src/lado/providers/opencode_plugin.js` or `tests/js/` changed |
| `make web` | root | when `web/` or the server's API models changed (stale-types check) |
| `openspec validate --specs --strict` | root | blind to contradictions between capabilities: grep `openspec/specs/` |
| `openspec validate <change> --strict` | root | the change itself, while it is open (not after its archive) |

- Excluded from a normal round:
  - `make check` and `make test-integration` as a whole: CI runs them on every push, and a
    full local run takes the machine-wide lock for many minutes;
  - `make test-live`: real models, run only at a release, Claude Code only with the
    human's yes;
  - `make test-smoke`: needs the real CLIs; CI runs it.
- What CI proves: on every pull request and push to main, `ruff format --check`,
  `ruff check`, the unit tests and the integration tests (three shards per Python) on
  Python 3.10 and 3.13, the Node tests, `make dist` and the UI e2e tests (two shards). The
  smoke tests on Linux and macOS per provider run on every push to main, daily on main,
  and on each pull request that changes a file off ci.yml's skip list (`web/`, `docs/`,
  `openspec/`, `tests/ui/`, `tests/js/`, the top-level Markdown documents,
  `.github/dependabot.yml`). The one required check is `ci-ok`: green means the full
  `make check` plus the smoke, but for a pull request within the skip list, where the
  smoke was skipped.
- CI time ceiling: 40 minutes

## External reviewer

- Reviewer: Claude Code GitHub Action (`anthropics/claude-code-action`), on the human's
  Claude subscription
- Request: a pull request comment that starts with `@claude review` and holds the delta
  comment of `review-loop`
- Finished: Claude's progress comment on the pull request, newer than the request, says
  `Claude finished`; its findings are in that comment
- Coverage: taken from the lists `Files read` and `Files not read` at the end of Claude's
  comment; a risky file of the diff that is not under `Files read` was not reviewed
  externally (and `Risky code not fully read` at the top of the comment says so)
- Time ceiling: 25 minutes
- Round cap: 2 for a full change, 1 for a hotfix or tweak
- It is the same model family as this kit's agents: weigh "nothing found" accordingly

## Review traps

- A test file of `tests/integration/` or `tests/ui/` run without its marker — `0 passed`,
  `no tests ran`, or a mixed run whose count lacks those files — run each layer as its
  own command with `-m integration` / `-m ui`.
- A gating check piped into `tail`, `grep` or `tee` — the pipe's exit status hides a red
  run — send it to a log outside the tree (`> /tmp/<name>.log 2>&1`), read the exit
  status, then the log.
- Two heavy test runs at once — `check lock: waiting for the run in …` — never start a
  second; wait for the first.
- A unit suite run without `-n auto` — it takes minutes — `-n auto` for suites, `-n0` for
  single node ids.
- A timeout failure under machine load (known flakes in BACKLOG.md, P1 "`make check`
  fails on timeouts") — the test passes when its node id is rerun alone with `-n0` and its
  marker — rerun it up to twice; a pass is a flake: record it in the ledger, do not change
  code for it.
- A CI job red with no cause in the work (a timeout, a runner or service that fails at
  random) — `gh run view <id>` names the failed job, step and test, and nothing in the
  diff or the target branch it meets explains it — the agent that waits for CI (the
  developer in `build`, the reviewer in `review`, the integrator in `merge`) reruns the
  failed jobs alone, `gh run rerun <id> --failed`, at most twice, without asking the
  supervisor first; any job of CI, the smoke included; never the whole run, never an
  automatic retry inside pytest. A pass on a rerun is a flake: name its job, step and
  test in the ledger (the developer in `build-report`, the integrator in its note);
  search the tracker for an open task on that test and name it when there is one,
  otherwise propose a task to the human at once with `ask_human` (as LAD-57), go on
  without waiting, and create it only on their "yes, create"; the reviewer, who has no
  tracker, leaves the search and the proposal to the supervisor with `send_message`.
  Red after the second rerun follows kit sdlc's "A red check".
- `web/openapi.json` or `web/src/api.gen.ts` stale after an API model change — `make web`
  fails its stale-types check — run `make web-types` and commit both files.
- A live test added or changed — it only collects without real CLIs — say "written, not
  run" in the build report; never claim it passed.
- An HTML mockup that inlines the UI's CSS (`web/src/styles.css`, after
  `web/src/tokens.css`) — it does not scroll in a window wider
  than 900px (`html, body { overflow: hidden; overscroll-behavior: none }`) — end its
  `<style>` with `html, body { height: auto !important; overflow: visible !important;
  overscroll-behavior: auto !important; }` (`overflow: auto` is not enough: the wheel
  still does not scroll) and check with the wheel that it scrolls to its end.

## Extra instructions

For all:
- Read AGENTS.md (Design principles, Rules, Testing) and ROADMAP.md before your step;
  AGENTS.md is the project's architecture document and wins over a general habit.
- Clean-room: never copy code, tests, prompt texts or file layout from other projects or
  agent CLIs; describe the behaviour in your own words, then write it.
- Defects or debt found outside the task do not grow the task: the reviewer lists them in
  the ledger under "Found on the way"; the developer adds each to BACKLOG.md (its
  template: tier P0-P3, `Size:` and `Why here:` lines, Found: date and branch) in the
  next build visit, in a commit of its own. This replaces `review-loop`'s "no finding
  becomes a debt entry". Never create a tracker task for them without the human's yes.

Analyst:
- In the design, name the root cause, give 2-3 options with their long-term cost, and
  hold the chosen one against ROADMAP.md's coming stages and AGENTS.md's Design principles
  (neutral core: works with at least two providers or says where not; one source of
  truth; no silent drops; only what is used). Put every decision the human must make
  under "Questions for the human" before design_ok.
- Name the test layer of each requirement (AGENTS.md, Testing: the lowest that can catch
  its bugs); behaviour that crosses processes needs an integration test with the fake
  agent.
- UI work: name the change to `docs/design/ui.md`, and attach an HTML mockup of each new
  or changed screen as a run artifact. A mockup that inlines the UI's CSS
  (`web/src/tokens.css`, then `web/src/styles.css`) takes its app-shell rules too: on a window wider than 900px
  `html, body { overflow: hidden; overscroll-behavior: none }` stops the page from
  scrolling, as only `.content` scrolls in the app. End the mockup's `<style>` with
  `html, body { height: auto !important; overflow: visible !important;
  overscroll-behavior: auto !important; }` (with `overflow: auto` the wheel still does
  not scroll), or put the screens inside the `.app`/`.content` frame, and before
  attaching check with the wheel that the page scrolls in a wide window to its last
  screen.
- Say in the design whether the change bumps the minor (feature, MCP tool or CLI change,
  schema migration) or the patch (fixes and docs only).

Developer:
- Edit files with your edit tools, not shell heredocs or `sed -i`. No sub-agents.
- Each change users see adds a line to CHANGELOG.md under `## X.Y.Z (unreleased)` (add
  that heading on top when it is missing; X.Y.Z is the next version by AGENTS.md's
  Versions rule), written by docs/release.md's rules for its items (CHANGELOG.md: its
  group, a bold title, at most three lines, the user's words). AGENTS.md is the
  project's map: add to it only what an agent needs in any task. Behaviour goes to `docs/design/agents.md`, `docs/design/modules.md`,
  `docs/testing.md`, `docs/cli.md` or the module's docstring; keep them true to the code
  in the same pull request.
- A schema change: bump `SCHEMA_VERSION`, add a step to `MIGRATIONS` and update
  `tests/agent_helpers.previous_schema`.
- UI work: build to the approved mockup, add a UI e2e test, and attach a screenshot of
  each changed screen as a run artifact listed in `build-report`.
- After three failed attempts at one fix, stop and tell the supervisor.

Reviewer:
- Besides the lenses, review the architecture against AGENTS.md: a provider detail
  leaking above `providers/`, a second source of truth, a silent drop, a new field no kit
  uses, a test at a higher layer than needed or a mock of the thing tested.
- UI work: check the screenshots against `docs/design/ui.md` and the approved mockup.
- Name a change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
  `agent_env.py` or `tests/live/` in the closing report: the human may want live tests
  before the merge.

Integrator:
- Never bump the version, date CHANGELOG.md or tag: a release is a separate task the
  human starts.
- After merging `origin/<target>` into the run's branch (the kit's Merge, step 2), run
  none of the settings' **Checks** locally but `openspec validate --specs --strict`
  (CI does not run it); with it green, push and wait for the pull request's CI, which
  runs the rest. A red CI then follows step 3 as written, after the Review trap's
  reruns for a CI job red with no cause in the work: the merge commit stays, and a
  cause in the work is `conflicts`, fixed by the developer on top. This replaces step
  2's local run of the Checks on this project.
