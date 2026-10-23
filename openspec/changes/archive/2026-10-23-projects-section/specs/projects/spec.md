## MODIFIED Requirements

### Requirement: The server gives a project with its repositories

`GET /api/projects/{id}` SHALL answer `{id, title, folder, found, repos, variables,
secrets, running, overrides, unused}`, `repos` the project's repositories as `{name, path,
remote, branch}`, `variables` its variables as `{name, value}` by name, `secrets` the names
of its secrets (as `lado project show` lists them, never a value), `running` the names of
its sessions that are not stopped, and 404 for an unknown id. The routes that change a
project SHALL answer it in this form.

#### Scenario: A project
- **WHEN** the UI asks `GET /api/projects/shop`
- **THEN** the answer has `id: "shop"`, its title, its folder, `found: true`, its
  repositories as `lado project show` lists them, its variables and its secrets' names

#### Scenario: Running sessions
- **WHEN** `shop-frontend` of `shop` runs and `shop-backend` is stopped
- **THEN** `running` is `["shop-frontend"]`

## ADDED Requirements

### Requirement: The server's project names what overrides and what its agents do not get

A project's `overrides` SHALL be the names of its variables, and of its secrets its agents
get, that the outside folder (`LADO_ENV_DIR`) gives too, sorted; its `unused` the entries
of its secrets folder its agents do not get as `{name, reason}` (`name` null for the folder
itself), as `lado doctor` names them. No field SHALL hold a value of a secret or of the
outside folder.

#### Scenario: A name the outside folder gives too
- **WHEN** `LADO_ENV_DIR` holds `YOUGILE_API_KEY` with `yk-out`, `shop` has the secret
  `YOUGILE_API_KEY` and the UI asks `GET /api/projects/shop`
- **THEN** `overrides` is `["YOUGILE_API_KEY"]` and the answer holds no `yk-out` and no
  value of the secret

#### Scenario: A secret file the agents do not get
- **WHEN** `<LADO_HOME>/projects/shop/secrets/SENTRY_DSN` has mode 644
- **THEN** `secrets` holds `SENTRY_DSN` and `unused` holds `{name: "SENTRY_DSN", reason:
  "readable or writable by others: chmod 600 it"}`, and `overrides` does not name it

### Requirement: The session's project links to the project's page

In the session's head and in a phone's session details, the project's title SHALL be a
link to the project's page `/projects/<id>`, its tooltip kept.

#### Scenario: From the head to the project
- **WHEN** the human clicks `Shop` in the head of `shop-frontend`
- **THEN** the Projects section opens at `/projects/shop`

### Requirement: The server lists the projects

`GET /api/projects` SHALL answer every project by id as `{id, title, folder, found, repos,
running}`: `repos` the number of its repositories read from the disk as `lado project show`
reads them (0 when its folder is not found), `running` the names of its sessions that are
not stopped. Without `lado.db` it SHALL answer an empty list and make no `lado.db`.

#### Scenario: Two projects
- **WHEN** `acme` has one repository and `shop` two, with `shop-frontend` running
- **THEN** the answer is `acme` with `repos: 1, running: []`, then `shop` with `repos: 2,
  running: ["shop-frontend"]`

#### Scenario: A folder not found
- **WHEN** the folder of `sandbox` was deleted by hand
- **THEN** its entry has `found: false` and `repos: 0`

### Requirement: The server makes a project

`POST /api/projects` with `{id, title}` (`title` optional) and the token for changes
(`guard.changes`) SHALL make the project as `lado project create` does and answer it as `GET
/api/projects/{id}` does. Each refusal of the core SHALL be 400 with the core's text, with
nothing made.

#### Scenario: Made
- **WHEN** the UI sends `POST /api/projects` with `{"id": "shop-eu", "title": "Shop EU"}`
- **THEN** the project `shop-eu` titled `Shop EU` and its folder `<workspace>/projects/shop-eu`
  exist, and the answer is the project with `repos: []`

#### Scenario: A folder of the name exists
- **WHEN** `<workspace>/projects/shop-eu` exists and is no project's
- **THEN** the answer is 400 with `<workspace>/projects/shop-eu already exists: LADO makes a
  project's folder itself; choose another id or move that folder away`, and no record is
  made

