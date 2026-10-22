## ADDED Requirements

### Requirement: Where hints and recent folders leave out LADO's projects/

The subfolders the server gives for the workspace SHALL leave out `projects` when it is
LADO's (capability `projects`), a folder inside LADO's `projects/` SHALL have none, and the
recent folders SHALL leave out the folders inside it.

#### Scenario: The workspace with projects
- **WHEN** `/Users/ann/workspace` holds `app` and `projects`, which holds the folder of the
  project `shop`, and the human clicks into an empty Where
- **THEN** the list shows `app/` only

#### Scenario: The human's own projects folder
- **WHEN** `/Users/ann/workspace/projects` holds only the human's `notes` and LADO has no
  project
- **THEN** the list shows `projects/` as any folder
