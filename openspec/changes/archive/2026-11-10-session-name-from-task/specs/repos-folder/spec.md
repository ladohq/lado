## MODIFIED Requirements

### Requirement: Where hints and recent folders leave out LADO's projects/

The subfolders the server gives for the workspace SHALL leave out `projects` when it is
LADO's (capability `projects`), a folder inside LADO's `projects/` SHALL have none, and the
recent places SHALL leave out the folders inside it, but a project's repository whose
session ran in that project, listed as a project item (capability new-session-window).

#### Scenario: The workspace with projects
- **WHEN** `/Users/ann/workspace` holds `app` and `projects`, which holds the folder of the
  project `shop`, and the human clicks into an empty path field
- **THEN** the list shows `app/` only

#### Scenario: The human's own projects folder
- **WHEN** `/Users/ann/workspace/projects` holds only the human's `notes` and LADO has no
  project
- **THEN** the list shows `projects/` as any folder

#### Scenario: A project's session in the recent places
- **WHEN** the latest session ran in the repository `backend` of the project `shop`
- **THEN** `/api/folders/recent` lists it with `project: {id: "shop", title, repo:
  "backend"}`, and Where's Recent shows `backend` with `in project <title>`
