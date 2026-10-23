## ADDED Requirements

### Requirement: lado project set --secret stores a secret in its own file

`lado project set <id> NAME --secret` SHALL store the value as the project's secret
`NAME` in the file `<LADO_HOME>/projects/<id>/secrets/NAME`, the file's content being the
value, making the folders it lacks; each folder of `<LADO_HOME>/projects/<id>/secrets`
SHALL have the mode 700 and the file 600. It SHALL print `Set secret <NAME> in project
<id>.` and then the agents' line of `lado project set`. No value of a secret SHALL be
stored in `lado.db`.

#### Scenario: First secret
- **WHEN** project `shop` has no secret and the human runs `lado project set shop GH_TOKEN
  --secret` and types `ghp_1`
- **THEN** `<LADO_HOME>/projects/shop/secrets/GH_TOKEN` holds `ghp_1`, its mode is 600, the
  folders `projects/shop`, `shop` and `secrets` are 700, and it prints `Set secret GH_TOKEN
  in project shop.` and `Agents started from now on get it.`

### Requirement: The secret's value is asked without echo, or read from stdin

On a terminal, `lado project set <id> NAME --secret` SHALL ask `Value of <NAME> (not
shown): ` and read one line without echo. When stdin is no terminal it SHALL read the
whole of stdin as the value, one line break at its end (`\n` or `\r\n`) dropped.

#### Scenario: From a pipe
- **WHEN** the human runs `printf 'ghp_2\n' | lado project set shop GH_TOKEN --secret`
- **THEN** the secret `GH_TOKEN` of `shop` is `ghp_2`, and nothing is asked

#### Scenario: Several lines
- **WHEN** stdin holds `line1\nline2\n`
- **THEN** the secret is `line1\nline2`

### Requirement: A secret's value is never given on the command line

`lado project set <id> NAME VALUE --secret` SHALL refuse, exit 1 with `lado: a secret's
value is never given on the command line (ps and the shell's history keep it); run lado
project set <id> <NAME> --secret and type it, or pipe it in`, and store nothing.

#### Scenario: The value as an argument
- **WHEN** the human runs `lado project set shop GH_TOKEN ghp_3 --secret`
- **THEN** it exits 1 with that text and `shop` keeps its secrets as they were

### Requirement: A secret is a non-empty short text

A secret's value SHALL be at most 64 KiB of UTF-8 text without NUL, by the rule of a
plain variable's value, and SHALL NOT be empty: an empty value SHALL exit 1 with `lado:
the secret <NAME> is empty; to remove it: lado project unset <id> <NAME>`, storing
nothing.

#### Scenario: Enter only
- **WHEN** the human runs `lado project set shop GH_TOKEN --secret` and presses Enter
- **THEN** it exits 1 with `lado: the secret GH_TOKEN is empty; to remove it: lado project
  unset shop GH_TOKEN`

#### Scenario: Too large
- **WHEN** stdin holds 70 000 bytes
- **THEN** it exits 1 with `lado: the value of GH_TOKEN is larger than 64 KiB`, and nothing
  is stored

### Requirement: Setting a secret again replaces it atomically

A secret set again SHALL replace the old value: the new value SHALL be written to a new
file in the same folder and renamed over the old one, so that a reader finds the old
value or the new one, never a part, and no temporary file stays, also when the write
fails. Secrets set at once by the CLI and the server SHALL not overwrite each other's
names.

#### Scenario: Replace
- **WHEN** `shop` has `GH_TOKEN=ghp_1` and the human sets it again to `ghp_4`
- **THEN** the file holds `ghp_4`, its mode is 600, and `secrets/` holds no other file

#### Scenario: A failed write
- **WHEN** writing the new value fails (the disk is full)
- **THEN** the command exits 1 naming the failure, the file still holds `ghp_1`, and no
  temporary file stays

### Requirement: A secret's name is checked by the variables' rule

A secret's name SHALL be checked by the rule of a project variable's name: a name that is
no variable name, or a reserved one, SHALL be refused with that rule's text. Any other
name SHALL be accepted, also one that does not look like a secret.

#### Scenario: A reserved name
- **WHEN** the human runs `printf x | lado project set shop LADO_HOME --secret`
- **THEN** it exits 1 with `lado: LADO_HOME is reserved: LADO or the agent CLIs set it`,
  and nothing is stored

#### Scenario: A name that does not look like a secret
- **WHEN** the human runs `printf 'postgres://u:p@db/x' | lado project set shop
  DATABASE_URL --secret`
- **THEN** `DATABASE_URL` is a secret of `shop`

### Requirement: A name is a plain variable or a secret, never both

A project SHALL hold one value per name. Setting a secret whose name is a plain variable
of the project SHALL exit 1 with `lado: <NAME> is a plain variable of <id>; remove it
first with lado project unset <id> <NAME>`, and setting a plain variable whose name is a
secret of the project SHALL exit 1 with `lado: <NAME> is a secret of <id>; remove it
first with lado project unset <id> <NAME>`; neither stores anything.

#### Scenario: A plain variable made a secret
- **WHEN** `shop` has the plain variable `DATABASE_URL` and the human runs `lado project
  set shop DATABASE_URL --secret`
- **THEN** it exits 1 with `lado: DATABASE_URL is a plain variable of shop; remove it first
  with lado project unset shop DATABASE_URL`, and the plain variable stays

#### Scenario: A secret set as a plain variable
- **WHEN** `shop` has the secret `DATABASE_URL` and the human runs `lado project set shop
  DATABASE_URL postgres://x`
