# Project secrets (LAD-132)

Change: `openspec/changes/project-secrets/` (proposal with AC-1..AC-14, delta specs of
`projects` and `agent-variables`, `design.md` with the decisions D1-D15). Step S5b of the
epic LAD-116 (`docs/epics/lad-116/plan.md`); the model is `docs/design/projects.md`. This
document is the human's view: what a user gets, what was decided with the human, and how
the human checks it. No mockup: no screen changes (the UI of secrets is S6).

## What a user gets

- **A secret per project**, asked without echo, or read from a pipe:
  ```
  $ lado project set shop GH_TOKEN --secret
  Value of GH_TOKEN (not shown):
  Set secret GH_TOKEN in project shop.
  Agents started from now on get it.
  $ printf %s "$(gh auth token)" | lado project set shop GH_TOKEN --secret
  Set secret GH_TOKEN in project shop.
  Agents started from now on get it; running sessions of shop keep the old environment until restarted: shop-frontend
  $ lado project unset shop GH_TOKEN
  Removed GH_TOKEN from project shop.
  Agents started from now on do not get it.
  ```
- **Never read back.** `lado project show` names the secrets, without values:
  ```
  shop "Shop"
    folder:  /Users/ann/workspace/projects/shop
    made:    2026-10-22 18:40
    repositories:
      frontend  main  https://github.com/shop/frontend
    variables:
      BOARD_URL  https://ru.yougile.com
    secrets:
      GH_TOKEN
      YOUGILE_API_KEY
  ```
- **Where they are.** `~/.lado/projects/shop/secrets/GH_TOKEN` (in LADO's image on the
  home volume, not in the workspace), one file per secret, folders 700, files 600, in the
  form of Docker's `/run/secrets`. A backup of the volume holds them; `lado uninstall`
  removes them with `~/.lado`; `lado project delete shop --yes` removes them with the
  project.
- **The whole session in the project gets them**, as plain variables: the supervisor, the
  workers, the flow runs' workers, the session the supervisor starts, and the CLI's
  subagents and the kits' MCP servers as their children. A kit's key (`YOUGILE_API_KEY`,
  `GH_TOKEN`) set only as the project's secret counts as set: the epic's goal, sessions
  for different clients with different keys, is reached.
- **The layers**: login shell → outside folder (`LADO_ENV_DIR`, `/run/secrets`) → the
  project (variables and secrets) → LADO and the agent CLI. A project's secret wins over
  the outside one of the same name; `lado doctor` says so: `[info] Project variables: shop
  overrides GH_TOKEN of LADO_ENV_DIR`.
- **Refusals**:
  ```
  $ lado project set shop GH_TOKEN ghp_x --secret
  lado: a secret's value is never given on the command line (ps and the shell's history keep it); run lado project set shop GH_TOKEN --secret and type it, or pipe it in
  $ lado project set shop GH_TOKEN --secret      (Enter only)
  lado: the secret GH_TOKEN is empty; to remove it: lado project unset shop GH_TOKEN
  $ lado project set shop DATABASE_URL --secret  (DATABASE_URL is a plain variable)
  lado: DATABASE_URL is a plain variable of shop; remove it first with lado project unset shop DATABASE_URL
  $ lado project set shop GH_TOKEN x
  lado: GH_TOKEN looks like a secret (TOKEN): a plain variable takes no name with TOKEN, KEY, SECRET or PASSWORD; set it as a secret with lado project set shop GH_TOKEN --secret
  ```
- **A secret file LADO cannot take** (made readable by others, a link, too large, a bad
  name) is not given to agents and is named, never shown: in the warnings of a session's
  start and in `lado doctor`, e.g. `[warn] Project secrets: shop: GH_TOKEN not used:
  readable or writable by others: chmod 600 it`.
- **The server's API**, for the UI of S6 and the LADO manager (with the change token):
  `PUT` and `DELETE /api/projects/{id}/secrets/{name}`, and `secrets` (names) in `GET
  /api/projects/{id}`. Nothing returns a value.

## What was decided with the human

1. **One value per name** (#1060): a name is a plain variable or a secret; setting the
   other kind is refused with the hint to `unset` first.
2. **Any name may be a secret** (#1062), also one that does not look like one
   (`DATABASE_URL` with a password in it); reserved and invalid names stay refused.
3. **The launch file** (#1064): a secret reaches the agent's window as every key does
   today, through `env.json` (600) in the agent's config folder, removed by the window as
   it starts; never through a process's arguments or the tmux server's environment.
4. **Entering the value** (#1066): asked once without echo, or the whole stdin without a
   terminal; never on the command line; an empty value refused.
5. **Loose permissions** (#1068): a secret file others may read or write is not used and
   is named, as ssh does with a key.

## The security boundary

Projects of one LADO are not isolated: every agent runs as the same operating-system user
and can read another project's secrets. For clients that must not mix, run a separate
LADO. `docs/design/projects.md` and `docs/install.md` say so.

## Manual check

Branch `feature/lad-132-project-secrets`, from a checkout of it (never the human's own
LADO):

```bash
env | grep LADO_          # unset whatever a previous test left: unset LADO_HOME LADO_REPOS …
export LADO_HOME=$(mktemp -d) LADO_REPOS=$(mktemp -d) LADO_TMUX_SOCKET=lado-s5b
uv run lado project create shop && uv run lado project repo add shop --new web
uv run lado project set shop GH_TOKEN --secret        # type s5b-one; nothing is echoed
printf 's5b-two\n' | uv run lado project set shop YOUGILE_API_KEY --secret
uv run lado project show shop                         # secrets: GH_TOKEN, YOUGILE_API_KEY; no value
ls -la "$LADO_HOME/projects" "$LADO_HOME/projects/shop" "$LADO_HOME/projects/shop/secrets"   # drwx------ / -rw-------
uv run lado start --project shop --repo web --no-attach
uv run lado attach shop-web                           # ask the supervisor: echo $GH_TOKEN → s5b-one
printf 's5b-three' | uv run lado project set shop GH_TOKEN --secret   # replace; names shop-web as running
uv run lado project set shop GH_TOKEN x --secret      # refused: value on the command line
uv run lado project unset shop YOUGILE_API_KEY        # "do not get it"
mv "$LADO_HOME/projects/shop/secrets" /tmp/s5b-moved && ln -s /tmp/s5b-moved "$LADO_HOME/projects/shop/secrets"
printf x | uv run lado project set shop GH_TOKEN --secret   # refused: names the link
rm "$LADO_HOME/projects/shop/secrets" && mv /tmp/s5b-moved "$LADO_HOME/projects/shop/secrets"
uv run lado doctor                                    # no value anywhere
grep -r s5b- "$LADO_HOME" --exclude-dir=secrets       # nothing
uv run lado stop --all; uv run lado project delete shop --yes
ls "$LADO_HOME/projects"                              # no shop
uv run lado project create shop && uv run lado project show shop   # secrets: none
tmux -L lado-s5b kill-server; unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET
```

Expected: each step as in "What a user gets".
