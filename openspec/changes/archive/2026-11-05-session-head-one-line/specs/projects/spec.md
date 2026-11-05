## MODIFIED Requirements

### Requirement: The session's API and head show its project

`SessionInfo` SHALL carry `project`, the project's id or null. `SessionAbout` SHALL carry
`project`, `{id, title}` read when asked, or null. Outside the phone layout the head of a
session in a project SHALL show the project's title (its id when it has none) as a breadcrumb
before the session's title, with `Project <id>` in its tooltip; Details and the phone's sheet
SHALL show `project <title>` in their state line. A session without a project SHALL show
neither.

#### Scenario: The head of a session in a project
- **WHEN** the human opens `shop-frontend` of project `shop` titled `Shop`
- **THEN** the head reads `Shop / <the session's title>`, and the tooltip of `Shop` has
  `Project shop`

#### Scenario: Renamed project
- **WHEN** the project is renamed `Shop EU` and the human opens the session again
- **THEN** the head shows `Shop EU` before the session's title

### Requirement: The session's project links to the project's page

In the session's head and in the session's details, the project's title SHALL be a
link to the project's page `/projects/<id>`, its tooltip kept.

#### Scenario: From the head to the project
- **WHEN** the human clicks `Shop` in the head of `shop-frontend`
- **THEN** the Projects section opens at `/projects/shop`

### Requirement: The project's page renames the project in place

The title in the head of the project's page and its `Rename` button SHALL open a field in
the title's place holding the title; Enter or leaving the field SHALL save it through
`PATCH /api/projects/{id}`, Esc SHALL cancel, an empty field SHALL clear the title (the id
then shows), and the same text as stored SHALL send nothing. A refusal SHALL show under the
field verbatim, the field kept open with the text. After a save the head and the project
list SHALL show the new title.

#### Scenario: Renamed
- **WHEN** the human clicks `Rename` on `/projects/shop`, types `Shop EU` and presses Enter
- **THEN** the head and the list's row read `Shop EU`, and the session `shop-frontend`'s
  head reads `Shop EU` before its title when it is next opened

#### Scenario: Tab takes the id
- **WHEN** the project `shop` has no title, the human clicks `Rename` and presses Tab
- **THEN** the field holds `shop`, nothing is sent, and the focus stays in the field

#### Scenario: Cancelled
- **WHEN** the human types in the field and presses Esc
- **THEN** the title stays as it was and nothing is sent

### Requirement: The New session window starts a session in a project

The New session window SHALL have the source **Project** last in its switch. Project SHALL
show a select of the projects (one whose folder is not found off, marked `folder not
found`), the chosen project's line `<N> repositories · <N> sessions running · folder
<folder>`, and its repositories, each with its name, branch and remote, one chosen. Its
start button SHALL start with `where: {kind: "project", project, repo}` and open the
session's page. The window's first source SHALL stay as before.

#### Scenario: Start in a project's repository
- **WHEN** the human picks Project, `Shop`, then `frontend`, and clicks `Start in Shop`
- **THEN** the session `shop-frontend` starts in the project and its page opens, its head
  showing `Shop` before its title