- **THEN** it exits 1 with `lado: DATABASE_URL is a secret of shop; remove it first with
  lado project unset shop DATABASE_URL`

### Requirement: lado project show lists the project's secrets by name

`lado project show <id>` SHALL print, after the variables, `  secrets:` and one line per
secret, `    <NAME>`, by name; with none, `  secrets: none`. It SHALL list them without
opening any file: each file of the secrets folder that is no link, has a variable name and
is not reserved (a file the agents still cannot take, for its size or content, is named
by `lado doctor`).

#### Scenario: Two secrets
- **WHEN** `shop` has the secrets `YOUGILE_API_KEY` and `GH_TOKEN`
- **THEN** `lado project show shop` ends with `  secrets:`, `    GH_TOKEN` and
  `    YOUGILE_API_KEY`, and no value

### Requirement: No secret is written or removed through a symbolic link

Writing or removing a secret SHALL refuse, exit 1 with `lado: <path> is a symbolic link:
LADO writes and removes a project's secrets only in its own folders`, and touch nothing,
when `<LADO_HOME>/projects`, `<LADO_HOME>/projects/<id>`, its `secrets` or the secret's
file is a symbolic link; no link SHALL be followed on the way.

#### Scenario: secrets/ is a link
- **WHEN** `<LADO_HOME>/projects/shop/secrets` is a link to `/tmp/elsewhere` and the human
  sets a secret of `shop`
- **THEN** it exits 1 naming `<LADO_HOME>/projects/shop/secrets`, and `/tmp/elsewhere`
  holds no new file

#### Scenario: projects/ or the project's folder is a link
- **WHEN** `<LADO_HOME>/projects` or `<LADO_HOME>/projects/shop` is a link
- **THEN** setting and removing a secret of `shop` exit 1 naming that link

#### Scenario: The secret's file is a link
- **WHEN** `<LADO_HOME>/projects/shop/secrets/GH_TOKEN` is a link to `/tmp/t`, and the human
  sets or unsets `GH_TOKEN`
- **THEN** it exits 1 naming the file, and the link and `/tmp/t` stay as they were

### Requirement: The server sets and removes a project's secrets

`PUT /api/projects/{id}/secrets/{name}` with `{value}` SHALL set or replace a secret and
`DELETE /api/projects/{id}/secrets/{name}` remove one, both with the token for changes
(`guard.changes`), by the same rules as the CLI, answering `{project, running}` as the
variables' endpoints do. No endpoint SHALL return a secret's value.

#### Scenario: Set through the API
- **WHEN** the LADO manager sends `PUT /api/projects/shop/secrets/GH_TOKEN` with
  `{"value": "ghp_5"}`
- **THEN** the secret is stored, and the answer's `project.secrets` holds `"GH_TOKEN"` and
  no `ghp_5` anywhere

### Requirement: The server refuses a secret as the CLI does

An unknown project SHALL be 404, an unknown secret on `DELETE` 404, and a refused name or
value or a name held by a plain variable 400 with the refusal's text, nothing stored. A
request on these routes the server cannot read (422) SHALL answer without the input it
was given.

#### Scenario: An empty value through the API
- **WHEN** the UI sends `PUT /api/projects/shop/secrets/GH_TOKEN` with `{"value": ""}`
- **THEN** the answer is 400 with `the secret GH_TOKEN is empty; …`