#### Scenario: Without the token
- **WHEN** a client sends `POST /api/projects` without the token for changes
- **THEN** it is refused as every change is, and nothing is made

### Requirement: The server suggests a project's id from a title

`GET /api/project-id?title=<text>` SHALL answer `{id, folder, problem}` and make nothing:
`id` the name a fresh start makes of the text, with `_` made `-`, cut to 40 characters and
trimmed of `-`, or null when nothing is left; `folder` the id's folder; `problem` the core's
refusal of `lado project create <id>` (`projects.check_new`), the reason there is no id, or
null. `?id=<id>` SHALL answer the same for that id as typed.

#### Scenario: A Cyrillic title
- **WHEN** the UI asks `GET /api/project-id?title=Магазин EU`
- **THEN** the answer is `{id: "magazin-eu", folder: "<workspace>/projects/magazin-eu",
  problem: null}`

#### Scenario: A taken id
- **WHEN** `shop` exists and the UI asks `GET /api/project-id?title=Shop`
- **THEN** `id` is `shop` and `problem` is `project shop exists`

#### Scenario: A typed id
- **WHEN** the UI asks `GET /api/project-id?id=Shop`
- **THEN** `problem` is the core's `the project id Shop is not valid: …`

#### Scenario: No Latin letter
- **WHEN** the UI asks `GET /api/project-id?title=日本`
- **THEN** `id` is null and `problem` is the fresh start's `the name needs a Latin letter or
  digit for its folder: type one`

### Requirement: The Projects section lists the projects

The Projects section (`/projects`) SHALL list the projects of `GET /api/projects` at the
left, as Sessions lists sessions: each row the title (the id without one), then `<id> · <N>
repositories · <N> running` (`no sessions running` when none runs) and the mark `folder not
found` when its folder is missing; a search by title and id; a `+` labelled `New project`. A
row SHALL open the project at `/projects/<id>` at the right; an unknown id SHALL show `No
project <id>`.

#### Scenario: The list
- **WHEN** the human opens Projects with `acme` (titled `ACME CRM`, one repository) and
  `shop` (titled `Shop`, two repositories, two sessions running)
- **THEN** the rows read `ACME CRM` `acme · 1 repository · no sessions running` and `Shop`
  `shop · 2 repositories · 2 running`

### Requirement: The project list follows the sessions

The project list SHALL be read anew when the section opens and when a session starts or
stops.

#### Scenario: A session starts
- **WHEN** the section is open and a session of `acme` starts
- **THEN** the row of `acme` reads `1 running` without a reload

### Requirement: The Projects section has an empty state

With no project the Projects section SHALL show `No projects yet`, a sentence on what a
project is, and one button `New project…`.

#### Scenario: No project
- **WHEN** the human opens Projects and LADO has no project
- **THEN** the section shows `No projects yet` and the button `New project…`

### Requirement: The Projects section takes the phone's screen in turns

On a phone the project list SHALL fill the screen and a project SHALL open in its place,
with a link `← All projects` above it.

#### Scenario: On a phone
- **WHEN** the human opens `/projects/shop` on a phone
- **THEN** only the project shows, with `← All projects` above it, which opens the list

### Requirement: The UI makes a project

`New project…` and the list's `+` SHALL open a dialog with Title (optional), Id, the
warning `⚠ Projects of one LADO are not isolated from each other. For clients that must not
mix, run a separate LADO.`, Cancel and `Create project`. `Create project` SHALL send `POST
/api/projects`, show a refusal under Id, and on success close the dialog and open
`/projects/<id>`.

#### Scenario: Made from the dialog
- **WHEN** the human types the title `Shop EU` and clicks `Create project`
- **THEN** the dialog closes and `/projects/shop-eu` shows `Shop EU`

### Requirement: New project's id follows the title until edited

Until the human edits Id, Id SHALL follow the title by `GET /api/project-id?title=`; an
edited Id SHALL be checked by `?id=`. Under Id the dialog SHALL show `Its folder: <workspace>/projects/<id>. The id never changes.`, or the
core's refusal of the id in its place, with `Create project` disabled while a refusal holds.

#### Scenario: The id follows the title
- **WHEN** the human types the title `Shop EU`
- **THEN** Id reads `shop-eu` and the note `Its folder: <workspace>/projects/shop-eu. The id
  never changes.`

#### Scenario: An edited id stays
- **WHEN** the human edits Id to `eu-shop` and then changes the title
- **THEN** Id stays `eu-shop`

#### Scenario: A refused id
- **WHEN** Id is `shop` and `shop` exists
- **THEN** `project shop exists` shows under Id and `Create project` is disabled

### Requirement: The project's page shows the project and what is not built yet

The project's page SHALL show the title (the id without one), the id, the line `<N>
repositories · <N> sessions running · folder <folder>` (`folder not found` after the folder
when it is missing), and the line `Repositories, sessions, renaming and deleting the
project: not built yet. Plan: Projects, step S7. Meanwhile: lado project show <id>, lado
project repo add <id> <git-url>.` with the plan a link.

#### Scenario: The head of the page
- **WHEN** the human opens `/projects/shop`
- **THEN** the page shows `Shop`, `shop`, `2 repositories · 2 sessions running · folder
  <workspace>/projects/shop` and the not-built line naming `lado project show shop`

### Requirement: The project's page warns that projects are not isolated

Above the variables the project's page SHALL always show `⚠ Projects of one LADO are not
isolated from each other: an agent of one project can read another's variables and secrets.
For clients that must not mix, run a separate LADO.`

#### Scenario: Always there
- **WHEN** the human opens a project with no variables and no secrets
- **THEN** the warning shows

### Requirement: The project's page says which agents get new values

Under the warning the page SHALL always show, while sessions of the project run, `New values
reach the agents started after a change; running agents keep the environment they started
with. Running now: <sessions> — restart a session to give it the change.`, each session by
its title (its name without one) as a link to the session; with none, `New values reach the
agents started after a change. No session of this project is running.` The line SHALL follow
the sessions' starts and stops.

#### Scenario: Two sessions run
- **WHEN** `shop-frontend` (titled `Checkout redesign`) and `shop-backend` run
- **THEN** the line names `Checkout redesign` and `shop-backend` as links to their sessions

#### Scenario: A session stops
- **WHEN** the page is open and `shop-backend` stops
- **THEN** `shop-backend` leaves the line without a reload

### Requirement: The UI sets, edits and removes a project's plain variables

The page SHALL show a block `Variables` with each plain variable's name and value by name,
`Edit` (in place, `Save` and `Cancel`), `Remove`, and `+ Add variable` (a name and a value).
They SHALL go through `PUT` and `DELETE /api/projects/{id}/variables/{name}`; a refusal
SHALL show the core's text verbatim under the row, the fields kept.

#### Scenario: Add a variable
- **WHEN** the human adds `BOARD_URL` with `https://a`
- **THEN** the block lists `BOARD_URL` `https://a` by name

