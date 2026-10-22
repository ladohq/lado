## ADDED Requirements

### Requirement: A folder inside LADO's projects/ is no fresh start's folder

The check of a fresh start's folder SHALL also give this state, which lets no fresh start
go on, checked before the others:

| State | When | Text |
|---|---|---|
| `in_project` | the folder, by its real path, is inside LADO's `<workspace>/projects` (capability `projects`) | the refusal of a new session there, with its hint |

#### Scenario: A fresh start in a project's folder
- **WHEN** the human runs `lado start --new ~/workspace/projects/shop/site` and `shop` is a
  project
- **THEN** it exits 1 with the refusal naming the project and `lado start --project shop
  --repo site`, and no folder `site` is made