#### Scenario: A body the server cannot read
- **WHEN** a client sends `PUT /api/projects/shop/secrets/GH_TOKEN` with `{"secret":
  "ghp_6"}`
- **THEN** the answer is 422 and holds no `ghp_6`

#### Scenario: A secret through the variables' route
- **WHEN** `shop` has the secret `GH_TOKEN` and the UI sends `DELETE
  /api/projects/shop/variables/GH_TOKEN`
- **THEN** the answer is 404 and the secret stays

### Requirement: Deleting a project removes its data folder

`lado project delete <id> --yes` SHALL remove `<LADO_HOME>/projects/<id>/` with its
secrets after the project folder and the sessions and before the record. When
`<LADO_HOME>/projects`, `<LADO_HOME>/projects/<id>`, its `secrets` or a file in it is a
symbolic link, it SHALL refuse before removing anything, exit 1 naming the link, and keep
the project.

#### Scenario: Delete, then create again
- **WHEN** `shop` has the secret `GH_TOKEN`, the human runs `lado project delete shop
  --yes` and then `lado project create shop`
- **THEN** `<LADO_HOME>/projects/shop` was removed, and `lado project show shop` prints
  `  secrets: none`

#### Scenario: A link in the data folder
- **WHEN** `<LADO_HOME>/projects/shop/secrets` is a link and the human runs `lado project
  delete shop --yes`
- **THEN** it exits 1 naming the link, and the project, its folder and the link's target
  stay

## MODIFIED Requirements

### Requirement: lado project create refuses with its reason and makes nothing