#### Scenario: Edit in place
- **WHEN** the human edits `BOARD_URL` to `https://b` and saves
- **THEN** the row shows `https://b`

### Requirement: A name that looks like a secret is offered as a secret

For the refusal of a plain variable whose name looks like a secret the UI SHALL offer `Add
<NAME> as a secret instead`, which closes the variable's form and opens the secret's form
with the name and an empty value.

#### Scenario: A name that looks like a secret
- **WHEN** the human adds the variable `STRIPE_KEY` with `sk_test_1`
- **THEN** `STRIPE_KEY looks like a secret (KEY): a plain variable takes no name with TOKEN,
  KEY, SECRET or PASSWORD; set it as a secret with lado project set shop STRIPE_KEY
  --secret` shows with `Add STRIPE_KEY as a secret instead`

#### Scenario: As a secret instead
- **WHEN** the human clicks `Add STRIPE_KEY as a secret instead`
- **THEN** the secret's form opens with the name `STRIPE_KEY` and an empty value, and
  `sk_test_1` is in no field

### Requirement: The UI sets, replaces and removes a project's secrets without showing them

The page SHALL show a block `Secrets` with each secret's name and `set · hidden`, `Replace`,
`Remove` and `+ Add secret`, through `PUT` and `DELETE /api/projects/{id}/secrets/{name}`; a
refusal (an empty value, a reserved or invalid name, a name held by a plain variable) SHALL
show the core's text verbatim under the row. No screen SHALL show a secret's value.

