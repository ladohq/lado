## MODIFIED Requirements

### Requirement: The Project way's start names the project

For a project's repository the start button SHALL read `Start in <title>` (the id without
one), and `Start new session in <title>` when the repository has a stopped session of the
default name, so the human sees which project's keys the session gets; another place's button
names the place.

#### Scenario: Another project than the one last used
- **WHEN** the window opens on `Shop`, the project last used, and the human picks `ACME CRM`
  and its repository `crm`
- **THEN** the button reads `Start in ACME CRM`, and the session `acme-crm` starts in the
  project `acme`, as its head and `lado ls` show

### Requirement: The Project way takes the session's settings as Folder does

For a project's repository, Team's Name SHALL be the default name, else the free name, until
the human edits it; Team setup and Permissions SHALL come from the repository's last session,
as for a folder, and Agent from the server's suggestion. The line `Session <name> stopped here`
SHALL name only a stopped session of the name that is of this project.

#### Scenario: A taken name
- **WHEN** a stopped `shop-frontend` of this repository exists and the window opens on it
- **THEN** Team reads `Name shop-frontend-2`, and the footer shows one button, `Start new
  session in Shop`, and no `Resume shop-frontend`, also when the workspace's path goes through a
  link
