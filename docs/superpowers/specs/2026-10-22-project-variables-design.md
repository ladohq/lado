# Project variables (LAD-130)

Change: `openspec/changes/project-variables/` (proposal with AC-1..AC-14, delta specs of
`projects` and `agent-variables`, `design.md` with the decisions D1-D13). Step S5a of the
epic LAD-116 (`docs/epics/lad-116/plan.md`); the model is `docs/design/projects.md`. This
document is the human's view: what a user gets, what was decided with the human, and how
the human checks it. No mockup: no screen changes.

## What a user gets

- **A plain variable per project**:
  ```
  $ lado project set shop BOARD_URL https://ru.yougile.com
  Set BOARD_URL in project shop.
  Agents started from now on get it; running sessions of shop keep the old environment until restarted: shop-frontend
  $ lado project unset shop BOARD_URL
  Removed BOARD_URL from project shop.
  Agents started from now on get it; running sessions of shop keep the old environment until restarted: shop-frontend
  ```
- **`lado project show`** lists them with their values:
  ```
  shop "Shop"
    folder:  /Users/ann/workspace/projects/shop
    made:    2026-10-22 18:40
    repositories:
      frontend  main  https://github.com/shop/frontend
    variables:
      BOARD_URL  https://ru.yougile.com
      MODEL_URL  http://localhost:11434
  ```
- **The whole session in the project gets them**: its supervisor, its workers, its flow
  runs' workers, the session its supervisor starts, and, as their children, the CLI's
  subagents and the kits' MCP servers. Two sessions of two projects with one name each
  get their own value; a session without a project gets none.
- **The layers**: login shell → outside folder (`LADO_ENV_DIR`, `/run/secrets` in Docker)
  → the project → LADO and the agent CLI. The project wins over the outside folder; LADO's
  own variables win over the project (refused at `set` anyway).
- **Kit keys**: a kit's MCP server that needs `${NAME}` starts in a session whose project
  sets `NAME`, even when nothing else does.
- **Refused names**:
  ```
  $ lado project set shop GH_TOKEN x
  lado: GH_TOKEN looks like a secret (TOKEN): a plain variable takes no name with TOKEN, KEY, SECRET or PASSWORD; secrets come with lado project set shop GH_TOKEN --secret (not built yet)
  $ lado project set shop CLAUDE_CONFIG_DIR /tmp/c
  lado: CLAUDE_CONFIG_DIR is reserved: LADO or the agent CLIs set it
  $ lado project set shop A-B x
  lado: the name A-B is not a variable name: Latin letters, digits and _, not starting with a digit
  ```
- **`lado doctor`**, when a project overrides a variable of the outside folder:
  `[info] Project variables: shop overrides BOARD_URL of LADO_ENV_DIR`.
- **From an agent** `set` and `unset` refuse; `show` works (plain values are visible).
- **The server's API** for the UI to come (S6) and the LADO manager: `variables` in `GET
  /api/projects/{id}`, `PUT` and `DELETE /api/projects/{id}/variables/{name}`.

## What was decided with the human (#966)

1. **Kit keys named like secrets wait for S5b.** `YOUGILE_API_KEY` and `GH_TOKEN` cannot be
   plain variables (the concept's rule); in S5a the kit-key path works and is tested with
   plain names, and the secrets of S5b use the same layer.
2. **Reserved names are exact**: the shell's and terminal's names, every `LADO_*`, and the
   names LADO sets for the CLIs (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `OPENCODE_CONFIG*`,
   `OPENCODE_DISABLE_AUTOUPDATE`, `KILO_CONFIG*`, `KILO_DISABLE_AUTOUPDATE`,
   `KILO_NO_DAEMON`), not whole prefixes, so a project can still set the CLIs' own model
   settings. A name that looks like a secret: `TOKEN`, `KEY`, `SECRET`, `PASSWORD`
   anywhere, in any case.
3. **The texts** of `set`, `unset`, `show` and `lado doctor` as above.

## The security boundary

Projects of one LADO share the environment's machinery but are not isolated: every agent
runs as the same operating-system user and can read another project's files and values.
For clients that must not mix, run a separate LADO. `docs/design/projects.md` says so.

## Manual check

Branch `feature/lad-130-project-variables`, from a checkout of it (never the human's own
LADO):

```bash
env | grep LADO_          # unset whatever a previous test left: unset LADO_HOME LADO_REPOS …
export LADO_HOME=$(mktemp -d) LADO_REPOS=$(mktemp -d) LADO_TMUX_SOCKET=lado-s5a
uv run lado project create shop && uv run lado project create acme
uv run lado project repo add shop --new web && uv run lado project repo add acme --new web
uv run lado project set shop BOARD_URL https://a
uv run lado project set acme BOARD_URL https://b
uv run lado project show shop                 # variables: BOARD_URL  https://a
uv run lado start --project shop --repo web --no-attach
uv run lado start --project acme --repo web --no-attach
uv run lado attach shop-web                   # in the supervisor's window: ask it to run `echo $BOARD_URL` → https://a
uv run lado attach acme-web                   # → https://b
uv run lado project set shop MODEL_URL http://x   # names shop-web as running
uv run lado project unset shop BOARD_URL
uv run lado project set shop GH_TOKEN x       # refused: looks like a secret
uv run lado project set shop PATH /tmp        # refused: reserved
uv run lado stop --all; tmux -L lado-s5a kill-server; unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET
```

Expected: each step as in "What a user gets"; after `unset`, a session started anew in
`shop` has no `BOARD_URL`.
