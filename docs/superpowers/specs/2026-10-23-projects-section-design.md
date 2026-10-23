# The Projects section and a project's variables (LAD-134)

Change: `openspec/changes/projects-section/` (proposal with AC-1..AC-14, the delta of
`projects`, `design.md` with D1-D16). Step S6a of the epic LAD-116; the model is
`docs/design/projects.md`. This document is the human's view: what a user gets, what was
decided with the human, and how the human checks it. Mockup: the run's artifact
`mockup-projects.html` (ten frames on LADO's own CSS: desktop and 390 px, light and dark).

## What was decided with the human

- **#1151: split.** S6a (this change): the Projects section, making a project, the
  project's variables and secrets. S6b (a new task): the Project way of New session.
- **#1153: the mockup's recommendations 1–10, all accepted.**
  1. The section is laid out as Sessions: the list at the left, the project at the right at
     `/projects/<id>`; on a phone one after the other (frames 1, 8, 9). Not cards (frame 2).
  2. Two blocks, Variables and Secrets, each with its own "+ Add" (frame 1), not one table
     with a kind column (frame 3).
  3. The page's head: title, id, `N repositories · N sessions running · folder …`, and one
     line for what S7 brings, with the CLI meanwhile.
  4. The security warning always above the variables, its short form in New project.
  5. The line "New values reach the agents started after a change…" always, with the
     running sessions as links.
  6. The core's "looks like a secret" refusal verbatim, with "Add NAME as a secret instead",
     which moves the name only (frame 5).
  7. New project: Title (optional) and Id, the id following the title, the core's refusal
     under Id (frames 6, 10); opened by the list's "+" or "New project…" (frame 7).
  8. `overrides outside value` with a tooltip, no outside value shown (frame 4).
  9. Remove asks in the row, for both kinds.
  10. The session head's `project Shop` becomes a link to the project.
- **#1158: adding repositories.** Through the CLI until S6b (with a start in New session)
  and S7 (on the project's page); the page's not-built line names the command.

## What a user gets

- **Projects** in the rail opens the list:
  ```
  Projects                              +
  [Find a project            ]
  ACME CRM
    acme · 1 repository · no sessions running
  Shop                                         ← selected
    shop · 2 repositories · 2 running
  sandbox  [folder not found]
    sandbox · 0 repositories
  ```
- **The project's page** at `/projects/shop`:
  ```
  Shop  shop
  2 repositories · 2 sessions running · folder ~/workspace/projects/shop
  Repositories, sessions, renaming and deleting the project: not built yet. Plan: Projects,
  step S7. Meanwhile: lado project show shop, lado project repo add shop <git-url>.

  ⚠ Projects of one LADO are not isolated from each other: an agent of one project can read
    another's variables and secrets. For clients that must not mix, run a separate LADO.
  New values reach the agents started after a change; running agents keep the environment
  they started with. Running now: Checkout redesign, shop-backend — restart a session to
  give it the change.

  Variables
  BOARD_URL        https://yougile.com/board/shop-team        Edit  Remove
  MODEL_BASE_URL   http://10.0.0.5:11434/v1                   Edit  Remove
  + Add variable

  Secrets
  GH_TOKEN                                   set · hidden      Replace  Remove
  YOUGILE_API_KEY [overrides outside value]  set · hidden      Replace  Remove
  SENTRY_DSN   ⚠ Agents do not get it: readable or writable by others: chmod 600 it
  + Add secret
  ```
- **A secret is never shown.** Add and Replace take the value in a hidden field, empty after
  saving; the server never sends a value back. Replace says `New value (the old one is not
  shown)`.
- **New project** makes the project and its folder, as `lado project create` does.
- **The session head** links `project Shop` to the project's page.

## Out of scope

The Project way of New session and "+ new repository" (S6b); the page's repositories,
sessions, rename and delete (S7); a live feed of projects (the page reads anew on open,
after a change, when a session of the project starts or stops, and on focus); global
variables; outside secrets per project; isolation.

## How the human checks it

From a checkout of the pull request's branch `feature/lad-134-projects-section` in its own
folder (never the working copy you work in):

```bash
git fetch origin && git switch feature/lad-134-projects-section   # in a separate clone/worktree
pwd && git branch --show-current                                   # the folder and the branch
env | grep LADO_                      # what your shell gives LADO; unset each, e.g.:
unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET LADO_ENV_DIR
export LADO_HOME=$(mktemp -d) LADO_REPOS=$(mktemp -d) LADO_TMUX_SOCKET=lado-check-134
make web && uv run lado server        # open the URL it prints
```

1. Projects shows `No projects yet` and `New project…`.
2. New project: type `Магазин EU`; Id reads `magazin-eu` with its folder; Create opens it.
   Again with the title `magazin eu`: `project magazin-eu exists` under Id, Create disabled.
3. Add the variable `BOARD_URL` `https://a`; edit it; add `STRIPE_KEY` `x`: the refusal and
   "Add STRIPE_KEY as a secret instead"; click it: the secret form has the name, the value
   is empty.
4. Add the secret `STRIPE_KEY` `sk_check_134`; the field is empty after it. In the browser's
   dev tools: Application → Local and Session storage hold no `sk_check_134`; Network: the
   value only in the `PUT …/secrets/STRIPE_KEY` request's body.
5. Make an outside folder (`export LADO_ENV_DIR=$(mktemp -d); printf out >
   $LADO_ENV_DIR/GH_TOKEN`), restart the server, add the secret `GH_TOKEN`: its row is marked `overrides outside value`, and `out`
   is nowhere on the page.
6. `chmod 644 $LADO_HOME/projects/magazin-eu/secrets/STRIPE_KEY`, reload: `Agents do not get
   it: readable or writable by others: chmod 600 it`; Replace it: the warning goes.
7. Start a session in the project (`uv run lado start --project magazin-eu --repo app` after
   `uv run lado project repo add magazin-eu --new app`): the page's line names it as a
   link without a reload; its head links `project Магазин EU` back to the project.
8. Remove a variable and a secret: each asks in its row first.
9. At the end: `tmux -L lado-check-134 kill-server; rm -rf "$LADO_HOME" "$LADO_REPOS" "$LADO_ENV_DIR"`.