#### Scenario: Add a secret
- **WHEN** the human adds the secret `GH_TOKEN` with `ghp_1`
- **THEN** the block lists `GH_TOKEN` `set · hidden` and the value field is empty

### Requirement: A secret's value is typed into a hidden field emptied after use

A secret's value SHALL be typed into a hidden field (`type="password"`, no autocomplete)
that is empty after a save, after Cancel and after the page is left; Replace SHALL open an
empty field with the placeholder `New value (the old one is not shown)`.

#### Scenario: Replace
- **WHEN** the human replaces `GH_TOKEN` with `ghp_2`
- **THEN** agents started after it get `ghp_2`, and the field is closed and empty

#### Scenario: A name held by a plain variable
- **WHEN** `BOARD_URL` is a plain variable and the human adds the secret `BOARD_URL`
- **THEN** `BOARD_URL is a plain variable of shop; remove it first with lado project unset
  shop BOARD_URL` shows

### Requirement: A secret's value leaves the browser only in the body of its request

The UI SHALL send a secret's value only as the JSON body of one `PUT
/api/projects/{id}/secrets/{name}`: never in a URL, a query or a header, never in
`localStorage`, `sessionStorage` or a cookie, never in a field the browser keeps in its form
history; the server SHALL write it in no log. Nothing the UI or the change feed receives
SHALL hold it.

#### Scenario: After a replace
- **WHEN** the human replaces `GH_TOKEN` with a unique value in the browser
- **THEN** the value is in no URL the page visited, in neither storage of the page, and in no
  file under `LADO_HOME` but the secret's own

### Requirement: The project's page marks a name that overrides the outside folder

A variable or secret whose name is in `overrides` SHALL carry the mark `overrides outside
value` with the tooltip `The outside folder (LADO_ENV_DIR) also gives <NAME>. This
project's sessions get the project's value; its outside value is not shown.`

#### Scenario: An overridden key
- **WHEN** `LADO_ENV_DIR` gives `YOUGILE_API_KEY` and `shop` has it as a secret
- **THEN** its row carries `overrides outside value`, and no outside value is on the page

### Requirement: The project's page names a secret file its agents do not get

A secret in `unused` SHALL show `⚠ Agents do not get it: <reason>` in its row, keeping
Replace and Remove; an entry of `unused` that is no secret's name (a link, a bad name) SHALL
show as `⚠ <name>: agents do not get it: <reason>` under the block, and one for the folder
as `⚠ The secrets folder is not used: <reason>`.

#### Scenario: A loose file
- **WHEN** `SENTRY_DSN`'s file has mode 644
- **THEN** its row shows `⚠ Agents do not get it: readable or writable by others: chmod 600
  it`

#### Scenario: A replace mends it
- **WHEN** the human replaces `SENTRY_DSN`
- **THEN** its file has mode 600 and the row shows no warning

### Requirement: Removing a variable or a secret asks in its row

`Remove` SHALL turn the row into `Remove <NAME>? Remove · Cancel`; only the second `Remove`
SHALL send the `DELETE`.

#### Scenario: Cancelled
- **WHEN** the human clicks `Remove` on `GH_TOKEN`, then `Cancel`
- **THEN** no request is sent and `GH_TOKEN` stays