`lado project create` SHALL refuse, exit 1 with `lado: <reason>`, and make no record and
no folder, when the id breaks the id rule, a project of that id exists,
`<workspace>/projects/<id>` exists, `<LADO_HOME>/projects/<id>` exists (left by a project
of that id whose deletion failed), `projects/` is the human's own folder, or the
workspace is not a folder LADO can make or write in (`lado doctor`'s reason).

#### Scenario: A bad id
- **WHEN** the human runs `lado project create Shop`
- **THEN** it exits 1 with `lado: the project id Shop is not valid: lowercase Latin
  letters, digits and -, starting with a letter or digit, at most 40 characters`, and
  nothing is made

#### Scenario: A taken id
- **WHEN** LADO has the project `shop` and the human runs `lado project create shop`
- **THEN** it exits 1 with `lado: project shop exists`

#### Scenario: The folder exists
- **WHEN** `~/workspace/projects/shop` exists with no project `shop` in LADO and the human
  runs `lado project create shop`
- **THEN** it exits 1 with `lado: <folder> already exists: LADO makes a project's folder
  itself; choose another id or move that folder away`, and LADO has no project `shop`

#### Scenario: The data folder is left
- **WHEN** `<LADO_HOME>/projects/shop` exists with no project `shop` in LADO and the human
  runs `lado project create shop`
- **THEN** it exits 1 with `lado: <LADO_HOME>/projects/shop is left from a project shop:
  remove it or choose another id`, and LADO has no project `shop`

#### Scenario: A workspace that is a file
- **WHEN** `LADO_REPOS=/srv/notes`, a regular file, and the human runs `lado project create
  shop`
- **THEN** it exits 1 with `lado: LADO_REPOS is not a folder: /srv/notes`

### Requirement: lado project delete --yes removes the folder, then the record

`lado project delete <id> --yes` SHALL remove the project folder whole, then forget each
of the sessions it listed (as `lado forget --force` does), then remove its data folder
`<LADO_HOME>/projects/<id>/`, then the record, and print `Deleted project <id>`. A project
whose folder is not found SHALL lose its sessions, data folder and record only. When the
folder or the data folder cannot be removed whole, the record SHALL stay and the command
SHALL exit 1 naming what stayed.

#### Scenario: Confirmed
- **WHEN** the human runs `lado project delete shop --yes`
- **THEN** `<ws>/projects/shop`, `<LADO_HOME>/projects/shop` and the record are gone, and
  `<ws>/projects` and the rest of the workspace are as they were

#### Scenario: The folder already gone
- **WHEN** the folder of `acme` is not found and the human runs `lado project delete acme
  --yes`
- **THEN** the record is gone and no folder is touched

#### Scenario: With stopped sessions
- **WHEN** `shop-frontend` of project `shop` is stopped and the human runs `lado project
  delete shop --yes`
- **THEN** the folder, the session `shop-frontend` with its history, and the record are
  gone, and `lado ls` no longer lists it

### Requirement: Agents cannot change projects

`lado project create`, `rename`, `delete`, `set` (with `--secret` too), `unset`, `repo
add` and `repo remove` SHALL refuse, exit 1 with `lado: lado project <command> is for the
human; agent "<agent>" cannot use it` and change nothing, when `LADO_AGENT` is set (every
agent of LADO has it). `list` and `show` SHALL work for agents. LADO SHALL offer no MCP
tool that makes, changes or deletes a project, its repositories, its variables or its
secrets.

#### Scenario: From an agent
- **WHEN** a worker runs `lado project create shop` in its shell
- **THEN** it exits 1 with that text, and no project or folder is made

#### Scenario: Adding a repository from an agent
- **WHEN** a worker runs `lado project repo add shop --new site` in its shell
- **THEN** it exits 1 with `lado: lado project repo add is for the human; agent
  "<agent>" cannot use it`, and no folder `site` is made

#### Scenario: Setting a variable from an agent
- **WHEN** a worker runs `lado project set shop MODEL_URL http://evil` in its shell
- **THEN** it exits 1 with `lado: lado project set is for the human; agent "<agent>"
  cannot use it`, and `shop` keeps its variables as they were

#### Scenario: Setting a secret from an agent
- **WHEN** a worker runs `printf x | lado project set shop GH_TOKEN --secret` in its shell
- **THEN** it exits 1 with `lado: lado project set is for the human; agent "<agent>"
  cannot use it`, before reading stdin, and `shop` keeps its secrets as they were

### Requirement: The server gives a project with its repositories

`GET /api/projects/{id}` SHALL answer `{id, title, folder, found, repos, variables,
secrets}`, `repos` the project's repositories as `{name, path, remote, branch}`,
`variables` its variables as `{name, value}` by name, `secrets` the names of its secrets
(as `lado project show` lists them, never a value), and 404 for an unknown id.

#### Scenario: A project
- **WHEN** the UI asks `GET /api/projects/shop`
- **THEN** the answer has `id: "shop"`, its title, its folder, `found: true`, its
  repositories as `lado project show` lists them, its variables and its secrets' names

### Requirement: lado project unset removes a plain variable

`lado project unset <id> NAME` SHALL remove the project's plain variable or secret `NAME`
and print `Removed <NAME> from project <id>.` and then `Agents started from now on do not
get it; running sessions of <id> keep the old environment until restarted: <names>`, or
`Agents started from now on do not get it.` when no session of the project runs. A name
the project lacks SHALL exit 1 with `lado: project <id> has no variable or secret <NAME>;
its variables: <names>; its secrets: <names>` (`none` without any).

#### Scenario: Unset
- **WHEN** `shop` has `BOARD_URL` and no session of it runs, and the human runs `lado
  project unset shop BOARD_URL`
- **THEN** it prints `Removed BOARD_URL from project shop.` and `Agents started from now
  on do not get it.`, and `lado project show shop` prints `  variables: none`

#### Scenario: A name the project lacks
- **WHEN** `shop` has only `BOARD_URL` and the human runs `lado project unset shop MODEL_URL`
- **THEN** it exits 1 with `lado: project shop has no variable or secret MODEL_URL; its
  variables: BOARD_URL; its secrets: none`

#### Scenario: Unset a secret
- **WHEN** `shop` has the secret `GH_TOKEN` and the human runs `lado project unset shop
  GH_TOKEN`
- **THEN** `<LADO_HOME>/projects/shop/secrets/GH_TOKEN` is gone and it prints `Removed
  GH_TOKEN from project shop.`

### Requirement: A name that looks like a secret is no plain variable

The rule SHALL refuse a name with `TOKEN`, `KEY`, `SECRET` or `PASSWORD` in it, in any
case, as a plain variable, with `<NAME> looks like a secret (<word>): a plain variable
takes no name with TOKEN, KEY, SECRET or PASSWORD; set it as a secret with lado project
set <id> <NAME> --secret`.

#### Scenario: A secret's name
- **WHEN** the human runs `lado project set shop GH_TOKEN x`
- **THEN** it exits 1 with `lado: GH_TOKEN looks like a secret (TOKEN): …` and `shop` has no
  `GH_TOKEN`

#### Scenario: Lowercase is a secret's name too
- **WHEN** the human runs `lado project set shop yougile_api_key x`
- **THEN** it exits 1 naming `KEY`
