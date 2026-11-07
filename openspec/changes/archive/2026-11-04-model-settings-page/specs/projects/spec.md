## MODIFIED Requirements

### Requirement: The Project way takes the session's settings as Folder does

In Project, Name SHALL be the default name until the human edits it, with the folder
check's notes for a taken name; Kits and Permission mode SHALL come from the repository's
last session, as Folder takes them from a folder's, and Agent CLI from the server's
suggestion. A refused start SHALL show the core's text, with `Resume it` or `Open it` as
for a folder, only when the session that has the name is of this project.

#### Scenario: A taken name
- **WHEN** a stopped `shop-frontend` of this repository exists and the human clicks `Start
  in Shop`
- **THEN** the window shows `session "shop-frontend" exists already (stopped, in
  <workspace>/projects/shop/frontend); resume it, or give the new session another name`
  and `Resume it`, also when the workspace's path goes through a link
